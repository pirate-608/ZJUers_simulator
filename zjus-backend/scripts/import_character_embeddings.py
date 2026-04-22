"""
导入预构建角色向量到 PostgreSQL(pgvector)。

用途：
  - 运行时不再调用 embedding 模型推理。
  - 部署阶段将 world/character_embeddings.csv 导入 character_embeddings 表。

特性：
  - 幂等：每次导入前清空旧数据。
  - 兼容 Docker 与本地路径探测。
"""

import asyncio
import csv
import json
from pathlib import Path

from sqlalchemy import text

from app.core.database import AsyncSessionLocal
from app.models.embedding import EMBEDDING_DIM


def _world_dir() -> Path:
    docker_path = Path("/app/world")
    if docker_path.exists():
        return docker_path
    return Path(__file__).resolve().parent.parent / "world"


async def import_character_embeddings() -> int:
    csv_path = _world_dir() / "character_embeddings.csv"
    if not csv_path.exists():
        print(f"[seed_embeddings] CSV not found: {csv_path}")
        return 1

    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            embedding_raw = row.get("embedding", "[]")
            try:
                embedding = json.loads(embedding_raw)
            except json.JSONDecodeError:
                print("[seed_embeddings] Invalid embedding JSON, skip one row")
                continue

            if not isinstance(embedding, list) or not embedding:
                continue

            rows.append(
                {
                    "char_name": row.get("char_name", ""),
                    "char_role": row.get("char_role", "unknown"),
                    "source_text": row.get("source_text", ""),
                    "embedding": embedding,
                    "char_json": row.get("char_json", "{}"),
                }
            )

    if not rows:
        print("[seed_embeddings] No valid rows found in CSV")
        return 1

    async with AsyncSessionLocal() as db:
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS character_embeddings (
                    id SERIAL PRIMARY KEY,
                    char_name VARCHAR(128) NOT NULL,
                    char_role VARCHAR(64) NOT NULL,
                    source_text TEXT NOT NULL,
                    embedding vector({EMBEDDING_DIM}) NOT NULL,
                    char_json TEXT NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
        )
        await db.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_character_embeddings_cosine
                ON character_embeddings USING hnsw (embedding vector_cosine_ops)
                """
            )
        )

        await db.execute(text("TRUNCATE TABLE character_embeddings RESTART IDENTITY"))

        insert_sql = text(
            """
            INSERT INTO character_embeddings
              (char_name, char_role, source_text, embedding, char_json)
            VALUES
              (:char_name, :char_role, :source_text, CAST(:embedding AS vector), :char_json)
            """
        )

        for row in rows:
            await db.execute(
                insert_sql,
                {
                    "char_name": row["char_name"],
                    "char_role": row["char_role"],
                    "source_text": row["source_text"],
                    "embedding": "[" + ",".join(str(v) for v in row["embedding"]) + "]",
                    "char_json": row["char_json"],
                },
            )

        await db.commit()

    print(f"[seed_embeddings] Imported {len(rows)} rows from {csv_path}")
    return 0


def main() -> None:
    code = asyncio.run(import_character_embeddings())
    raise SystemExit(code)


if __name__ == "__main__":
    main()
