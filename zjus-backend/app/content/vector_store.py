"""
pgvector 向量存储抽象层

架构设计要点：
  - Embedding 生成仅在本地开发机上离线执行（scripts/embed_world_data.py）
  - 运行时（2C2G 云服务器）不调用任何模型，仅使用预计算的查询向量做 pgvector 检索
  - 查询向量预存于 world/query_embeddings.json，启动时加载到内存
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ============================================================
# 预计算查询向量（运行时零推理）
# ============================================================

_query_embeddings: Dict[str, List[float]] = {}


def _world_dir() -> Path:
    docker_path = Path("/app/world")
    if docker_path.exists():
        return docker_path
    return Path(__file__).resolve().parent.parent.parent / "world"


def _load_query_embeddings() -> Dict[str, List[float]]:
    """
    加载预计算的查询向量。

    文件格式 (world/query_embeddings.json):
    {
        "random": [0.123, -0.456, ...],
        "low_sanity": [...],
        "high_stress": [...],
        "low_gpa": [...]
    }
    """
    global _query_embeddings
    if _query_embeddings:
        return _query_embeddings

    path = _world_dir() / "query_embeddings.json"
    if not path.exists():
        logger.warning("query_embeddings.json not found at %s", path)
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            _query_embeddings = json.load(f)
        logger.info(
            "Loaded %d pre-computed query embeddings: %s",
            len(_query_embeddings),
            list(_query_embeddings.keys()),
        )
    except Exception as e:
        logger.error("Failed to load query_embeddings.json: %s", e)

    return _query_embeddings


# ============================================================
# 检索（运行时，纯 SQL，不调用任何模型）
# ============================================================

async def search_similar_characters(
    context: str,
    top_k: int = 3,
    db: Optional[AsyncSession] = None,
) -> List[Dict[str, Any]]:
    """
    根据预计算的 context 查询向量检索最相似角色。

    运行时零模型推理，仅 pgvector 余弦距离排序。

    Args:
        context: 场景标识 ("random" / "low_sanity" / "high_stress" / "low_gpa")
        top_k: 返回数量

    Returns:
        [{"char": <角色 dict>, "similarity": float}, ...]
    """
    query_vecs = _load_query_embeddings()
    query_vec = query_vecs.get(context)

    if not query_vec:
        logger.warning("No pre-computed embedding for context '%s'", context)
        return []

    return await search_by_vector(query_vec, top_k=top_k, db=db)


async def search_by_vector(
    query_vec: List[float],
    top_k: int = 3,
    db: Optional[AsyncSession] = None,
) -> List[Dict[str, Any]]:
    """
    根据向量搜索最相似的角色（余弦距离）。

    Returns:
        [{"char": <原始 character dict>, "similarity": float}, ...]
    """
    own_session = db is None
    if own_session:
        db = AsyncSessionLocal()

    try:
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = text(
            """
            SELECT char_json, 1 - (embedding <=> :vec::vector) AS similarity
            FROM character_embeddings
            ORDER BY embedding <=> :vec::vector
            LIMIT :k
            """
        )
        result = await db.execute(sql, {"vec": vec_str, "k": top_k})
        rows = result.fetchall()

        results = []
        for row in rows:
            char_data = json.loads(row[0])
            results.append({
                "char": char_data,
                "similarity": float(row[1]),
            })
        return results
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        return []
    finally:
        if own_session:
            await db.close()
