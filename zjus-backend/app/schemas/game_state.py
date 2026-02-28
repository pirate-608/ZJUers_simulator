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
