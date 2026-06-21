"""Generate offline embeddings for character and query-vector retrieval.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    This development-only script reads `world/characters.json`, generates
    bge-m3 embeddings through local Ollama, writes pgvector rows, and exports
    backup CSV/query-vector files.

Prerequisites:
    - Local `ollama serve` with `bge-m3` pulled.
    - Docker PostgreSQL reachable at `localhost:15432`.

Usage:
    # Full flow: generate embeddings and write them to PostgreSQL.
    python scripts/embed_world_data.py

    # Export CSV and query_embeddings.json without writing PostgreSQL rows.
    python scripts/embed_world_data.py --csv-only
"""

import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests

# Make backend imports available when the script is run directly.
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

# Load `.env` from either `zjus-backend/` or the repository root.
for env_candidate in [_project_root / ".env", _project_root.parent / ".env"]:
    if env_candidate.exists():
        from dotenv import load_dotenv
        load_dotenv(env_candidate)
        break

# ============================================================
# Configuration.
# ============================================================

OLLAMA_EMBED_URL = "http://localhost:11434/api/embed"
OLLAMA_EMBED_MODEL = "bge-m3"

WORLD_DIR = _project_root / "world"
if not WORLD_DIR.exists():
    WORLD_DIR = _project_root / "zjus-backend" / "world"

# Context prompts used to precompute DingTalk character-retrieval query vectors.
CONTEXT_QUERIES = {
    "random": "浙江大学 日常校园生活 同学 室友 社团 聊天",
    "low_sanity": "浙江大学 学生情绪低落 心态崩了 需要关心安慰 室友 暗恋对象 辅导员",
    "high_stress": "浙江大学 学生压力很大 考试焦虑 作业太多 需要放松 室友 同学",
    "low_gpa": "浙江大学 学业困难 成绩不好 挂科 需要学业帮助 助教 老师 学习委员",
}


# ============================================================
# Ollama embedding client for this offline script.
# ============================================================

