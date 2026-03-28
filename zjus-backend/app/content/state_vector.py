"""
PlayerStateVector — 将 30+ 字段的 player_stats 浓缩为 5 维语义标签

用途：
  1. 作为事件库检索的过滤条件
  2. 作为 LLM 补货时的精简上下文（~50 token vs ~300 token）
  3. 作为向量化角色检索的查询文本
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any


@dataclass(frozen=True)
class PlayerStateVector:
    mood: str           # "高昂" | "正常" | "低落" | "崩溃"
    stress_level: str   # "轻松" | "适中" | "高压" | "爆表"
    academic: str       # "学霸" | "普通" | "挂科边缘"
    semester: str       # e.g. "大一秋冬"
    major: str          # e.g. "计算机科学与技术"

    @classmethod
    def from_stats(cls, stats: Dict[str, Any]) -> "PlayerStateVector":
        sanity = int(stats.get("sanity", 50))
        stress = int(stats.get("stress", 0))
        gpa = float(stats.get("gpa", 0) or 0)

        if sanity < 20:
            mood = "崩溃"
        elif sanity < 40:
            mood = "低落"
        elif sanity < 80:
            mood = "正常"
        else:
            mood = "高昂"

        if stress > 80:
            stress_level = "爆表"
        elif stress > 50:
            stress_level = "高压"
        elif stress > 20:
            stress_level = "适中"
        else:
            stress_level = "轻松"

        if gpa >= 3.8:
            academic = "学霸"
        elif 0 < gpa < 2.0:
            academic = "挂科边缘"
        else:
            academic = "普通"

        return cls(
            mood=mood,
            stress_level=stress_level,
            academic=academic,
            semester=str(stats.get("semester", "")),
            major=str(stats.get("major", "")),
        )

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)

    def to_prompt_fragment(self) -> str:
        """生成 ~50 token 的 LLM 上下文摘要"""
        return (
            f"{self.major}·{self.semester}｜"
            f"心态{self.mood}·压力{self.stress_level}·学业{self.academic}"
        )

    def matches_tags(self, tags: list[str]) -> bool:
        """判断当前状态是否匹配事件的标签列表（任一命中即匹配）"""
        state_tags = {self.mood, self.stress_level, self.academic}
        return bool(state_tags & set(tags))
