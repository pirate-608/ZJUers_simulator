"""Compact player state into semantic tags for content retrieval.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    The vector is used as an event-library filter, a compact LLM context, and a
    query text seed for role retrieval.
"""

from dataclasses import asdict, dataclass
from typing import Any, Dict

from app.game.stat_definitions import stat_definitions


def _stat_value(stats: Dict[str, Any], stat_id: str) -> int:
    definition = stat_definitions.by_id[stat_id]
    try:
        return int(stats.get(stat_id, definition.default))
    except (TypeError, ValueError):
        return definition.default


def _stat_ratio(value: int, stat_id: str) -> float:
    definition = stat_definitions.by_id[stat_id]
    span = definition.max - definition.min
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (value - definition.min) / span))


@dataclass(frozen=True)
class PlayerStateVector:
    """Categorical state summary for retrieval and prompt context."""

    mood: str
    stress_level: str
    academic: str
    social: str
    semester: str
    major: str

    @classmethod
    def from_stats(cls, stats: Dict[str, Any]) -> "PlayerStateVector":
        """Build a categorical vector from raw or effective player stats."""
        sanity = _stat_value(stats, "sanity")
        stress = _stat_value(stats, "stress")
        gpa = float(stats.get("gpa", 0) or 0)
        charm = _stat_value(stats, "charm")
        sanity_ratio = _stat_ratio(sanity, "sanity")
        stress_ratio = _stat_ratio(stress, "stress")
        charm_ratio = _stat_ratio(charm, "charm")

        if sanity_ratio < 0.1:
            mood = "崩溃"
        elif sanity_ratio < 0.2:
            mood = "低落"
        elif sanity_ratio < 0.4:
            mood = "正常"
        else:
            mood = "高昂"

        if stress_ratio > 0.4:
            stress_level = "爆表"
        elif stress_ratio > 0.25:
            stress_level = "高压"
        elif stress_ratio > 0.1:
            stress_level = "适中"
        else:
            stress_level = "轻松"

        if gpa >= 3.8:
            academic = "学霸"
        elif 0 < gpa < 2.0:
            academic = "挂科边缘"
        else:
            academic = "普通"

        if charm_ratio >= 0.6:
            social = "出众"
        elif charm_ratio < 0.2:
            social = "低调"
        else:
            social = "普通"

        return cls(
            mood=mood,
            stress_level=stress_level,
            academic=academic,
            social=social,
            semester=str(stats.get("semester", "")),
            major=str(stats.get("major", "")),
        )

    def to_dict(self) -> Dict[str, str]:
        """Return the vector as a plain dictionary."""
        return asdict(self)

    def to_prompt_fragment(self) -> str:
        """Return a compact prompt fragment for LLM content generation."""
        return (
            f"{self.major}·{self.semester}｜"
            f"心态{self.mood}·压力{self.stress_level}·"
            f"学业{self.academic}·{stat_definitions.by_id['charm'].label}{self.social}"
        )

    def matches_tags(self, tags: list[str]) -> bool:
        """Return whether any event tag matches the current state vector."""
        state_tags = {self.mood, self.stress_level, self.academic, self.social}
        return bool(state_tags & set(tags))
