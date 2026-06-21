"""
PlayerStateVector — 将 30+ 字段的 player_stats 浓缩为 6 维语义标签

用途：
  1. 作为事件库检索的过滤条件
  2. 作为 LLM 补货时的精简上下文（~50 token vs ~300 token）
  3. 作为向量化角色检索的查询文本
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
    mood: str           # "高昂" | "正常" | "低落" | "崩溃"
    stress_level: str   # "轻松" | "适中" | "高压" | "爆表"
    academic: str       # "学霸" | "普通" | "挂科边缘"
    social: str         # "出众" | "普通" | "低调"
    semester: str       # e.g. "大一秋冬"
    major: str          # e.g. "计算机科学与技术"

    @classmethod
    def from_stats(cls, stats: Dict[str, Any]) -> "PlayerStateVector":
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
        return asdict(self)

    def to_prompt_fragment(self) -> str:
        """生成 ~50 token 的 LLM 上下文摘要"""
        return (
            f"{self.major}·{self.semester}｜"
            f"心态{self.mood}·压力{self.stress_level}·"
            f"学业{self.academic}·{stat_definitions.by_id['charm'].label}{self.social}"
        )

    def matches_tags(self, tags: list[str]) -> bool:
        """判断当前状态是否匹配事件的标签列表（任一命中即匹配）"""
        state_tags = {self.mood, self.stress_level, self.academic, self.social}
        return bool(state_tags & set(tags))
