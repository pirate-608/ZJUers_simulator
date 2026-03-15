"""
GameBalance 单元测试

测试配置加载、属性读取、默认值回退、热重载。
使用 tmp_path 创建临时 JSON，不依赖真实 game_balance.json。
"""

import json
import pytest
from app.game.balance import GameBalance


# ==========================================
# 重置单例（每个测试独立）
# ==========================================

@pytest.fixture(autouse=True)
def reset_singleton():
    """每个测试前重置 GameBalance 单例，避免状态泄漏"""
    GameBalance._instance = None
    GameBalance._config = {}
    yield
    GameBalance._instance = None
    GameBalance._config = {}


# ==========================================
# 配置加载
# ==========================================


class TestConfigLoading:
    """测试配置文件加载"""

    def test_load_valid_config(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert gb.version == "1.0-test"

    def test_load_nonexistent_file_raises(self):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        with pytest.raises(FileNotFoundError):
            gb.load("/nonexistent/path/game_balance.json")

    def test_load_invalid_json_raises(self, tmp_path):
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{invalid json", encoding="utf-8")
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        with pytest.raises(Exception):
            gb.load(str(bad_file))

    def test_reload_updates_config(self, tmp_path):
        # 第一次加载
        config_v1 = {"version": "1.0", "tick": {"interval_seconds": 3}}
        path = tmp_path / "game_balance.json"
        path.write_text(json.dumps(config_v1), encoding="utf-8")
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(str(path))
        assert gb.version == "1.0"

        # 更新文件后热重载
        config_v2 = {"version": "2.0", "tick": {"interval_seconds": 5}}
        path.write_text(json.dumps(config_v2), encoding="utf-8")
        gb.reload(str(path))
        assert gb.version == "2.0"
        assert gb.tick_interval == 5


# ==========================================
# Tick 配置
# ==========================================


class TestTickConfig:
    """测试 Tick 相关属性"""

    def test_tick_interval(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert gb.tick_interval == 3

    def test_base_energy_drain(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert gb.base_energy_drain == 0.8

    def test_base_mastery_growth(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert gb.base_mastery_growth == 0.5

    def test_defaults_when_tick_missing(self, tmp_path):
        """tick 配置缺失时使用默认值"""
        path = tmp_path / "game_balance.json"
        path.write_text('{"version": "empty"}', encoding="utf-8")
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(str(path))
        assert gb.tick_interval == 3  # default
        assert gb.base_energy_drain == 0.8  # default


# ==========================================
# 学期配置
# ==========================================


class TestSemesterConfig:
    """测试学期相关配置读取"""

    def test_specific_semester_duration(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert gb.get_semester_duration(1) == 300
        assert gb.get_semester_duration(2) == 350

    def test_default_semester_duration(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        # 学期 5 没有特殊配置，应该走默认值
        assert gb.get_semester_duration(5) == 360

    def test_speed_modes(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        modes = gb.speed_modes
        assert "1.0" in modes
        assert "2.0" in modes
        assert modes["2.0"]["multiplier"] == 2.0


# ==========================================
# 课程状态配置
# ==========================================


class TestCourseStatesConfig:
    """测试课程状态系数（摆/摸/卷）"""

    def test_course_states_loaded(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        states = gb.course_states
        assert "0" in states  # 摆烂
        assert "1" in states  # 摸鱼
        assert "2" in states  # 内卷

    def test_course_state_coeffs_int_keys(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        coeffs = gb.get_course_state_coeffs()
        assert 0 in coeffs
        assert 1 in coeffs
        assert 2 in coeffs
        assert coeffs[2]["growth_multiplier"] == 1.5

    def test_raw_config_accessible(self, sample_balance_config):
        gb = GameBalance.__new__(GameBalance)
        gb._config = {}
        gb.load(sample_balance_config)
        assert isinstance(gb.raw, dict)
        assert "version" in gb.raw
