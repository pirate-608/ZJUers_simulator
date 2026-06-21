"""Precompiled event and CC98 library retrieval.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    Runtime selection avoids LLM calls by matching local JSON content against
    state ranges, tags, and recent event history.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.game.stat_definitions import stat_definitions

logger = logging.getLogger(__name__)

# ============================================================
# World data path resolution.
# ============================================================


def _world_dir() -> Path:
    """Prefer Docker's `/app/world`, then fall back to the local repo path."""
    docker_path = Path("/app/world")
    if docker_path.exists():
        return docker_path
    return Path(__file__).resolve().parent.parent.parent / "world"


# ============================================================
# Random event library.
# ============================================================

_event_library: List[Dict[str, Any]] = []


def _stat_default(stat_id: str) -> int:
    return stat_definitions.by_id[stat_id].default


def _stat_range(stat_id: str) -> list[int]:
    definition = stat_definitions.by_id[stat_id]
    return [definition.min, definition.max]


def _load_event_library() -> List[Dict[str, Any]]:
    global _event_library
    if _event_library:
        return _event_library
    path = _world_dir() / "event_library.json"
    if not path.exists():
        logger.warning("event_library.json not found at %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            _event_library = json.load(f)
        logger.info("Loaded %d events from event_library.json", len(_event_library))
    except Exception as e:
        logger.error("Failed to load event_library.json: %s", e)
    return _event_library


def pick_random_event(
    sanity: int | None = None,
    stress: int | None = None,
    seen_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick an unseen event from the precompiled library by player state range.

    The returned shape remains compatible with the LLM event payload and carries
    `id` for history-based deduplication:
    {"id": "evt_xxx", "title": ..., "desc": ..., "options": [...]}。
    """
    library = _load_event_library()
    if not library:
        return None

    sanity = _stat_default("sanity") if sanity is None else sanity
    stress = _stat_default("stress") if stress is None else stress
    seen = seen_ids or set()
    candidates = []
    for evt in library:
        if evt.get("id") in seen:
            continue
        sr = evt.get("sanity_range", _stat_range("sanity"))
        tr = evt.get("stress_range", _stat_range("stress"))
        if sr[0] <= sanity <= sr[1] and tr[0] <= stress <= tr[1]:
            candidates.append(evt)

    if not candidates:
        # Relax state matching before giving up, but still avoid seen events.
        candidates = [e for e in library if e.get("id") not in seen]

    if not candidates:
        return None

    chosen = random.choice(candidates)
    # Return the clean LLM-compatible shape and expose `id` for deduplication.
    return {
        "id": chosen.get("id"),
        "title": chosen["title"],
        "desc": chosen["desc"],
        "options": chosen["options"],
    }


# ============================================================
# CC98 post library.
# ============================================================

_cc98_library: List[Dict[str, Any]] = []


def _load_cc98_library() -> List[Dict[str, Any]]:
    global _cc98_library
    if _cc98_library:
        return _cc98_library
    path = _world_dir() / "cc98_library.json"
    if not path.exists():
        logger.warning("cc98_library.json not found at %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            _cc98_library = json.load(f)
        logger.info("Loaded %d posts from cc98_library.json", len(_cc98_library))
    except Exception as e:
        logger.error("Failed to load cc98_library.json: %s", e)
    return _cc98_library


def pick_cc98_post(
    effect: str = "neutral",
    trigger: str = "",
) -> Optional[str]:
    """
        Pick a CC98 post from the precompiled library by trigger and effect.

        Matching strategy:
            1) Filter by effect first.
            2) Prefer topic/content hits for the trigger.
            3) Fall back to a random effect-matched candidate.

    Returns:
        Post content, or None when the library is empty and LLM fallback should run.
    """
    library = _load_cc98_library()
    if not library:
        return None

    # Filter by effect before applying the optional trigger preference.
    candidates = [p for p in library if p.get("effect") == effect]
    if not candidates:
        candidates = library

    trigger_norm = (trigger or "").strip().lower()
    if trigger_norm:
        trigger_hits = []
        for post in candidates:
            topic = str(post.get("topic", "")).lower()
            content = str(post.get("content", "")).lower()
            # Match the literal trigger first, then retry after removing spaces.
            if (
                trigger_norm in topic
                or trigger_norm in content
                or trigger_norm.replace(" ", "") in topic.replace(" ", "")
                or trigger_norm.replace(" ", "") in content.replace(" ", "")
            ):
                trigger_hits.append(post)

        if trigger_hits:
            candidates = trigger_hits

    chosen = random.choice(candidates)
    return chosen.get("content", "CC98 帖子加载失败...")
