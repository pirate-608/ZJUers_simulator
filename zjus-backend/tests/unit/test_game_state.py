"""
PlayerStats 单元测试

测试 build_initial / from_redis / get_repair_fields / model_dump 等核心方法。
纯同步，零外部依赖。
"""

import time
import pytest

from app.schemas.game_state import (
    PlayerStats,
    GameStateSnapshot,
    _to_int,
    _to_float,
    _to_str,
)


# ==========================================
# 辅助函数测试
# ==========================================


class TestTypeConversion:
    """测试 _to_int / _to_float / _to_str 边界场景"""

    def test_to_int_normal(self):
        assert _to_int(42) == 42
        assert _to_int("100") == 100

    def test_to_int_invalid(self):
        assert _to_int(None) == 0
        assert _to_int("abc", 99) == 99
        assert _to_int("", 5) == 5

    def test_to_float_normal(self):
        assert _to_float(3.14) == 3.14
        assert _to_float("2.5") == 2.5

    def test_to_float_invalid(self):
        assert _to_float(None, 1.0) == 1.0
        assert _to_float("xyz") == 0.0

    def test_to_str_normal(self):
        assert _to_str("hello") == "hello"
        assert _to_str(123) == "123"

    def test_to_str_none(self):
        assert _to_str(None) == ""
        assert _to_str(None, "fallback") == "fallback"


# ==========================================
# PlayerStats.build_initial 测试
# ==========================================


class TestBuildInitial:
    """测试全局唯一的初始状态工厂方法"""

    def test_returns_player_stats_instance(self):
        ps = PlayerStats.build_initial(username="Alice")
        assert isinstance(ps, PlayerStats)

    def test_username_set_correctly(self):
        ps = PlayerStats.build_initial(username="Bob")
        assert ps.username == "Bob"

    def test_default_field_values(self):
        ps = PlayerStats.build_initial(username="Test")
        assert ps.major == ""
        assert ps.major_abbr == ""
        assert ps.semester == "大一秋冬"
        assert ps.semester_idx == 1
        assert ps.energy == 100
        assert ps.sanity == 80
        assert ps.stress == 0
        assert ps.iq == 0
        assert ps.gpa == "0.0"
        assert ps.highest_gpa == "0.0"
        assert ps.reputation == 0
        assert ps.course_plan_json == ""
        assert ps.course_info_json == ""

    def test_random_fields_in_range(self):
        """eq 和 luck 是随机值，验证范围"""
        for _ in range(20):
            ps = PlayerStats.build_initial()
            assert 60 <= ps.eq <= 90, f"eq={ps.eq} out of range [60, 90]"
            assert 0 <= ps.luck <= 100, f"luck={ps.luck} out of range [0, 100]"

    def test_semester_start_time_is_recent(self):
        before = int(time.time())
        ps = PlayerStats.build_initial()
        after = int(time.time())
        assert before <= ps.semester_start_time <= after

    def test_overrides_work(self):
        ps = PlayerStats.build_initial(
            username="Override",
            energy=50,
            major="物理学",
            iq=120,
        )
        assert ps.username == "Override"
        assert ps.energy == 50
        assert ps.major == "物理学"
        assert ps.iq == 120
        # 非覆盖字段保持默认
        assert ps.sanity == 80
        assert ps.semester == "大一秋冬"

    def test_model_dump_contains_all_fields(self):
        """确保 model_dump 输出完整（Redis 写入依赖这个）"""
        ps = PlayerStats.build_initial(username="DumpTest")
        d = ps.model_dump()
        expected_keys = {
            "username", "major", "major_abbr", "semester", "semester_idx",
            "semester_start_time", "energy", "sanity", "stress", "iq", "eq",
            "luck", "gpa", "highest_gpa", "reputation", "course_plan_json",
            "course_info_json",
        }
        assert set(d.keys()) == expected_keys

    def test_two_calls_produce_independent_instances(self):
        ps1 = PlayerStats.build_initial(username="A")
        ps2 = PlayerStats.build_initial(username="B")
        assert ps1.username != ps2.username
        assert ps1 is not ps2


# ==========================================
# PlayerStats.from_redis 测试
# ==========================================


