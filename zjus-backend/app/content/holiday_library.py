"""Seasonal event-library fallback for nonblocking holiday generation.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
"""

import json
import logging
import random
from pathlib import Path
from typing import Literal

from app.content.event_library import _world_dir
from app.schemas.holiday import HolidayEvent

logger = logging.getLogger(__name__)


def load_holiday_library(path: Path | None = None) -> dict[str, list[HolidayEvent]]:
    """Validate the world file; callers can report invalid deployment data."""
    path = path or _world_dir() / "holiday_events.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("holiday_events.json must contain a list")
    result: dict[str, list[HolidayEvent]] = {"winter": [], "summer": []}
    seen: set[str] = set()
    for entry in raw:
        event = HolidayEvent.model_validate(entry)
        season = entry.get("season")
        if season not in result or not event.id or event.id in seen:
            raise ValueError("Holiday events need unique IDs and winter/summer seasons")
        seen.add(event.id)
        result[season].append(event)
    if not all(result.values()):
        raise ValueError("Both holiday seasons need at least one event")
    return result


def pick_holiday_event(season: Literal["winter", "summer"]) -> HolidayEvent:
    """Return a seasonal choice, or a neutral emergency fallback."""
    try:
        return random.choice(load_holiday_library()[season]).model_copy(deep=True)
    except Exception:
        logger.warning(
            "Holiday library unavailable; using a neutral fallback", exc_info=True
        )
        return HolidayEvent(
            title="返校前的小计划",
            desc="假期结束前，你整理着行李，也为下一段校园生活留下一点期待。",
            options=[
                {
                    "id": "A",
                    "text": "记下新学期的计划",
                    "effects": {"desc": "你把新的期待写进了日程本。"},
                },
                {
                    "id": "B",
                    "text": "和家人好好告别",
                    "effects": {"desc": "带着家人的叮嘱，你再次踏上返校的路。"},
                },
            ],
        )
