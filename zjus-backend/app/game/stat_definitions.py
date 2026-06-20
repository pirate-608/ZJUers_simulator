"""Game stat registry loaded from world/stat_definitions.json."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

PositiveEndpoint = Literal["max", "min", "none"]


class StatDefinition(BaseModel):
    id: str
    label: str
    icon: str = ""
    default: int = 0
    min: int = 0
    max: int = 200
    positive_endpoint: PositiveEndpoint = "max"
    allocatable: bool = False
    allow_item_effect: bool = False
    allow_event_effect: bool = False
    llm_context: bool = False
    show_in_character_create: bool = False
    show_in_hud: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        stat_id = value.strip()
        if not re.fullmatch(r"[a-z][a-z0-9_]*", stat_id):
            raise ValueError(f"invalid stat id: {value}")
        return stat_id

    @model_validator(mode="after")
    def validate_bounds(self) -> "StatDefinition":
        if self.min > self.max:
            raise ValueError(f"{self.id}: min cannot exceed max")
        if self.default < self.min or self.default > self.max:
            raise ValueError(f"{self.id}: default must be within min/max")
        if self.allocatable and not self.show_in_character_create:
            raise ValueError(
                f"{self.id}: allocatable stats must show in character create"
            )
        return self

    def clamp(self, value: Any) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = self.default
        return max(self.min, min(self.max, parsed))

    def public_meta(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "default": self.default,
            "min": self.min,
            "max": self.max,
            "positiveEndpoint": self.positive_endpoint,
            "allocatable": self.allocatable,
            "allowItemEffect": self.allow_item_effect,
            "allowEventEffect": self.allow_event_effect,
            "llmContext": self.llm_context,
            "showInCharacterCreate": self.show_in_character_create,
            "showInHud": self.show_in_hud,
        }


class StatDefinitionsConfig(BaseModel):
    version: str = "1.0.0"
    initial_budget: int = Field(default=300, ge=0)
    stats: list[StatDefinition]

    @model_validator(mode="after")
    def validate_stats(self) -> "StatDefinitionsConfig":
        ids = [stat.id for stat in self.stats]
        duplicates = sorted({stat_id for stat_id in ids if ids.count(stat_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate stat ids: {', '.join(duplicates)}")
        if not any(stat.allocatable for stat in self.stats):
            raise ValueError("at least one allocatable stat is required")
        defaults_total = sum(stat.default for stat in self.stats if stat.allocatable)
        if defaults_total != self.initial_budget:
            raise ValueError(
                "allocatable stat defaults must sum to initial_budget "
                f"({defaults_total} != {self.initial_budget})"
            )
        return self


class StatDefinitions:
    """Loads and exposes gameplay stat metadata."""

    _config: StatDefinitionsConfig | None = None
    _config_path: Path | None = None

    @staticmethod
    def resolve_config_path(config_path: str | Path | None = None) -> Path:
        if config_path is not None:
            return Path(config_path)
        candidates = [
            Path("world/stat_definitions.json"),
            Path("/app/world/stat_definitions.json"),
            Path(__file__).resolve().parent.parent.parent
            / "world"
            / "stat_definitions.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def __init__(self, config_path: str | Path | None = None):
        if self._config is None:
            self.load(config_path)
        elif config_path is not None:
            self.load(config_path)

    def load(self, config_path: str | Path | None = None) -> None:
        path = self.resolve_config_path(config_path)
        self._config_path = path
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
        self._config = StatDefinitionsConfig.model_validate(raw)
        logger.info(
            "Stat definitions loaded: version=%s stats=%s",
            self.version,
            len(self.stats),
        )

    def reload(self, config_path: str | Path | None = None) -> None:
        self._config = None
        self.load(config_path or self._config_path)

    @property
    def config(self) -> StatDefinitionsConfig:
        if self._config is None:
            self.load(self._config_path)
        assert self._config is not None
        return self._config

    @property
    def version(self) -> str:
        return self.config.version

    @property
    def initial_budget(self) -> int:
        return self.config.initial_budget

    @property
    def stats(self) -> list[StatDefinition]:
        return self.config.stats

    @property
    def by_id(self) -> dict[str, StatDefinition]:
        return {stat.id: stat for stat in self.stats}

    @property
    def allocatable(self) -> list[StatDefinition]:
        return [stat for stat in self.stats if stat.allocatable]

    @property
    def allocatable_ids(self) -> list[str]:
        return [stat.id for stat in self.allocatable]

    @property
    def numeric_stat_ids(self) -> set[str]:
        return {stat.id for stat in self.stats}

    @property
    def redis_int_fields(self) -> set[str]:
        initial_fields = {f"initial_{stat.id}" for stat in self.allocatable}
        return self.numeric_stat_ids | initial_fields

    @property
    def item_effect_fields(self) -> set[str]:
        return {stat.id for stat in self.stats if stat.allow_item_effect}

    @property
    def event_effect_fields(self) -> set[str]:
        return {stat.id for stat in self.stats if stat.allow_event_effect}

    @property
    def feedback_labels(self) -> dict[str, str]:
        return {stat.id: stat.label for stat in self.stats}

    def default_stats(self) -> dict[str, int]:
        return {stat.id: stat.default for stat in self.stats}

    def initial_default_stats(self) -> dict[str, int]:
        return {stat.id: stat.default for stat in self.allocatable}

    def initial_field_defaults(self) -> dict[str, int]:
        return {f"initial_{stat.id}": 0 for stat in self.allocatable}

    def public_metadata(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "initialBudget": self.initial_budget,
            "stats": [stat.public_meta() for stat in self.stats],
        }

    def coerce_stat(self, stat_id: str, value: Any, default: int | None = None) -> int:
        stat = self.by_id.get(stat_id)
        if stat is None:
            raise KeyError(f"unknown stat: {stat_id}")
        if default is not None:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                parsed = default
            return max(stat.min, min(stat.max, parsed))
        return stat.clamp(value)

    def normalize_initial_allocations(
        self,
        raw: dict[str, Any] | None,
        *,
        allow_missing: bool = False,
    ) -> dict[str, int]:
        source = raw or {}
        unknown = sorted(
            key for key in source if key not in self.allocatable_ids
        )
        if unknown:
            raise ValueError(f"不支持的初始属性：{', '.join(unknown)}")

        values: dict[str, int] = {}
        for stat in self.allocatable:
            if stat.id not in source:
                if not allow_missing:
                    raise ValueError(f"缺少初始属性：{stat.label}")
                values[stat.id] = stat.default
                continue
            try:
                parsed = int(source[stat.id])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{stat.label} 必须是整数") from exc
            if parsed < stat.min or parsed > stat.max:
                raise ValueError(f"{stat.label} 必须在 {stat.min} 到 {stat.max} 之间")
            values[stat.id] = parsed

        total = sum(values.values())
        if total != self.initial_budget:
            labels = "/".join(stat.label for stat in self.allocatable)
            raise ValueError(f"{labels} 初始总点数必须等于 {self.initial_budget}")
        return values


stat_definitions = StatDefinitions()
