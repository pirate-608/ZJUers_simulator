from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.llm import generate_dingtalk_reply_message


@pytest.mark.asyncio
async def test_generate_dingtalk_reply_message_uses_generic_llm(sample_player_stats):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"npc_reply":"那我一会儿把资料发你。",'
                        '"reply_options":["谢谢！","我先看看","还有别的吗？"]}'
                    )
                )
            )
        ]
    )
    client = Mock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with patch(
        "app.core.llm._resolve_llm_config",
        return_value=("test-key", "https://example.test/v1", "qwen-test"),
    ), patch("app.core.llm._get_client", return_value=client):
        result = await generate_dingtalk_reply_message(
            {
                "name": "【学习委员】",
                "role": "classmate",
                "content": "你是热心但有点忙的学习委员。",
                "examples": ["我把资料发群里了。"],
            },
            sample_player_stats,
            [{"speaker": "npc", "content": "你要复习资料吗？"}],
            "可以发我一份吗？",
            reply_count=1,
        )

    assert result == {
        "content": "那我一会儿把资料发你。",
        "reply_options": [
            {"option_id": "opt_1", "text": "谢谢！"},
            {"option_id": "opt_2", "text": "我先看看"},
            {"option_id": "opt_3", "text": "还有别的吗？"},
        ],
    }
    client.chat.completions.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_dingtalk_reply_message_can_return_settlement(
    sample_player_stats,
):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"npc_reply":"那就先这样，别太焦虑。",'
                        '"settlement":{"desc":"朋友安慰了你。","effects":{"sanity":2}}}'
                    )
                )
            )
        ]
    )
    client = Mock()
    client.chat.completions.create = AsyncMock(return_value=response)

    with patch(
        "app.core.llm._resolve_llm_config",
        return_value=("test-key", "https://example.test/v1", "qwen-test"),
    ), patch("app.core.llm._get_client", return_value=client):
        result = await generate_dingtalk_reply_message(
            {"name": "【朋友】", "role": "friend", "content": "你是玩家的朋友。"},
            sample_player_stats,
            [{"speaker": "player", "content": "我有点慌。"}],
            "那我先去复习。",
            reply_count=3,
        )

    assert result == {
        "content": "那就先这样，别太焦虑。",
        "settlement": {
            "desc": "朋友安慰了你。",
            "effects": {"sanity": 2},
        },
    }
