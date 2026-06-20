from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict

from app.game.stat_definitions import stat_definitions


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


class PlayerStats(BaseModel):
    model_config = ConfigDict(extra="allow")

    username: str = ""
    major: str = ""
    major_abbr: str = ""
    semester: str = ""
    semester_idx: int = 1
    semester_start_time: int = 0
    energy: int = 0
    sanity: int = 0
    stress: int = 0
    iq: int = 0
    eq: int = 0
    luck: int = 0
    charm: int = 0
    gpa: str = "0.0"
    highest_gpa: str = "0.0"
    gpa_points_total: str = "0.0"
    gpa_credits_total: str = "0.0"
    reputation: int = 0
    efficiency: int = 100
    gold: int = 0
    initial_major_abbr: str = ""
    initial_iq: int = 0
    initial_eq: int = 0
    initial_luck: int = 0
    initial_charm: int = 0
    course_plan_json: str = ""
    course_info_json: str = ""
    elapsed_game_time: int = 0
    exam_completed: int = 0

    @classmethod
    def from_redis(cls, raw: Dict[str, Any]) -> "PlayerStats":
        raw = raw or {}
        defaults = stat_definitions.default_stats()
        initial_defaults = stat_definitions.initial_field_defaults()
        explicit_fields = set(cls.model_fields)
        extra_stats = {
            stat_id: _to_int(raw.get(stat_id), default)
            for stat_id, default in defaults.items()
            if stat_id not in explicit_fields
        }
        extra_stats.update(
            {
                field: _to_int(raw.get(field), default)
                for field, default in initial_defaults.items()
                if field not in explicit_fields
            }
        )
        return cls(
            username=_to_str(raw.get("username"), ""),
            major=_to_str(raw.get("major"), ""),
            major_abbr=_to_str(raw.get("major_abbr"), ""),
            semester=_to_str(raw.get("semester"), ""),
            semester_idx=_to_int(raw.get("semester_idx"), 1),
            semester_start_time=_to_int(raw.get("semester_start_time"), 0),
            energy=_to_int(raw.get("energy"), defaults.get("energy", 0)),
            sanity=_to_int(raw.get("sanity"), defaults.get("sanity", 0)),
            stress=_to_int(raw.get("stress"), defaults.get("stress", 0)),
            iq=_to_int(raw.get("iq"), defaults.get("iq", 0)),
            eq=_to_int(raw.get("eq"), defaults.get("eq", 0)),
            luck=_to_int(raw.get("luck"), defaults.get("luck", 0)),
            charm=_to_int(raw.get("charm"), defaults.get("charm", 50)),
            gpa=_to_str(raw.get("gpa"), "0.0"),
            highest_gpa=_to_str(raw.get("highest_gpa"), "0.0"),
            gpa_points_total=_to_str(raw.get("gpa_points_total"), "0.0"),
            gpa_credits_total=_to_str(raw.get("gpa_credits_total"), "0.0"),
            reputation=_to_int(raw.get("reputation"), 0),
            efficiency=_to_int(raw.get("efficiency"), 100),
            gold=_to_int(raw.get("gold"), 0),
            initial_major_abbr=_to_str(raw.get("initial_major_abbr"), ""),
            initial_iq=_to_int(
                raw.get("initial_iq"), initial_defaults.get("initial_iq", 0)
            ),
            initial_eq=_to_int(
                raw.get("initial_eq"), initial_defaults.get("initial_eq", 0)
            ),
            initial_luck=_to_int(
                raw.get("initial_luck"), initial_defaults.get("initial_luck", 0)
            ),
            initial_charm=_to_int(
                raw.get("initial_charm"), initial_defaults.get("initial_charm", 0)
            ),
            course_plan_json=_to_str(raw.get("course_plan_json"), ""),
            course_info_json=_to_str(raw.get("course_info_json"), ""),
            elapsed_game_time=_to_int(raw.get("elapsed_game_time"), 0),
            exam_completed=_to_int(raw.get("exam_completed"), 0),
            **extra_stats,
        )

    @classmethod
    def build_initial(cls, username: str = "", **overrides) -> "PlayerStats":
        """全局唯一的玩家初始状态工厂方法（Single Source of Truth）"""
        import time as _time
        defaults = stat_definitions.default_stats()
        initial_defaults = stat_definitions.initial_field_defaults()
        explicit_fields = set(cls.model_fields)
        extra_stats = {
            stat_id: value
            for stat_id, value in defaults.items()
            if stat_id not in explicit_fields
        }
        extra_stats.update(
            {
                field: value
                for field, value in initial_defaults.items()
                if field not in explicit_fields
            }
        )

        defaults = cls(
            username=username,
            major="",
            major_abbr="",
            semester="大一秋冬",
            semester_idx=1,
            semester_start_time=int(_time.time()),
            energy=defaults.get("energy", 100),
            sanity=defaults.get("sanity", 80),
            stress=defaults.get("stress", 0),
            iq=defaults.get("iq", 100),
            eq=defaults.get("eq", 100),
            luck=defaults.get("luck", 50),
            charm=defaults.get("charm", 50),
            gpa="0.0",
            highest_gpa="0.0",
            gpa_points_total="0.0",
            gpa_credits_total="0.0",
            reputation=0,
            efficiency=100,
            gold=0,
            initial_major_abbr="",
            initial_iq=0,
            initial_eq=0,
            initial_luck=0,
            initial_charm=0,
            course_plan_json="",
            course_info_json="",
            exam_completed=0,
            **extra_stats,
        )
        if overrides:
            defaults = defaults.model_copy(update=overrides)
        return defaults

    def get_repair_fields(self) -> Dict[str, Any]:
        """返回需要修复的字段字典（用于补全缺失/异常数据）"""
        import random as _random
        import time as _time

        repairs: Dict[str, Any] = {}
        if not self.semester:
            repairs["semester"] = "大一秋冬"
        if not self.semester_idx or self.semester_idx <= 0:
            repairs["semester_idx"] = 1
        if not self.semester_start_time:
            repairs["semester_start_time"] = int(_time.time())
        for stat in stat_definitions.allocatable:
            value = getattr(self, stat.id, None)
            if value is None or value <= 0:
                repairs[stat.id] = stat.default
        iq_definition = stat_definitions.by_id.get("iq")
        if iq_definition and repairs.get("iq") == iq_definition.default:
            repairs["iq"] = _random.randint(80, 100)
        return repairs


class GameStateSnapshot(BaseModel):
    stats: PlayerStats
    courses: Dict[str, float]
    course_states: Dict[str, int]
    achievements: List[str]

    @classmethod
    def from_redis_data(
        cls,
        stats_raw: Dict[str, Any],
        courses_raw: Dict[str, Any],
        states_raw: Dict[str, Any],
        achievements_raw: Any,
    ) -> "GameStateSnapshot":
        stats = PlayerStats.from_redis(stats_raw)
        courses = {str(k): _to_float(v, 0.0) for k, v in (courses_raw or {}).items()}
        course_states = {str(k): _to_int(v, 1) for k, v in (states_raw or {}).items()}
        achievements = list(achievements_raw) if achievements_raw else []
        return cls(
            stats=stats,
            courses=courses,
            course_states=course_states,
            achievements=achievements,
        )
