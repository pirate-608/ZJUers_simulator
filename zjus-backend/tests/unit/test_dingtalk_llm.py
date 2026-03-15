"""
dingtalk_llm 单元测试

测试 M2-her 消息构建（_build_m2her_messages）逻辑。
API 调用和 Redis 缓存使用 mock，不需要真实服务。
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.core.dingtalk_llm import (
    _build_m2her_messages,
    _call_m2her_api,
    generate_dingtalk_via_m2her,
)


# ==========================================
# _build_m2her_messages 测试（纯函数，无 I/O）
# ==========================================


class TestBuildM2herMessages:
    """测试 character → M2-her messages 映射"""

    def test_basic_structure(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")

        # 必须包含 system, user_system, group, user 角色
        roles = [m["role"] for m in msgs]
        assert roles[0] == "system"
        assert "user_system" in roles
        assert "group" in roles
        assert roles[-1] == "user"  # 最后一条触发生成

    def test_system_message_uses_character_data(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")
        system_msg = msgs[0]
        assert system_msg["name"] == "【室友】"
        assert "室友" in system_msg["content"]

    def test_user_system_contains_player_info(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")
        user_system_msgs = [m for m in msgs if m["role"] == "user_system"]
        assert len(user_system_msgs) == 1
        content = user_system_msgs[0]["content"]
        assert "TestPlayer" in content
        assert "计算机科学与技术" in content
        assert "大一秋冬" in content

    def test_high_stress_adds_description(self, sample_character, sample_player_stats):
        stats = {**sample_player_stats, "stress": 85}
        msgs = _build_m2her_messages(sample_character, stats, "high_stress")
        user_system = [m for m in msgs if m["role"] == "user_system"][0]
        assert "压力很大" in user_system["content"]

    def test_low_sanity_adds_description(self, sample_character, sample_player_stats):
        stats = {**sample_player_stats, "sanity": 20}
        msgs = _build_m2her_messages(sample_character, stats, "low_sanity")
        user_system = [m for m in msgs if m["role"] == "user_system"][0]
        assert "心态不太好" in user_system["content"]

    def test_group_message_contains_context(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "low_gpa")
        group_msgs = [m for m in msgs if m["role"] == "group"]
        assert len(group_msgs) == 1
        assert "成绩亮红灯" in group_msgs[0]["content"]

    def test_sample_messages_from_examples(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")
        sample_ai_msgs = [m for m in msgs if m["role"] == "sample_message_ai"]
        # sample_character has 3 examples → should produce 3 sample_message_ai
        assert len(sample_ai_msgs) == 3
        assert sample_ai_msgs[0]["content"] == "你早上出门忘关空调了！"

    def test_sample_user_replies_between_examples(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")
        sample_user_msgs = [m for m in msgs if m["role"] == "sample_message_user"]
        # 3 examples → 2 user replies (between each pair)
        assert len(sample_user_msgs) == 2

    def test_empty_examples(self, sample_player_stats):
        char = {"name": "【空角色】", "role": "test", "content": "测试", "examples": []}
        msgs = _build_m2her_messages(char, sample_player_stats, "random")
        sample_msgs = [m for m in msgs if "sample_message" in m["role"]]
        assert len(sample_msgs) == 0

    def test_user_trigger_message_is_last(self, sample_character, sample_player_stats):
        msgs = _build_m2her_messages(sample_character, sample_player_stats, "random")
        last = msgs[-1]
        assert last["role"] == "user"
        assert last["name"] == "TestPlayer"


# ==========================================
# _call_m2her_api 测试（mock httpx）
# ==========================================


class TestCallM2herApi:
    """测试 API 调用的各种响应场景"""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self):
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = ""
            result = await _call_m2her_api([{"role": "user", "content": "test"}])
            assert result is None

    @pytest.mark.asyncio
    async def test_success_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [
                {"message": {"content": "今天记得带伞哦！", "role": "assistant"}}
            ],
            "base_resp": {"status_code": 0},
            "output_sensitive": False,
        }

        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            mock_settings.MINIMAX_BASE_URL = "https://test.api.com"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await _call_m2her_api([{"role": "user", "content": "test"}])
                assert result == "今天记得带伞哦！"

    @pytest.mark.asyncio
    async def test_sensitive_output_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "bad content"}}],
            "base_resp": {"status_code": 0},
            "output_sensitive": True,
        }

        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            mock_settings.MINIMAX_BASE_URL = "https://test.api.com"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await _call_m2her_api([{"role": "user", "content": "test"}])
                assert result is None

    @pytest.mark.asyncio
    async def test_api_error_status_returns_none(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [],
            "base_resp": {"status_code": 1001, "status_msg": "rate limited"},
        }

        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            mock_settings.MINIMAX_BASE_URL = "https://test.api.com"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_resp
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await _call_m2her_api([{"role": "user", "content": "test"}])
                assert result is None

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self):
        import httpx as httpx_mod

        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            mock_settings.MINIMAX_BASE_URL = "https://test.api.com"
            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.post.side_effect = httpx_mod.TimeoutException("timeout")
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=False)
                MockClient.return_value = mock_client

                result = await _call_m2her_api([{"role": "user", "content": "test"}])
                assert result is None


# ==========================================
# generate_dingtalk_via_m2her 集成测试（mock 外部依赖）
# ==========================================


class TestGenerateDingtalkViaM2her:
    """测试主入口函数的编排逻辑"""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self, sample_player_stats):
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = ""
            result = await generate_dingtalk_via_m2her(sample_player_stats)
            assert result is None

    @pytest.mark.asyncio
    async def test_returns_cached_message(self, sample_player_stats):
        cached_msg = json.dumps({
            "sender": "【室友】",
            "role": "roommate",
            "content": "缓存消息",
            "is_urgent": False,
        })
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch("app.core.dingtalk_llm.RedisCache") as mock_cache:
                mock_cache.lpop = AsyncMock(return_value=cached_msg)
                result = await generate_dingtalk_via_m2her(sample_player_stats)
                assert result["sender"] == "【室友】"
                assert result["content"] == "缓存消息"

    @pytest.mark.asyncio
    async def test_result_structure(self, sample_player_stats, sample_characters_list):
        """验证返回值结构正确"""
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch("app.core.dingtalk_llm.RedisCache") as mock_cache:
                mock_cache.lpop = AsyncMock(return_value=None)
                mock_cache.rpush_many_with_limit = AsyncMock()
                with patch("app.core.dingtalk_llm._load_characters", return_value=sample_characters_list):
                    with patch("app.core.dingtalk_llm._call_m2her_api", new_callable=AsyncMock) as mock_api:
                        mock_api.return_value = "测试消息内容"
                        result = await generate_dingtalk_via_m2her(sample_player_stats)

                        assert result is not None
                        assert "sender" in result
                        assert "role" in result
                        assert "content" in result
                        assert "is_urgent" in result
                        assert result["content"] == "测试消息内容"

    @pytest.mark.asyncio
    async def test_api_failure_returns_none(self, sample_player_stats, sample_characters_list):
        """所有 API 调用失败时返回 None"""
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch("app.core.dingtalk_llm.RedisCache") as mock_cache:
                mock_cache.lpop = AsyncMock(return_value=None)
                with patch("app.core.dingtalk_llm._load_characters", return_value=sample_characters_list):
                    with patch("app.core.dingtalk_llm._call_m2her_api", new_callable=AsyncMock) as mock_api:
                        mock_api.return_value = None  # API 全部失败
                        result = await generate_dingtalk_via_m2her(sample_player_stats)
                        assert result is None

    @pytest.mark.asyncio
    async def test_empty_characters_returns_none(self, sample_player_stats):
        """无角色数据时返回 None"""
        with patch("app.core.dingtalk_llm.settings") as mock_settings:
            mock_settings.MINIMAX_API_KEY = "test-key"
            with patch("app.core.dingtalk_llm.RedisCache") as mock_cache:
                mock_cache.lpop = AsyncMock(return_value=None)
                with patch("app.core.dingtalk_llm._load_characters", return_value=[]):
                    result = await generate_dingtalk_via_m2her(sample_player_stats)
                    assert result is None
