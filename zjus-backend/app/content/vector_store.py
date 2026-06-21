"""pgvector-backed character retrieval helpers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    Embeddings are generated offline by `scripts/embed_world_data.py`; the
    production runtime only loads precomputed query vectors and performs
    pgvector similarity search.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ============================================================
# Precomputed query vectors.
# ============================================================

_query_embeddings: Dict[str, List[float]] = {}


def _world_dir() -> Path:
    docker_path = Path("/app/world")
    if docker_path.exists():
        return docker_path
    return Path(__file__).resolve().parent.parent.parent / "world"


def _load_query_embeddings() -> Dict[str, List[float]]:
    """
    Load precomputed query vectors.

    The `world/query_embeddings.json` shape is:
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
# Runtime retrieval.
# ============================================================

async def search_similar_characters(
    context: str,
    top_k: int = 3,
    db: Optional[AsyncSession] = None,
) -> List[Dict[str, Any]]:
    """
    Search similar characters using a precomputed context vector.

    The runtime path performs only pgvector cosine-distance sorting.

    Args:
        context: Scene identifier such as "random" or "low_sanity".
        top_k: Maximum number of matches to return.

    Returns:
        Character dictionaries with similarity scores.
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
    Search the most similar characters by cosine distance.

    Returns:
        Raw character dictionaries with similarity scores.
    """
    own_session = db is None
    session = db or AsyncSessionLocal()

    try:
        vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
        sql = text(
            """
            SELECT char_json, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM character_embeddings
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :k
            """
        )
        result = await session.execute(sql, {"vec": vec_str, "k": top_k})
        rows = result.fetchall()

        results = []
        for row in rows:
            char_data = json.loads(row[0])
            if isinstance(char_data, dict):
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
            await session.close()
