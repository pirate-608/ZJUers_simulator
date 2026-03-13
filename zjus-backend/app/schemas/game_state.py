from typing import Any, Dict, List
from pydantic import BaseModel


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
    gpa: str = "0.0"
    highest_gpa: str = "0.0"
    reputation: int = 0
    course_plan_json: str = ""
    course_info_json: str = ""

    @classmethod
    def from_redis(cls, raw: Dict[str, Any]) -> "PlayerStats":
        raw = raw or {}
        return cls(
            username=_to_str(raw.get("username"), ""),
            major=_to_str(raw.get("major"), ""),
            major_abbr=_to_str(raw.get("major_abbr"), ""),
            semester=_to_str(raw.get("semester"), ""),
            semester_idx=_to_int(raw.get("semester_idx"), 1),
            semester_start_time=_to_int(raw.get("semester_start_time"), 0),
            energy=_to_int(raw.get("energy"), 0),
            sanity=_to_int(raw.get("sanity"), 0),
            stress=_to_int(raw.get("stress"), 0),
            iq=_to_int(raw.get("iq"), 0),
            eq=_to_int(raw.get("eq"), 0),
            luck=_to_int(raw.get("luck"), 0),
            gpa=_to_str(raw.get("gpa"), "0.0"),
            highest_gpa=_to_str(raw.get("highest_gpa"), "0.0"),
            reputation=_to_int(raw.get("reputation"), 0),
            course_plan_json=_to_str(raw.get("course_plan_json"), ""),
            course_info_json=_to_str(raw.get("course_info_json"), ""),
        )

    @classmethod
    def build_initial(cls, username: str = "", **overrides) -> "PlayerStats":
        """全局唯一的玩家初始状态工厂方法（Single Source of Truth）"""
        import random as _random
        import time as _time

        defaults = cls(
            username=username,
            major="",
            major_abbr="",
            semester="大一秋冬",
            semester_idx=1,
            semester_start_time=int(_time.time()),
            energy=100,
            sanity=80,
            stress=0,
            iq=0,
            eq=_random.randint(60, 90),
            luck=_random.randint(0, 100),
            gpa="0.0",
            highest_gpa="0.0",
            reputation=0,
            course_plan_json="",
            course_info_json="",
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
        if not self.iq or self.iq <= 0:
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