def get_embedding(text: str) -> List[float]:
    """Fetch one bge-m3 embedding from local Ollama."""
    resp = requests.post(
        OLLAMA_EMBED_URL,
        json={"model": OLLAMA_EMBED_MODEL, "input": text},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    embeddings = data.get("embeddings", [])
    if embeddings:
        return embeddings[0]
    raise ValueError(f"No embedding returned for: {text[:50]}...")


# ============================================================
# Load `characters.json`.
# ============================================================

def load_characters() -> List[Dict[str, Any]]:
    """Load character records before generating embedding artifacts."""
    path = WORLD_DIR / "characters.json"
    if not path.exists():
        print(f"❌ characters.json 未找到: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Generate character embeddings.
# ============================================================

def generate_character_embeddings(characters: List[Dict]) -> List[Dict[str, Any]]:
    """Generate one embedding record for each character."""
    results = []
    for i, char in enumerate(characters):
        name = char.get("name", "未知")
        role = char.get("role", "unknown")
        content = char.get("content", "")
        examples = char.get("examples", [])

        source_text = f"{name} {role} {content} {' '.join(examples[:3])}"

        print(f"  [{i+1}/{len(characters)}] Embedding: {name} ...", end=" ")
        try:
            vec = get_embedding(source_text)
            print(f"✅ dim={len(vec)}")
            results.append({
                "char_name": name,
                "char_role": role,
                "source_text": source_text,
                "embedding": vec,
                "char_json": json.dumps(char, ensure_ascii=False),
            })
        except Exception as e:
            print(f"❌ {e}")

    return results


# ============================================================
# Generate precomputed query vectors.
# ============================================================

def generate_query_embeddings() -> Dict[str, List[float]]:
    """Generate precomputed query vectors for all DingTalk contexts."""
    print("\n🔎 生成预计算查询向量...")
    query_vecs = {}
    for context, query_text in CONTEXT_QUERIES.items():
        print(f"  {context}: \"{query_text[:40]}...\"", end=" ")
        try:
            vec = get_embedding(query_text)
            query_vecs[context] = vec
            print(f"✅ dim={len(vec)}")
        except Exception as e:
            print(f"❌ {e}")

    # Persist vectors for runtime SQL-only retrieval.
    out_path = WORLD_DIR / "query_embeddings.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(query_vecs, f)
    print(f"\n📄 查询向量已保存: {out_path} ({len(query_vecs)} 个 context)")

    return query_vecs


# ============================================================
# CSV export.
# ============================================================

def export_csv(records: List[Dict], output_path: Path):
    """Export embedding records to a CSV backup file."""
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["char_name", "char_role", "source_text", "embedding", "char_json"])  # noqa: E501
        for rec in records:
            vec_str = "[" + ",".join(f"{v:.6f}" for v in rec["embedding"]) + "]"
            writer.writerow([
                rec["char_name"],
                rec["char_role"],
                rec["source_text"],
                vec_str,
                rec["char_json"],
            ])
    print(f"\n📄 CSV 已导出: {output_path} ({len(records)} 行)")


# ============================================================
# pgvector import.
# ============================================================

async def write_to_pgvector(records: List[Dict]):
    """Write embeddings to PostgreSQL, creating pgvector objects if needed."""
    from sqlalchemy import delete, text

    from app.core.database import AsyncSessionLocal
    from app.models.embedding import EMBEDDING_DIM, CharacterEmbedding

    async with AsyncSessionLocal() as db:
        # Ensure the pgvector extension, table, and index exist idempotently.
        await db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await db.execute(text(f"""
            CREATE TABLE IF NOT EXISTS character_embeddings (
                id SERIAL PRIMARY KEY,
                char_name VARCHAR(128) NOT NULL,
                char_role VARCHAR(64) NOT NULL,
                source_text TEXT NOT NULL,
                embedding vector({EMBEDDING_DIM}) NOT NULL,
                char_json TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))
        await db.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_character_embeddings_cosine
            ON character_embeddings USING hnsw (embedding vector_cosine_ops)
        """))
        await db.commit()

        # Replace old vectors so retrieval always matches the current world data.
        await db.execute(delete(CharacterEmbedding))
        for rec in records:
            row = CharacterEmbedding(
                char_name=rec["char_name"],
                char_role=rec["char_role"],
                source_text=rec["source_text"],
                embedding=rec["embedding"],
                char_json=rec["char_json"],
            )
            db.add(row)

        await db.commit()
        print(f"\n🗃️  已写入 pgvector: {len(records)} 条 character embeddings")


# ============================================================
# CLI entry point.
# ============================================================

def main():
    """CLI entry point for generating character embeddings and query vectors."""
    import argparse
    parser = argparse.ArgumentParser(
        description="生成角色 embedding + 查询向量（仅在开发机运行）"
    )
    parser.add_argument(
        "--csv-only", action="store_true",
        help="仅导出 CSV + query_embeddings.json，不写入数据库",
    )
    parser.add_argument(
        "--db-url", type=str, default=None,
        help="数据库 URL（默认用 localhost:15432 连接 Docker PG）",
    )
    args = parser.parse_args()

    # This script runs on the host, so Docker's internal `db:5432` must be
    # converted to the host-published PostgreSQL port.
    if not args.csv_only:
        if args.db_url:
            os.environ["DATABASE_URL"] = args.db_url
        elif "db:" in os.environ.get("DATABASE_URL", ""):
            original = os.environ["DATABASE_URL"]
            fixed = original.replace("@db:", "@localhost:").replace(":5432/", ":15432/")
            os.environ["DATABASE_URL"] = fixed
            print("📌 DATABASE_URL 已自动修正为宿主机地址: ...@localhost:15432/...")

    # Check local Ollama and the required embedding model.
    print("🔍 检查 Ollama bge-m3...")
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        has_bge = any("bge-m3" in m for m in models)
        print(f"  ✅ Ollama 在线，模型: {', '.join(models[:5])}")
        if not has_bge:
            print("  ⚠️  未找到 bge-m3，请先运行: ollama pull bge-m3")
            sys.exit(1)
    except Exception as e:
        print(f"  ❌ Ollama 连接失败: {e}")
        print("  请确保 `ollama serve` 已启动")
        sys.exit(1)

    # Load world characters.
    print("\n📂 加载 characters.json...")
    characters = load_characters()
    print(f"  找到 {len(characters)} 个角色")

    # Generate one embedding per character.
    print("\n🧠 生成角色 bge-m3 embeddings...")
    records = generate_character_embeddings(characters)

    if not records:
        print("\n❌ 没有生成任何 embedding")
        sys.exit(1)

    # Generate context query vectors for runtime retrieval.
    generate_query_embeddings()

    # Export a CSV backup alongside runtime JSON artifacts.
    csv_path = WORLD_DIR / "character_embeddings.csv"
    export_csv(records, csv_path)

    # Write vectors into the development pgvector table unless skipped.
    if not args.csv_only:
        print("\n🗃️  写入 pgvector（连接 Docker PostgreSQL）...")
        try:
            asyncio.run(write_to_pgvector(records))
        except Exception as e:
            print(f"\n⚠️  数据库写入失败: {e}")
            print("  CSV 和 query_embeddings.json 已导出，可稍后导入")
            sys.exit(1)

    print("\n🎉 完毕！产出文件：")
    print(f"  - {WORLD_DIR / 'query_embeddings.json'} (运行时查询向量)")
    print(f"  - {WORLD_DIR / 'character_embeddings.csv'} (备份)")


if __name__ == "__main__":
    main()
