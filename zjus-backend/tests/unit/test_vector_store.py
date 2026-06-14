import json

import pytest

from app.content.vector_store import search_by_vector


class _Result:
    def fetchall(self):
        return [(json.dumps({"name": "【室友】"}, ensure_ascii=False), 0.91)]


class _Session:
    def __init__(self):
        self.sql = ""
        self.params = {}

    async def execute(self, sql, params):
        self.sql = str(sql)
        self.params = params
        return _Result()


@pytest.mark.asyncio
async def test_search_by_vector_uses_asyncpg_safe_vector_cast():
    session = _Session()

    result = await search_by_vector([0.1, 0.2], top_k=2, db=session)  # type: ignore[arg-type]

    assert "CAST(:vec AS vector)" in session.sql
    assert ":vec::vector" not in session.sql
    assert session.params == {"vec": "[0.1,0.2]", "k": 2}
    assert result == [{"char": {"name": "【室友】"}, "similarity": 0.91}]
