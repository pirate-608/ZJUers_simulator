"""Validated holiday events and resumable per-semester delivery state.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
"""

import json
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.game.stat_definitions import stat_definitions

HOLIDAY_EFFECT_LIMIT = 10


class HolidayOption(BaseModel):
    """One holiday choice using the ordinary event effect contract."""

    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    effects: dict[str, Any]

    @field_validator("effects")
    @classmethod
    def validate_effects(cls, effects: dict[str, Any]) -> dict[str, Any]:
        for field, value in effects.items():
            if field == "desc" and isinstance(value, str):
                continue
            if field not in stat_definitions.event_effect_fields:
                raise ValueError(f"Unsupported holiday effect: {field}")
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or abs(value) > HOLIDAY_EFFECT_LIMIT
            ):
                raise ValueError(
                    f"Holiday effects must be integers in "
                    f"[-{HOLIDAY_EFFECT_LIMIT}, {HOLIDAY_EFFECT_LIMIT}]: {field}"
                )
        return effects


class HolidayEvent(BaseModel):
    """An event that can be displayed by the existing random-event modal."""

    id: str = ""
    kind: Literal["holiday"] = "holiday"
    semester_idx: int = 0
    title: str = Field(min_length=1)
    desc: str = Field(min_length=1)
    options: list[HolidayOption] = Field(min_length=2, max_length=4)

    @field_validator("options")
    @classmethod
    def unique_options(cls, options: list[HolidayOption]) -> list[HolidayOption]:
        if len({option.id for option in options}) != len(options):
            raise ValueError("Holiday option IDs must be unique")
        return options


class HolidayState(BaseModel):
    """Persisted delivery state; generation tasks themselves are session-local."""

    semester_idx: int = 0
    token: str = ""
    season: Literal["winter", "summer"] = "winter"
    status: Literal["none", "pending", "ready", "resolved"] = "none"
    event: HolidayEvent | None = None

    @classmethod
    def pending(cls, semester_idx: int) -> "HolidayState":
        return cls(
            semester_idx=semester_idx,
            token=f"holiday_{semester_idx}_{uuid4().hex[:12]}",
            season="winter" if semester_idx % 2 == 0 else "summer",
            status="pending",
        )

    @classmethod
    def from_raw(cls, raw: Any) -> "HolidayState":
        """Read old or malformed save metadata without breaking game startup."""
        if isinstance(raw, cls):
            return raw.model_copy(deep=True)
        try:
            if isinstance(raw, (str, bytes)):
                raw = json.loads(raw)
            return cls.model_validate(raw) if isinstance(raw, dict) else cls()
        except (ValueError, TypeError, ValidationError):
            return cls()
