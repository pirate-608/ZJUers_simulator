"""
公共 pytest fixtures

所有 fixture 在此集中定义，测试文件自动可用。
核心策略：mock 所有外部依赖（Redis / DB / httpx），测试不需要任何运行中的服务。
"""

import os
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

# ==========================================
# 环境变量 — 在导入 app 代码前设置
# 防止 Settings 验证器因缺少配置而报错
# ==========================================

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("ADMIN_SESSION_SECRET", "test-admin-session-secret")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")
os.environ.setdefault("ENVIRONMENT", "development")


# ==========================================
# 基础数据 fixtures
# ==========================================

@pytest.fixture
def sample_player_stats():
    """标准玩家状态数据，可用于各种测试场景"""
    return {
        "username": "TestPlayer",
        "major": "计算机科学与技术",
        "major_abbr": "CS",
        "semester": "大一秋冬",
        "semester_idx": 1,
        "semester_start_time": 1700000000,
        "energy": 80,
        "sanity": 60,
        "stress": 30,
        "iq": 90,
        "eq": 75,
        "luck": 50,
        "gpa": "3.5",
        "highest_gpa": "3.8",
        "reputation": 10,
        "course_plan_json": "",
        "course_info_json": "",
    }


@pytest.fixture
def sample_player_stats_low_sanity(sample_player_stats):
    """心态低落的玩家状态"""
    return {**sample_player_stats, "sanity": 20, "stress": 85}


@pytest.fixture
def sample_player_stats_corrupted():
    """损坏/缺失字段的玩家状态（用于测试 repair 逻辑）"""
    return {
        "username": "CorruptedPlayer",
        "energy": "not_a_number",
        "gpa": None,
        # 其他字段全部缺失
    }


@pytest.fixture
def sample_character():
    """单个 characters.json 角色条目"""
    return {
        "name": "【室友】",
        "role": "roommate",
        "content": "你是浙江大学某学生的室友，平时会和他/她一起生活、学习和娱乐。",
        "examples": [
            "你早上出门忘关空调了！",
            "steam冬促又开始了，你赶紧买几款！",
            "昨晚你又熬夜打游戏了？",
        ],
    }


@pytest.fixture
def sample_characters_list(sample_character):
    """多个角色列表"""
    return [
        sample_character,
        {
            "name": "【辅导员】",
            "role": "counselor",
            "content": "你是浙江大学的本科生辅导员",
            "examples": ["各位同学好，近期天气转凉，请注意保暖。"],
        },
        {
            "name": "【学习委员】",
            "role": "classmate",
            "content": "你是浙江大学某班级的学习委员",
            "examples": ["大家有没有高数的期末复习资料？"],
        },
    ]


# ==========================================
# GameBalance fixture
# ==========================================

@pytest.fixture
def sample_balance_config(tmp_path):
    """创建临时的 game_balance.json 并返回路径"""
    config = {
        "version": "1.0-test",
        "tick": {
            "interval_seconds": 3,
            "base_energy_drain": 0.8,
            "base_mastery_growth": 0.5,
        },
        "semester": {
            "default_duration_seconds": 360,
            "duration_by_index": {"1": 300, "2": 350},
            "speed_modes": {
                "1.0": {"label": "正常速度", "multiplier": 1.0},
                "2.0": {"label": "二倍速", "multiplier": 2.0},
            },
        },
        "course_states": {
            "0": {"label": "摆烂", "growth_multiplier": 0.1, "drain_multiplier": 0.2},
            "1": {"label": "摸鱼", "growth_multiplier": 0.5, "drain_multiplier": 0.5},
            "2": {"label": "内卷", "growth_multiplier": 1.5, "drain_multiplier": 1.2},
        },
        "relax_actions": {
            "gym": {"energy": 15, "sanity": 5, "stress": -10, "cooldown": 60},
            "game": {"energy": -5, "sanity": 10, "stress": -15, "cooldown": 30},
        },
        "events": {
            "random_event_interval": 120,
            "dingtalk_interval": 90,
        },
        "exam": {
            "gpa_base": 2.0,
            "mastery_weight": 0.6,
        },
        "game_over": {
            "sanity_threshold": 0,
            "energy_threshold": 0,
        },
    }
    config_path = tmp_path / "game_balance.json"
    config_path.write_text(json.dumps(config, ensure_ascii=False), encoding="utf-8")
    return str(config_path)


# ==========================================
# Mock Redis fixture
# ==========================================

@pytest.fixture
def mock_redis_cache():
    """Mock RedisCache，用字典模拟 Redis 操作"""
    store = {}

    async def _lpop(key):
        items = store.get(key, [])
        return items.pop(0) if items else None

    async def _rpush_many_with_limit(key, values, max_len=None, ttl_seconds=None):
        if key not in store:
            store[key] = []
        store[key].extend(values)
        if max_len:
            store[key] = store[key][-max_len:]

    with patch("app.api.cache.RedisCache") as mock:
        mock.lpop = AsyncMock(side_effect=_lpop)
        mock.rpush_many_with_limit = AsyncMock(side_effect=_rpush_many_with_limit)
        mock._store = store  # 暴露内部存储供断言使用
        yield mock