class TestFromRedis:
    """测试从 Redis hash 数据反序列化"""

    def test_normal_data(self, sample_player_stats):
        ps = PlayerStats.from_redis(sample_player_stats)
        assert ps.username == "TestPlayer"
        assert ps.major == "计算机科学与技术"
        assert ps.energy == 80
        assert ps.gpa == "3.5"

    def test_empty_dict(self):
        ps = PlayerStats.from_redis({})
        assert ps.username == ""
        assert ps.energy == 0
        assert ps.semester_idx == 1  # default

    def test_none_input(self):
        ps = PlayerStats.from_redis(None)
        assert ps.username == ""
        assert ps.energy == 0

    def test_string_numbers(self):
        """Redis 返回的值都是字符串，验证类型转换"""
        ps = PlayerStats.from_redis({
            "energy": "75",
            "sanity": "60",
            "semester_idx": "3",
            "gpa": "3.85",
        })
        assert ps.energy == 75
        assert ps.sanity == 60
        assert ps.semester_idx == 3
        assert ps.gpa == "3.85"

    def test_corrupted_data(self, sample_player_stats_corrupted):
        """损坏数据不应抛异常，应回退到默认值"""
        ps = PlayerStats.from_redis(sample_player_stats_corrupted)
        assert ps.username == "CorruptedPlayer"
        assert ps.energy == 0  # "not_a_number" → default 0
        assert ps.gpa == "0.0"  # None → _to_str(None, "0.0") → default "0.0"


# ==========================================
# PlayerStats.get_repair_fields 测试
# ==========================================


class TestGetRepairFields:
    """测试损坏数据修复逻辑"""

    def test_healthy_data_no_repairs(self, sample_player_stats):
        ps = PlayerStats.from_redis(sample_player_stats)
        repairs = ps.get_repair_fields()
        assert repairs == {}, f"Healthy data should need no repairs, got: {repairs}"

    def test_missing_semester_repaired(self):
        ps = PlayerStats(semester="", semester_idx=1, iq=90, semester_start_time=1)
        repairs = ps.get_repair_fields()
        assert repairs["semester"] == "大一秋冬"

    def test_invalid_semester_idx_repaired(self):
        ps = PlayerStats(semester="OK", semester_idx=0, iq=90, semester_start_time=1)
        repairs = ps.get_repair_fields()
        assert repairs["semester_idx"] == 1

    def test_missing_iq_repaired(self):
        ps = PlayerStats(semester="OK", semester_idx=1, iq=0, semester_start_time=1)
        repairs = ps.get_repair_fields()
        assert "iq" in repairs
        assert 80 <= repairs["iq"] <= 100

    def test_missing_semester_start_time_repaired(self):
        ps = PlayerStats(semester="OK", semester_idx=1, iq=90, semester_start_time=0)
        repairs = ps.get_repair_fields()
        assert "semester_start_time" in repairs
        assert repairs["semester_start_time"] > 0

    def test_multiple_fields_repaired_at_once(self):
        """多个字段同时损坏"""
        ps = PlayerStats(semester="", semester_idx=-1, iq=0, semester_start_time=0)
        repairs = ps.get_repair_fields()
        assert "semester" in repairs
        assert "semester_idx" in repairs
        assert "iq" in repairs
        assert "semester_start_time" in repairs


# ==========================================
# GameStateSnapshot 测试
# ==========================================


class TestGameStateSnapshot:
    """测试快照数据组装"""

    def test_from_redis_data_normal(self, sample_player_stats):
        snap = GameStateSnapshot.from_redis_data(
            stats_raw=sample_player_stats,
            courses_raw={"高等数学": "0.75", "线性代数": "0.3"},
            states_raw={"高等数学": "2", "线性代数": "1"},
            achievements_raw={"first_blood", "gpa_3"},
        )
        assert snap.stats.username == "TestPlayer"
        assert snap.courses["高等数学"] == 0.75
        assert snap.course_states["线性代数"] == 1
        assert "first_blood" in snap.achievements

    def test_from_redis_data_empty(self):
        snap = GameStateSnapshot.from_redis_data(
            stats_raw={},
            courses_raw=None,
            states_raw=None,
            achievements_raw=None,
        )
        assert snap.stats.username == ""
        assert snap.courses == {}
        assert snap.achievements == []
