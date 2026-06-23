"""LLM client and shared content-cache isolation tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.llm import generate_random_event


@pytest.mark.asyncio
async def test_custom_llm_random_event_does_not_use_global_content_cache():
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"events":[{"title":"云端事件","desc":"自定义模型生成",'
                        '"options":[{"id":"A","text":"看看","effects":{"sanity":1}},'
                        '{"id":"B","text":"离开","effects":{"energy":1}}]}]}'
                    )
                )
            )
        ]
    )
    client = Mock()
    client.chat.completions.create = AsyncMock(return_value=response)
    client.close = AsyncMock()

    with (
        patch(
            "app.core.llm._resolve_llm_config",
            return_value=("custom-key", "https://example.test/v1", "custom-model"),
        ),
        patch("app.core.llm._get_client", return_value=client),
        patch("app.core.llm.RedisCache") as redis_cache,
    ):
        redis_cache.lpop = AsyncMock()
        redis_cache.rpush_many_with_limit = AsyncMock()

        result = await generate_random_event(
            {"sanity": 80, "stress": 20},
            llm_override={"api_key": "custom-key", "model": "custom-model"},
        )

    assert result["title"] == "云端事件"
    redis_cache.lpop.assert_not_awaited()
    redis_cache.rpush_many_with_limit.assert_not_awaited()
    client.close.assert_awaited_once()
