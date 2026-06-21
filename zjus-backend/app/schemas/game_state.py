"""Pydantic snapshots for player state and Redis game data.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The models bridge Redis hash values, registry-driven defaults, and typed
payloads sent to the simulation engine.
"""

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


def _stat_default(stat_id: str) -> int:
    return stat_definitions.by_id[stat_id].default


class PlayerStats(BaseModel):
    """Registry-aware player stats with typed core fields.

    The model keeps high-traffic fields explicit for route and engine code while
    allowing extra stat-registry fields to round-trip through saves.
    """

    model_config = ConfigDict(extra="allow")

    username: str = ""
    major: str = ""
    major_abbr: str = ""
    semester: str = ""
    semester_idx: int = 1
    semester_start_time: int = 0
    energy: int = _stat_default("energy")
    sanity: int = _stat_default("sanity")
    stress: int = _stat_default("stress")
    iq: int = _stat_default("iq")
    eq: int = _stat_default("eq")
    luck: int = _stat_default("luck")
    charm: int = _stat_default("charm")
    gpa: str = "0.0"
    highest_gpa: str = "0.0"
    gpa_points_total: str = "0.0"
    gpa_credits_total: str = "0.0"
    reputation: int = _stat_default("reputation")
    efficiency: int = _stat_default("efficiency")
    gold: int = _stat_default("gold")
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
        """Convert Redis hash data into typed player stats.

        Args:
            raw: Stringly typed Redis hash values for the player.

        Returns:
            Player stats with defaults and registry-defined dynamic fields
            repaired into concrete Python values.
        """
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
            energy=_to_int(raw.get("energy"), defaults["energy"]),
            sanity=_to_int(raw.get("sanity"), defaults["sanity"]),
            stress=_to_int(raw.get("stress"), defaults["stress"]),
            iq=_to_int(raw.get("iq"), defaults["iq"]),
            eq=_to_int(raw.get("eq"), defaults["eq"]),
            luck=_to_int(raw.get("luck"), defaults["luck"]),
            charm=_to_int(raw.get("charm"), defaults["charm"]),
            gpa=_to_str(raw.get("gpa"), "0.0"),
            highest_gpa=_to_str(raw.get("highest_gpa"), "0.0"),
            gpa_points_total=_to_str(raw.get("gpa_points_total"), "0.0"),
            gpa_credits_total=_to_str(raw.get("gpa_credits_total"), "0.0"),
            reputation=_to_int(raw.get("reputation"), defaults["reputation"]),
            efficiency=_to_int(raw.get("efficiency"), defaults["efficiency"]),
            gold=_to_int(raw.get("gold"), defaults["gold"]),
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
        """Build the canonical initial player-stat snapshot.

        Args:
            username: Prompt-safe username to store with the new game.
            **overrides: Explicit field overrides applied after registry
                defaults are assembled.

        Returns:
            Initial player stats ready to persist into Redis.
        """
        import time as _time
        stat_defaults = stat_definitions.default_stats()
        initial_defaults = stat_definitions.initial_field_defaults()
        explicit_fields = set(cls.model_fields)
        extra_stats = {
            stat_id: value
            for stat_id, value in stat_defaults.items()
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
            energy=stat_defaults["energy"],
            sanity=stat_defaults["sanity"],
            stress=stat_defaults["stress"],
            iq=stat_defaults["iq"],
            eq=stat_defaults["eq"],
            luck=stat_defaults["luck"],
            charm=stat_defaults["charm"],
            gpa="0.0",
            highest_gpa="0.0",
            gpa_points_total="0.0",
            gpa_credits_total="0.0",
            reputation=stat_defaults["reputation"],
            efficiency=stat_defaults["efficiency"],
            gold=stat_defaults["gold"],
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
        """Return missing or invalid fields that should be repaired in Redis.

        Returns:
            Mapping of field names to repaired values. The caller decides when
            to persist the patch so read paths can remain side-effect aware.
        """
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
    """Typed aggregate snapshot of the active Redis game state."""

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
        """Create a full game snapshot from independent Redis structures.

        Args:
            stats_raw: Player stat hash.
            courses_raw: Course mastery hash.
            states_raw: Course state hash.
            achievements_raw: Redis set/list of achievement codes.

        Returns:
            A typed snapshot used by services and the simulation engine.
        """
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
