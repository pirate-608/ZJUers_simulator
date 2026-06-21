"""Real-time game simulation engine.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
`GameEngine` owns the per-player tick loop, actions, exams, random events,
DingTalk conversations, item effects, saves, graduation, and Game Over flow.
"""

import asyncio
import hashlib
import json
import logging
import math
import random
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Literal, Optional

from sqlalchemy import update

from app.content.event_library import pick_cc98_post, pick_random_event
from app.core.database import AsyncSessionLocal
from app.core.events import GameEvent
from app.core.input_safety import safe_username_for_prompt
from app.core.llm import (
    generate_cc98_post,
    generate_dingtalk_message,
    generate_dingtalk_message_for_character,
    generate_dingtalk_reply_message,
    generate_random_event,
)
from app.game.balance import balance
from app.game.items import items
from app.game.stat_definitions import stat_definitions
from app.models.user import User
from app.repositories.redis_repo import RedisRepository
from app.schemas.dingtalk import (
    DingTalkContact,
    DingTalkMessage,
    DingTalkReplyOption,
    DingTalkRoundState,
    build_contact_id,
    is_replyable_role,
    new_message_id,
    normalize_dingtalk_role,
    now_ts,
)
from app.services.game_service import GameService
from app.services.save_service import SaveService

logger = logging.getLogger(__name__)


class GameMode:
    """Content-generation mode identifiers accepted by the running engine."""

    LIBRARY = "library"
    AI = "ai"
    HYBRID = "hybrid"

    @classmethod
    def from_str(cls, s: str):
        """Normalize a client-provided mode string into a supported mode."""
        s = s.lower()
        if s == "ai":
            return cls.AI
        if s == "library":
            return cls.LIBRARY
        return cls.HYBRID


class GameEngine:
    """Per-player real-time simulation loop.

    The engine deliberately owns WebSocket-facing side effects: it reads Redis
    state, applies actions, emits UI events, and tracks background content tasks
    so slow LLM calls do not block the receive loop.
    """

    # Fallback bounds for legacy or unknown stat fields. Registered gameplay
    # stats use `world/stat_definitions.json`; these 0-200 bounds preserve the
    # historical player-stat range when old saves or external effects contain a
    # field not yet present in the registry.
    _BASE_STAT_MIN = 0
    _BASE_STAT_MAX = 200

    # Relax overflow turns wasted positive feedback into useful but capped
    # benefits. Energy is most visible to moment-to-moment play, sanity is the
    # next recovery target, and charm is intentionally capped at +1 to avoid a
    # single relax action becoming the main charm-growth path.
    _RELAX_OVERFLOW_TARGETS = ("energy", "sanity", "charm")
    _RELAX_OVERFLOW_TRANSFER_CAP = 20
    _RELAX_CHARM_TRANSFER_CAP = 1
    _FEEDBACK_FIELD_LABELS = {
        **stat_definitions.feedback_labels,
        "gpa": "GPA",
    }

    @classmethod
    def _stat_bounds(cls, field: str) -> tuple[int, int]:
        """Return registry bounds for a stat, with a safe legacy fallback."""
        definition = stat_definitions.by_id.get(field)
        if definition is None:
            return cls._BASE_STAT_MIN, cls._BASE_STAT_MAX
        return definition.min, definition.max

    @staticmethod
    def _stat_default(field: str, fallback: int = 0) -> int:
        """Return the registry default for a stat if it exists."""
        definition = stat_definitions.by_id.get(field)
        return definition.default if definition else fallback

    async def emit(self, event_type: str, data: dict, msg: str | None = None):
        """Queue a WebSocket event for the connection manager.

        Args:
            event_type: Server-to-client event type.
            data: Payload already shaped for the frontend store.
            msg: Optional legacy log text emitted as a normal event first.
        """
        if msg:
            await self.event_queue.put(
                GameEvent(
                    user_id=self.user_id,
                    event_type="event",
                    data={"data": {"desc": msg}},
                )
            )
        await self.event_queue.put(
            GameEvent(user_id=self.user_id, event_type=event_type, data=data)
        )

    async def _emit_feedback(
        self,
        title: str,
        message: str,
        kind: str = "info",
        auto_close_ms: int = 3000,
        changes: list[dict[str, Any]] | None = None,
    ):
        """Emit a user-facing feedback popup."""
        payload: dict[str, Any] = {
            "title": title,
            "message": message,
            "kind": kind,
            "auto_close_ms": auto_close_ms,
        }
        if changes:
            payload["changes"] = changes
        await self.emit(
            "feedback",
            {"data": payload},
        )

    def _feedback_change(
        self,
        field: str,
        delta: int | float,
        value: int | float | None = None,
    ) -> dict[str, Any]:
        """Format one numeric delta for feedback modals."""
        change: dict[str, Any] = {
            "field": field,
            "label": self._FEEDBACK_FIELD_LABELS.get(field, field),
            "delta": delta,
        }
        if value is not None:
            change["value"] = value
        return change

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _calculate_cumulative_gpa(
        cls,
        stats: dict[str, Any],
        term_points: float,
        term_credits: float,
        term_gpa: float,
    ) -> tuple[float, float, float]:
        """Return cumulative GPA and updated weighted totals.

        New saves keep exact weighted totals. Older saves only have the last
        visible GPA, so fall back to treating it as the prior cumulative GPA
        across the completed terms. That is approximate for very old saves but
        avoids resetting CGPA to the current semester after this upgrade.
        """
        previous_points = cls._safe_float(stats.get("gpa_points_total"))
        previous_credits = cls._safe_float(stats.get("gpa_credits_total"))

        if previous_credits <= 0 and term_credits > 0:
            previous_gpa = cls._safe_float(stats.get("gpa"))
            completed_terms = max(0, cls._safe_int(stats.get("semester_idx"), 1) - 1)
            if previous_gpa > 0 and completed_terms > 0:
                previous_credits = term_credits * completed_terms
                previous_points = previous_gpa * previous_credits

        cumulative_points = previous_points + term_points
        cumulative_credits = previous_credits + term_credits
        if cumulative_credits <= 0:
            return term_gpa, cumulative_points, cumulative_credits
        cumulative_gpa = round(cumulative_points / cumulative_credits, 2)
        return cumulative_gpa, cumulative_points, cumulative_credits

    async def _apply_stat_delta_for_feedback(
        self,
        field: str,
        delta: int,
    ) -> dict[str, Any] | None:
        """Apply a stat delta and return a feedback entry if it changed."""
        if delta == 0:
            return None
        new_value = await self.repo.update_stat_safe(field, delta)
        return self._feedback_change(field, delta, new_value)

    def _positive_relax_overflow_units(
        self,
        field: str,
        requested_delta: int,
        actual_delta: int,
    ) -> int:
        """Calculate relax-only benefit lost to a stat's good endpoint."""
        if field == "stress" and requested_delta < 0:
            return max(0, abs(requested_delta) - max(0, -actual_delta))
        positive_fields = {
            stat.id
            for stat in stat_definitions.stats
            if stat.positive_endpoint == "max"
        }
        if field in positive_fields:
            if requested_delta > 0:
                return max(0, requested_delta - max(0, actual_delta))
        return 0

    async def _apply_relax_delta(
        self,
        field: str,
        delta: int,
        base_stats: dict[str, Any],
        changes: list[dict[str, Any]],
    ) -> int:
        """Apply a relax effect and return overflow units for redistribution."""
        if delta == 0:
            return 0
        current_value = self._safe_int(base_stats.get(field))
        min_value, max_value = self._stat_bounds(field)
        new_value = await self.repo.update_stat_safe(field, delta, min_value, max_value)
        actual_delta = int(new_value) - current_value
        base_stats[field] = int(new_value)
        if actual_delta:
            changes.append(self._feedback_change(field, actual_delta, int(new_value)))
        return self._positive_relax_overflow_units(field, delta, actual_delta)

    async def _transfer_relax_overflow(
        self,
        overflow_units: int,
        base_stats: dict[str, Any],
        changes: list[dict[str, Any]],
    ) -> None:
        """Redistribute relax-only overflow to still-useful positive stats."""
        remaining = min(max(0, overflow_units), self._RELAX_OVERFLOW_TRANSFER_CAP)
        charm_transferred = 0
        for field in self._RELAX_OVERFLOW_TARGETS:
            if remaining <= 0:
                break
            current_value = self._safe_int(base_stats.get(field))
            min_value, max_value = self._stat_bounds(field)
            room = max(0, max_value - current_value)
            if room <= 0:
                continue
            field_cap = remaining
            if field == "charm":
                field_cap = min(
                    field_cap,
                    max(0, self._RELAX_CHARM_TRANSFER_CAP - charm_transferred),
                )
            delta = min(remaining, room, field_cap)
            if delta <= 0:
                continue
            new_value = await self.repo.update_stat_safe(
                field,
                delta,
                min_value,
                max_value,
            )
            actual_delta = int(new_value) - current_value
            base_stats[field] = int(new_value)
            if actual_delta <= 0:
                continue
            if field == "charm":
                charm_transferred += actual_delta
            remaining -= actual_delta
            changes.append(self._feedback_change(field, actual_delta, int(new_value)))

    async def _get_items_state_payload(self) -> dict[str, Any]:
        """Build the item-state payload expected by the frontend."""
        return items.state_payload(await self.repo.get_items_state())

    async def _effective_stats(self, stats: dict[str, Any]) -> dict[str, Any]:
        """Return stats with passive item bonuses applied for reads only."""
        return items.apply_bonuses_to_stats(stats, await self.repo.get_items_state())

    async def _push_items_state(self):
        """Push the latest item catalog, backpack, and passive bonuses."""
        await self.emit(
            "items_state",
            {"data": await self._get_items_state_payload()},
        )

    def resume(self):
        """Resume ticking and notify the frontend."""
        if not self.is_running:
            self.start()
            asyncio.create_task(self._push_update())
            asyncio.create_task(self.emit("resumed", {"msg": "游戏已继续。"}))

    def pause(self):
        """Pause ticking while keeping the WebSocket session open."""
        self.is_running = False
        asyncio.create_task(self.emit("paused", {"msg": "游戏已暂停，可随时继续。"}))

    def __init__(
        self,
        user_id: str,
        repo: RedisRepository,
        save_service: SaveService,
        game_service: GameService,
        db_factory: Callable[[], Any] = AsyncSessionLocal,
        llm_override: Optional[dict[str, Any]] = None,
        rp_llm_override: Optional[dict[str, Any]] = None,
        save_slot: int = 1,
    ):
        """Initialize one active engine instance for a WebSocket session."""
        self.user_id = user_id
        self.repo = repo
        self.save_service = save_service
        self.game_service = game_service
        self.db_factory = db_factory
        self.llm_override = llm_override
        self.rp_llm_override = rp_llm_override
        self.save_slot = save_slot
        self.event_queue: asyncio.Queue[GameEvent] = asyncio.Queue()
        self.is_running = False
        self._run_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._random_event_inflight = False
        self._dingtalk_inflight = False
        self._relax_inflight: set[str] = set()
        self._dingtalk_state_lock = asyncio.Lock()
        self._items_lock = asyncio.Lock()
        self._ttl_refresh_interval_seconds = 600
        self._last_ttl_refresh = 0.0
        # Speed is session-local; the persisted world balance keeps available modes.
        self.speed_multiplier = 1.0

        # Content mode starts conservative and can be changed by the player.
        self.mode: str = GameMode.HYBRID
        self.llm_available: bool = True
        self._llm_probed: bool = False

        # Docker images mount world data at /app/world; local tests use repo paths.
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "achievements.json"
            )
        self._achievement_config: dict[str, Any] | None = None

        # Course strategy values: 0=lay flat, 1=balanced, 2=hardcore.
        self.COURSE_STATE_COEFFS = balance.get_course_state_coeffs()
        self.BASE_ENERGY_DRAIN = balance.base_energy_drain
        self.BASE_MASTERY_GROWTH = balance.base_mastery_growth

    def _make_dingtalk_message(
        self,
        speaker: Literal["npc", "player", "system"],
        content: str,
        round_id: str | None = None,
    ) -> DingTalkMessage:
        """Create a DingTalk message with consistent IDs and timestamps."""
        return DingTalkMessage(
            message_id=new_message_id(),
            speaker=speaker,
            content=str(content or "").strip(),
            created_at=now_ts(),
            round_id=round_id,
        )

    def _coerce_dingtalk_options(
        self, raw_options: Any, role: str
    ) -> list[DingTalkReplyOption]:
        """Normalize LLM reply options and provide role-specific fallbacks."""
        if not is_replyable_role(role):
            return []
        options: list[DingTalkReplyOption] = []
        if isinstance(raw_options, list):
            for idx, item in enumerate(raw_options[:3]):
                if isinstance(item, DingTalkReplyOption):
                    options.append(item)
                    continue
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = str(item.get("text") or item.get("content") or "").strip()
                else:
                    text = ""
                if text:
                    option_id = (
                        str(item.get("option_id"))
                        if isinstance(item, dict) and item.get("option_id")
                        else f"opt_{idx + 1}"
                    )
                    options.append(
                        DingTalkReplyOption(option_id=option_id, text=text[:80])
                    )
        if options:
            return options
        fallback = {
            "roommate": ["哈哈收到", "我马上看看", "你先别急"],
            "classmate": ["可以，我看一下", "等我整理一下资料", "我也有点懵"],
            "friend": ["晚上再说？", "可以啊", "你这也太会了"],
            "teaching_assistant": ["谢谢助教提醒", "我有个问题想问", "我会尽快完成"],
            "teacher": ["谢谢老师", "我会提前准备", "我还有一个问题"],
            "crush": ["还好，你呢？", "我也在想这个", "要不要一起去？"],
        }.get(role, ["好的收到", "我想想怎么回", "可以再说详细点吗"])
        return [
            DingTalkReplyOption(option_id=f"opt_{idx + 1}", text=text)
            for idx, text in enumerate(fallback[:3])
        ]

    def _normalize_dingtalk_payload(
        self, msg_data: dict[str, Any]
    ) -> tuple[dict[str, Any], str, list[DingTalkReplyOption]]:
        """Normalize raw LLM/library DingTalk data into contact and message parts."""
        contact_raw = msg_data.get("contact")
        contact = contact_raw if isinstance(contact_raw, dict) else {}
        sender = str(contact.get("sender") or msg_data.get("sender") or "未知")
        role = normalize_dingtalk_role(
            str(contact.get("role") or msg_data.get("role") or "unknown")
        )
        contact_id = str(
            contact.get("contact_id") or build_contact_id(sender, role)
        )
        is_urgent = bool(contact.get("is_urgent", msg_data.get("is_urgent", False)))
        content = ""
        message_raw = msg_data.get("message")
        if isinstance(message_raw, dict):
            content = str(message_raw.get("content") or "").strip()
        if not content:
            content = str(msg_data.get("content") or "").strip()
        options = self._coerce_dingtalk_options(msg_data.get("reply_options"), role)
        if not is_replyable_role(role):
            options = []
        return (
            {
                "contact_id": contact_id,
                "sender": sender,
                "role": role,
                "is_replyable": is_replyable_role(role),
                "is_urgent": is_urgent,
            },
            content,
            options,
        )

    def _closed_dingtalk_contacts(
        self,
        contacts: dict[str, DingTalkContact],
    ) -> list[DingTalkContact]:
        """Return reusable closed contacts ordered from quietest to newest."""
        closed = [
            contact
            for contact in contacts.values()
            if contact.round.status != "open"
        ]
        closed.sort(key=lambda c: (c.last_message_at, c.contact_id))
        return closed

    def _choose_reusable_dingtalk_contact(
        self,
        contacts: dict[str, DingTalkContact],
        force: bool = False,
    ) -> DingTalkContact | None:
        """Pick an existing contact to balance variety against inbox growth."""
        closed = self._closed_dingtalk_contacts(contacts)
        if not closed:
            return None
        should_reuse = force or (
            random.random() < balance.dingtalk_reuse_closed_contact_probability
        )
        if not should_reuse:
            return None
        if len(closed) == 1:
            return closed[0]

        # Prefer contacts that have been quiet for longer, while keeping variety.
        weights = list(range(len(closed), 0, -1))
        return random.choices(closed, weights=weights, k=1)[0]

    def _character_from_contact(self, contact: DingTalkContact) -> dict[str, Any]:
        """Recover character-library metadata for a persisted DingTalk contact."""
        try:
            from app.core.dingtalk_llm import get_character_by_contact_id

            character = get_character_by_contact_id(contact.contact_id)
            if character:
                return character
        except Exception as exc:
            logger.debug("Could not load DingTalk character for reuse: %s", exc)
        return {
            "name": contact.sender,
            "role": contact.role,
            "content": f"你是{contact.sender}。",
            "examples": [],
        }

    async def _generate_dingtalk_for_existing_contact(
        self,
        contact: DingTalkContact,
        stats: dict[str, Any],
        context: str,
    ) -> dict[str, Any] | None:
        """Generate a new NPC message for an existing contact."""
        character = self._character_from_contact(contact)
        msg_data = None
        rp_override = self.rp_llm_override
        if rp_override or not self.llm_override:
            try:
                from app.core.dingtalk_llm import (
                    generate_dingtalk_for_character_via_m2her,
                )

                msg_data = await generate_dingtalk_for_character_via_m2her(
                    character,
                    stats,
                    context,
                    llm_override=rp_override,
                )
            except Exception as exc:
                logger.warning("M2-her DingTalk reuse fallback: %s", exc)
        if not msg_data:
            msg_data = await generate_dingtalk_message_for_character(
                character,
                stats,
                context,
                llm_override=self.llm_override,
            )
        if not msg_data:
            return None

        contact_payload = msg_data.get("contact")
        if not isinstance(contact_payload, dict):
            contact_payload = {}
        contact_payload.update(
            {
                "contact_id": contact.contact_id,
                "sender": contact.sender,
                "role": contact.role,
                "is_replyable": contact.is_replyable,
                "is_urgent": contact.is_urgent,
            }
        )
        msg_data["contact"] = contact_payload
        msg_data["sender"] = contact.sender
        msg_data["role"] = contact.role
        msg_data["is_urgent"] = contact.is_urgent
        return msg_data

    async def _emit_dingtalk_contact_update(self, contact: DingTalkContact):
        await self.emit(
            "dingtalk_thread_update",
            {"contact": contact.model_dump()},
        )

    async def _store_dingtalk_npc_message(
        self, msg_data: dict[str, Any]
    ) -> DingTalkContact | None:
        contact_meta, content, options = self._normalize_dingtalk_payload(msg_data)
        if not content:
            return None
        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact_limit = balance.dingtalk_max_contacts
            contact = state.contacts.get(contact_meta["contact_id"])
            if contact and contact.round.status == "open":
                return None
            if not contact:
                force_reuse = len(state.contacts) >= contact_limit
                if force_reuse:
                    reusable = self._choose_reusable_dingtalk_contact(
                        state.contacts,
                        force=True,
                    )
                    if reusable:
                        contact_meta.update(
                            {
                                "contact_id": reusable.contact_id,
                                "sender": reusable.sender,
                                "role": reusable.role,
                                "is_replyable": reusable.is_replyable,
                                "is_urgent": reusable.is_urgent,
                            }
                        )
                        contact = reusable
                    else:
                        return None
            if not contact:
                contact = DingTalkContact(**contact_meta)
            else:
                contact.sender = contact_meta["sender"]
                contact.role = contact_meta["role"]
                contact.is_replyable = bool(contact_meta["is_replyable"])
                contact.is_urgent = bool(contact_meta["is_urgent"])

            round_id = None
            if contact.is_replyable and options:
                contact.round = DingTalkRoundState(
                    round_id=f"dtr_{new_message_id()[4:]}",
                    status="open",
                    player_reply_count=0,
                )
                round_id = contact.round.round_id
                contact.pending_options = options
            else:
                contact.pending_options = []
                contact.round = DingTalkRoundState()

            message = self._make_dingtalk_message("npc", content, round_id=round_id)
            contact.messages.append(message)
            contact.unread_count += 1
            contact.last_message_at = message.created_at
            contact.trim_messages()
            state.contacts[contact.contact_id] = contact
            state.compact(max_contacts=contact_limit)
            await self.repo.set_dingtalk_state(state)
            return contact

    def _fallback_dingtalk_reply_result(
        self, contact: DingTalkContact, reply_count: int
    ) -> dict[str, Any]:
        if reply_count >= 3:
            return {
                "content": "嗯嗯，那这事先这样。之后有情况再和你说。",
                "settlement": {
                    "desc": f"你和{contact.sender}聊了一会儿，心情有些变化。",
                    "effects": {"sanity": 1},
                },
            }
        return {
            "content": "收到，我懂你的意思了。",
            "reply_options": self._coerce_dingtalk_options([], contact.role),
        }

    async def _generate_dingtalk_reply_result(
        self,
        contact: DingTalkContact,
        player_reply: str,
        reply_count: int,
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        rp_override = self.rp_llm_override
        if rp_override or not self.llm_override:
            try:
                from app.core.dingtalk_llm import (
                    generate_dingtalk_reply_via_m2her,
                    get_character_by_contact_id,
                )

                character = get_character_by_contact_id(contact.contact_id) or {
                    "name": contact.sender,
                    "role": contact.role,
                    "content": f"你是{contact.sender}。",
                    "examples": [],
                }
                history = [m.model_dump() for m in contact.messages]
                generated = await generate_dingtalk_reply_via_m2her(
                    character,
                    stats,
                    history,
                    player_reply,
                    reply_count,
                    llm_override=rp_override,
                )
                if generated:
                    return generated
            except Exception as e:
                logger.warning("M2-her dingtalk reply fallback: %s", e)
        try:
            character = {
                "name": contact.sender,
                "role": contact.role,
                "content": f"你是{contact.sender}。",
                "examples": [],
            }
            history = [m.model_dump() for m in contact.messages]
            generated = await generate_dingtalk_reply_message(
                character,
                stats,
                history,
                player_reply,
                reply_count,
                llm_override=self.llm_override,
            )
            if generated:
                return generated
        except Exception as e:
            logger.warning("Generic dingtalk reply fallback failed: %s", e)
        return self._fallback_dingtalk_reply_result(contact, reply_count)

    def _sanitize_dingtalk_effects(
        self, settlement: Any
    ) -> tuple[str, dict[str, int]]:
        if not isinstance(settlement, dict):
            return "这轮对话没有产生明显影响。", {}
        desc = str(settlement.get("desc") or "这轮对话产生了一些影响。").strip()
        effects_raw = settlement.get("effects")
        effects_raw = effects_raw if isinstance(effects_raw, dict) else {}
        effects: dict[str, int] = {}
        for key, value in effects_raw.items():
            max_delta = self._allowed_effect_fields().get(str(key))
            if max_delta is None:
                continue
            try:
                delta = int(value)
            except (TypeError, ValueError):
                continue
            effects[str(key)] = max(-max_delta, min(max_delta, delta))
        return desc, effects

    async def _apply_dingtalk_settlement(
        self, contact: DingTalkContact, settlement: Any
    ) -> dict[str, Any]:
        desc, effects = self._sanitize_dingtalk_effects(settlement)
        applied: dict[str, dict[str, int]] = {}
        changes: list[dict[str, Any]] = []
        for field, delta in effects.items():
            if delta == 0:
                continue
            change = await self._apply_stat_delta_for_feedback(field, delta)
            if not change:
                continue
            new_value = int(change.get("value", 0))
            applied[field] = {"delta": delta, "value": new_value}
            changes.append(change)
        message = desc if applied else "这轮对话平静结束，没有明显数值变化。"
        await self.emit("event", {"data": {"desc": f"钉钉：{message}"}})
        await self._emit_feedback(
            "钉钉对话",
            message,
            kind="info",
            auto_close_ms=3500,
            changes=changes,
        )
        await self.emit(
            "dingtalk_effect",
            {
                "contact_id": contact.contact_id,
                "summary": message,
                "effects": applied,
            },
        )
        await self._push_update()
        return {"summary": message, "effects": applied}

    def _track_task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        """Run a background task without blocking the WebSocket receive loop."""
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)

        def _finalize_background_task(done_task: asyncio.Task[Any]) -> None:
            self._background_tasks.discard(done_task)
            try:
                done_task.result()
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.error("Background game task failed", exc_info=True)

        task.add_done_callback(_finalize_background_task)
        return task

    async def _run_relax_action(self, target: str):
        try:
            await self._handle_relax(target)
            await self.check_and_trigger_gameover()
        except Exception:
            logger.error("Relax action failed for %s", target, exc_info=True)
        finally:
            self._relax_inflight.discard(target)

    def start(self):
        """Start or restart the ticking task for this engine."""
        if self.is_running and self._run_task and not self._run_task.done():
            return
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
        self.is_running = True
        self._run_task = asyncio.create_task(self.run_loop())

    async def check_and_trigger_gameover(
        self, stats: dict[str, Any] | None = None
    ) -> bool:
        """Trigger Game Over when energy or sanity reaches its fail endpoint."""
        if stats is None:
            snapshot = await self.repo.get_snapshot()
            stats = await self._effective_stats(snapshot.stats.model_dump())
        if not stats:
            return False
        try:
            # Registry defaults keep old or partial saves evaluable.
            sanity = int(stats.get("sanity", self._stat_default("sanity")))
            energy = int(stats.get("energy", self._stat_default("energy")))

            reason = ""
            if sanity <= 0:
                reason = "心态崩了，天台风好大..."
            elif energy <= 0:
                reason = "精力耗尽，远去的救护车..."

            if reason:
                await self.emit(
                    "game_over",
                    {"reason": reason, "restartable": True},
                )
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _sanity_stress_growth_factor(self, sanity, stress):
        """Return the learning-growth multiplier from sanity and stress.

        Sanity uses 50 as a neutral baseline. Stress rewards the configured
        optimal range and penalizes extreme values.
        """
        growth_mod = balance.get_growth_modifiers()
        sanity_cfg = growth_mod.get("sanity", {})
        stress_cfg = growth_mod.get("stress", {})

        critical_threshold = sanity_cfg.get("critical_low", {}).get("threshold", 20)
        critical_factor = sanity_cfg.get("critical_low", {}).get("factor", 0.6)
        low_slope = sanity_cfg.get("low_slope", 0.013)
        high_slope = sanity_cfg.get("high_slope", 0.007)
        excellent_threshold = sanity_cfg.get("excellent", {}).get("threshold", 80)
        excellent_factor = sanity_cfg.get("excellent", {}).get("factor", 1.2)

        if sanity < critical_threshold:
            sanity_factor = critical_factor
        elif sanity < 50:
            sanity_factor = 1 - (50 - sanity) * low_slope
        elif sanity >= excellent_threshold:
            sanity_factor = excellent_factor
        elif sanity > 50:
            sanity_factor = 1 + (sanity - 50) * high_slope
        else:
            sanity_factor = 1.0

        optimal_range = stress_cfg.get("optimal_range", [40, 70])
        optimal_factor = stress_cfg.get("optimal_factor", 1.3)
        suboptimal_factor = stress_cfg.get("suboptimal_factor", 0.85)
        extreme_factor = stress_cfg.get("extreme_factor", 0.6)

        if optimal_range[0] <= stress <= optimal_range[1]:
            stress_factor = optimal_factor
        elif 20 <= stress < optimal_range[0] or optimal_range[1] < stress <= 90:
            stress_factor = suboptimal_factor
        else:
            stress_factor = extreme_factor

        return sanity_factor * stress_factor

    def _sanity_stress_exam_factor(self, sanity, stress):
        """Return the final-exam score adjustment from sanity and stress.

        The exact slopes and bonuses are read from `game_balance.json`.
        """
        exam_mod = balance.get_exam_modifiers()
        sanity_cfg = exam_mod.get("sanity", {})
        stress_cfg = exam_mod.get("stress", {})

        low_slope = sanity_cfg.get("low_slope", 0.3)
        high_slope = sanity_cfg.get("high_slope", 0.12)
        excellent_bonus = sanity_cfg.get("excellent_bonus", 6)

        if sanity < 50:
            sanity_bonus = (sanity - 50) * low_slope
        elif sanity >= 80:
            sanity_bonus = excellent_bonus
        elif sanity > 50:
            sanity_bonus = (sanity - 50) * high_slope
        else:
            sanity_bonus = 0

        optimal_bonus = stress_cfg.get("optimal_bonus", 6)
        suboptimal_penalty = stress_cfg.get("suboptimal_penalty", -5)
        extreme_penalty = stress_cfg.get("extreme_penalty", -10)

        if 40 <= stress <= 70:
            stress_bonus = optimal_bonus
        elif 20 <= stress < 40 or 70 < stress <= 90:
            stress_bonus = suboptimal_penalty
        else:
            stress_bonus = extreme_penalty

        return sanity_bonus + stress_bonus

    async def run_loop(self):
        """Run the tick loop and apply course, event, and DingTalk progression."""
        logger.info(f"State-based Game loop started for {self.user_id}")

        tick_count = 0
        try:
            while self.is_running:
                # Real-time sleep shortens under speed-up, while game time
                # remains discrete.
                await asyncio.sleep(3.0 / self.speed_multiplier)
                if not self.is_running:
                    break
                tick_count += 1

                # Do not clamp elapsed time through update_stat_safe; timer values
                # intentionally exceed ordinary stat max bounds.
                elapsed = await self.repo.update_stat("elapsed_game_time", 3)

                snapshot = await self.repo.get_snapshot()
                stats = await self._effective_stats(snapshot.stats.model_dump())

                sem_idx = int(stats.get("semester_idx") or 1)
                sem_duration = balance.get_semester_duration(sem_idx)
                if elapsed >= sem_duration:
                    logger.info(
                        "Semester time exceeded for %s, triggering final exam.",
                        self.user_id,
                    )
                    self.stop()
                    await self._handle_final_exam()
                    break

                # Refresh TTLs infrequently for active players.
                now_ts = asyncio.get_running_loop().time()
                if (
                    now_ts - self._last_ttl_refresh
                    >= self._ttl_refresh_interval_seconds
                ):
                    await self.repo.touch_ttl()
                    self._last_ttl_refresh = now_ts

                if await self.check_and_trigger_gameover(stats):
                    break

                course_states_raw = snapshot.course_states

                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except (TypeError, json.JSONDecodeError):
                    course_info = []

                # Empty-course periods behave like a light recovery break.
                if not course_info:
                    logger.warning(
                        "[%s] course_info is EMPTY, skipping mastery growth",
                        self.user_id,
                    )
                    await self.repo.update_stat_safe("energy", 1)
                    await self._push_update()
                    continue

                # Course mastery and drain are credit-weighted each tick.
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0:
                    total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}

                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    state_val = int(course_states_raw.get(c_id, 1))
                    coeffs = self.COURSE_STATE_COEFFS.get(
                        state_val, self.COURSE_STATE_COEFFS[1]
                    )
                    iq_default = self._stat_default("iq")
                    iq_buff = (int(stats.get("iq", iq_default)) - iq_default) * 0.01
                    if state_val in (1, 2):
                        sanity = int(stats.get("sanity", self._stat_default("sanity")))
                        stress = int(stats.get("stress", self._stat_default("stress")))
                        factor = self._sanity_stress_growth_factor(sanity, stress)
                    else:
                        factor = 1.0
                    actual_growth = (
                        self.BASE_MASTERY_GROWTH
                        * coeffs["growth"]
                        * (1 + iq_buff)
                        * factor
                    )
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                if mastery_updates:
                    await self.repo.batch_update_course_mastery(mastery_updates)
                    if tick_count <= 3:
                        logger.info(
                            "[%s] tick#%s mastery_updates: %s",
                            self.user_id,
                            tick_count,
                            mastery_updates,
                        )
                else:
                    if tick_count <= 3:
                        logger.warning(
                            "[%s] tick#%s mastery_updates is EMPTY",
                            self.user_id,
                            tick_count,
                        )

                final_energy_cost_float = self.BASE_ENERGY_DRAIN * total_drain_factor

                # Only near-zero drain counts as true recovery; avoid integer
                # truncation.
                if final_energy_cost_float < 0.3:
                    await self.repo.update_stat_safe("energy", 2)
                    await self.repo.update_stat_safe("stress", -2)
                else:
                    final_energy_cost = max(1, math.ceil(final_energy_cost_float))
                    await self.repo.update_stat_safe("energy", -final_energy_cost)
                    if total_drain_factor > 1.5:
                        await self.repo.update_stat_safe("stress", 1)

                if self.is_running:
                    event_cfg = balance.get_random_event_config()
                    event_interval = event_cfg.get("check_interval_ticks", 5)
                    event_probability = event_cfg.get("trigger_probability", 0.4)

                    if tick_count % event_interval == 0:
                        if random.random() < event_probability:
                            if not self._random_event_inflight:
                                self._track_task(self._trigger_random_event())
                        await self._check_achievements()

                    dingtalk_cfg = balance.get_dingtalk_config()
                    dingtalk_interval = dingtalk_cfg.get("check_interval_ticks", 10)
                    dingtalk_probability = dingtalk_cfg.get("trigger_probability", 0.3)

                    if (
                        tick_count % dingtalk_interval == 0
                        and random.random() < dingtalk_probability
                    ):
                        if not self._dingtalk_inflight:
                            self._track_task(self._trigger_dingtalk_message())

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}", exc_info=True)
            self.stop()

    async def process_action(self, action_data: dict):
        """Dispatch one client action from the WebSocket receive loop.

        State transition summary:

        | action | Engine state | Redis/game state | Emitted state |
        | --- | --- | --- | --- |
        | start/get_state | unchanged | unchanged | tick snapshot |
        | pause | `is_running=False` | unchanged | none |
        | resume | `is_running=True` | unchanged | tick loop resumes |
        | restart | loop resets | stats/courses/items reset | init/tick flow |
        | set_speed | speed multiplier changes | unchanged | none |
        | set_mode | content mode changes | unchanged | mode_changed |
        | change_course_state | unchanged | course strategy hash | tick snapshot |
        | dingtalk_mark_read | unchanged | DingTalk unread state | dingtalk_update |
        | dingtalk_reply | background task | DingTalk messages | update/feedback |
        | item_buy/item_sell | unchanged | gold/items state | items_state/tick |
        | relax | background task | cooldowns/stats/logs | update/feedback |
        | exam | loop stops for modal | GPA/gold/achievements | semester_summary |
        | event_choice | unchanged | stats/current event | update/feedback |
        | next_semester | restart/end | semester/courses | new_semester/graduation |
        """
        action = action_data.get("action")
        target = action_data.get("target")
        value = action_data.get("value")
        if action in {"start", "get_state"}:
            await self._push_update()
            return
        if action == "pause":
            self.pause()
            return
        if action == "resume":
            self.resume()
            return
        if action == "restart":
            await self._handle_restart()
            return

        if action == "set_speed":
            try:
                speed = float(action_data.get("speed", 1.0))
            except (TypeError, ValueError):
                return
            if speed < 0.5 or speed > 5.0:
                return
            self.speed_multiplier = speed
            return

        if action == "set_mode":
            raw = action_data.get("mode", "hybrid")
            new_mode = GameMode.from_str(raw)
            if new_mode == GameMode.AI and self._llm_probed and not self.llm_available:
                await self.emit(
                    "toast",
                    {"message": "LLM API 不可用，已保持在当前模式", "level": "warning"},
                )
            else:
                self.mode = new_mode
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": self.llm_available},
                )
            # Probe custom/general LLM availability on the first mode request.
            if not self._llm_probed:
                self._llm_probed = True
                self._track_task(self._probe_llm())
            return

        if action == "change_course_state":
            if target and value is not None:
                await self.repo.set_course_state(target, int(value))
                # Push immediately so strategy buttons reflect server state.
                await self._push_update()
            return

        if action == "dingtalk_mark_read":
            contact_id = str(action_data.get("contact_id") or "").strip()
            if not contact_id:
                return
            state = await self.repo.mark_dingtalk_read(contact_id)
            contact = state.contacts.get(contact_id)
            if contact:
                await self._emit_dingtalk_contact_update(contact)
            return

        if action == "dingtalk_reply":
            self._track_task(self._handle_dingtalk_reply(action_data))
            return

        if action == "item_buy":
            await self._handle_item_buy(action_data)
            return

        if action == "item_sell":
            await self._handle_item_sell(action_data)
            return

        try:
            if action == "relax":
                if not isinstance(target, str) or not target:
                    await self._push_update("请选择一个有效的休闲动作。")
                    return
                if target in self._relax_inflight:
                    await self.emit(
                        "toast",
                        {"message": "该休闲动作正在结算中，请稍等", "level": "info"},
                    )
                    return
                self._relax_inflight.add(target)
                self._track_task(self._run_relax_action(target))
                return
            elif action == "exam":
                await self._handle_final_exam()
            elif action == "event_choice":
                await self._handle_event_choice(action_data)
            elif action == "next_semester":
                await self._next_semester()

            await self.check_and_trigger_gameover()
        except Exception as e:
            logger.error(f"Action Error {action}: {e}")

    async def _handle_dingtalk_reply(self, data: dict[str, Any]):
        contact_id = str(data.get("contact_id") or "").strip()
        option_id = str(data.get("option_id") or "").strip()
        if not contact_id or not option_id:
            await self.emit(
                "toast",
                {"message": "无效的钉钉回复", "level": "warning"},
            )
            return

        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact = state.contacts.get(contact_id)
            if not contact or not contact.is_replyable:
                await self.emit(
                    "toast",
                    {"message": "该联系人暂不支持回复", "level": "warning"},
                )
                return
            if contact.round.status != "open":
                await self.emit(
                    "toast",
                    {"message": "当前没有可回复的钉钉消息", "level": "warning"},
                )
                return

            option = next(
                (opt for opt in contact.pending_options if opt.option_id == option_id),
                None,
            )
            if option is None:
                await self.emit(
                    "toast",
                    {"message": "回复选项已过期", "level": "warning"},
                )
                return

            round_id = contact.round.round_id or f"dtr_{new_message_id()[4:]}"
            contact.round.round_id = round_id
            contact.round.status = "open"
            contact.round.player_reply_count += 1
            contact.pending_options = []
            player_message = self._make_dingtalk_message(
                "player", option.text, round_id=round_id
            )
            contact.messages.append(player_message)
            contact.last_message_at = player_message.created_at
            contact.trim_messages()
            state.contacts[contact_id] = contact
            await self.repo.set_dingtalk_state(state)

        await self._emit_dingtalk_contact_update(contact)

        snapshot = await self.repo.get_snapshot()
        stats = await self._effective_stats(snapshot.stats.model_dump())
        reply_count = contact.round.player_reply_count
        result = await self._generate_dingtalk_reply_result(
            contact, option.text, reply_count, stats
        )

        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact = state.contacts.get(contact_id)
            if contact is None:
                return
            npc_content = str(result.get("content") or "").strip()
            if npc_content:
                npc_message = self._make_dingtalk_message(
                    "npc", npc_content, round_id=contact.round.round_id
                )
                contact.messages.append(npc_message)
                contact.unread_count += 1
                contact.last_message_at = npc_message.created_at
            if reply_count >= 3:
                contact.pending_options = []
                contact.round.status = "closed"
            else:
                contact.pending_options = self._coerce_dingtalk_options(
                    result.get("reply_options"), contact.role
                )
            contact.trim_messages()
            state.contacts[contact_id] = contact
            await self.repo.set_dingtalk_state(state)

        await self._emit_dingtalk_contact_update(contact)
        if reply_count >= 3:
            await self._apply_dingtalk_settlement(contact, result.get("settlement"))

    def _item_effect_changes(
        self, item: dict[str, Any], sign: int = 1
    ) -> list[dict[str, Any]]:
        effects = item.get("effects")
        if not isinstance(effects, dict):
            return []
        changes: list[dict[str, Any]] = []
        for field, raw_delta in effects.items():
            try:
                delta = int(raw_delta) * sign
            except (TypeError, ValueError):
                continue
            if delta:
                changes.append(self._feedback_change(field, delta))
        return changes

    async def _handle_item_buy(self, data: dict[str, Any]):
        item_id = str(data.get("item_id") or "").strip()
        if not item_id:
            await self.emit("toast", {"message": "无效的道具", "level": "warning"})
            return
        if not self.is_running:
            await self.emit(
                "toast",
                {"message": "游戏暂停中，暂不能购买道具", "level": "warning"},
            )
            return

        async with self._items_lock:
            current_state = await self.repo.get_items_state()
            new_state, item, error = items.build_buy_state(current_state, item_id)
            if error or not item or not new_state:
                await self.emit(
                    "toast",
                    {"message": error or "道具购买失败", "level": "warning"},
                )
                return

            price = int(item.get("price", 0) or 0)
            snapshot = await self.repo.get_snapshot()
            current_gold = int(snapshot.stats.gold or 0)
            if current_gold < price:
                gold_label = self._FEEDBACK_FIELD_LABELS.get("gold", "gold")
                await self.emit(
                    "toast",
                    {
                        "message": f"{gold_label}不足，还差 {price - current_gold} 枚",
                        "level": "warning",
                    },
                )
                return

            gold_after = await self.repo.update_stat_safe("gold", -price)
            await self.repo.set_items_state(new_state)

        changes = [self._feedback_change("gold", -price, gold_after)]
        changes.extend(self._item_effect_changes(item, sign=1))
        item_name = str(item.get("name") or item_id)
        await self._push_items_state()
        await self._push_update(f"购买道具：{item_name}")
        await self._emit_feedback(
            "道具购买成功",
            f"你获得了「{item_name}」，持有加成已生效。",
            kind="info",
            auto_close_ms=3000,
            changes=changes,
        )

    async def _handle_item_sell(self, data: dict[str, Any]):
        item_id = str(data.get("item_id") or "").strip()
        if not item_id:
            await self.emit("toast", {"message": "无效的道具", "level": "warning"})
            return
        if not self.is_running:
            await self.emit(
                "toast",
                {"message": "游戏暂停中，暂不能出售道具", "level": "warning"},
            )
            return

        async with self._items_lock:
            current_state = await self.repo.get_items_state()
            new_state, item, error = items.build_sell_state(current_state, item_id)
            if error or not item or not new_state:
                await self.emit(
                    "toast",
                    {"message": error or "道具出售失败", "level": "warning"},
                )
                return

            sell_price = int(item.get("sell_price", 0) or 0)
            gold_after = await self.repo.update_stat_safe("gold", sell_price)
            await self.repo.set_items_state(new_state)

        changes = [self._feedback_change("gold", sell_price, gold_after)]
        changes.extend(self._item_effect_changes(item, sign=-1))
        item_name = str(item.get("name") or item_id)
        await self._push_items_state()
        await self._push_update(f"出售道具：{item_name}")
        await self._emit_feedback(
            "道具已出售",
            f"你卖出了「{item_name}」，对应持有加成已移除。",
            kind="info",
            auto_close_ms=3000,
            changes=changes,
        )
        await self.check_and_trigger_gameover()

    async def _handle_final_exam(self):
        """Settle final exams, GPA, rewards, achievements, and transcript data."""
        snapshot = await self.repo.get_snapshot()
        base_stats = snapshot.stats.model_dump()
        stats = await self._effective_stats(base_stats)
        if int(stats.get("exam_completed", 0) or 0):
            await self._push_update("本学期已经结算过期末考试，请开启新学期。")
            return
        self.stop()
        await self.repo.update_stats({"exam_completed": 1})
        stats["exam_completed"] = 1
        course_mastery = snapshot.courses
        logger.info(
            f"[{self.user_id}] EXAM: course_mastery from Redis = {course_mastery}"
        )

        try:
            raw_json = stats.get("course_info_json", "[]")
            course_info = json.loads(raw_json)
            logger.info(f"[{self.user_id}] EXAM: parsed {len(course_info)} courses")
        except Exception as parse_err:
            logger.error(
                f"[{self.user_id}] EXAM: Failed to parse course_info_json: {parse_err}"
            )
            course_info = []

        total_credits, total_gp, failed_count = 0, 0, 0
        courses_result = []

        sanity = int(stats.get("sanity", self._stat_default("sanity")))
        luck_default = self._stat_default("luck")
        luck = int(stats.get("luck", luck_default))

        for course in course_info:
            c_id = str(course.get("id"))
            mastery = float(course_mastery.get(c_id, 0))
            credits = float(course.get("credits", 1))
            # Final score is mastery-led, with sanity/stress and luck variation.
            sanity = int(stats.get("sanity", self._stat_default("sanity")))
            stress = int(stats.get("stress", self._stat_default("stress")))
            exam_bonus = self._sanity_stress_exam_factor(sanity, stress)
            luck_bonus = random.uniform(-2, 5) + (luck - luck_default) / 20
            final_score = max(0, min(100, mastery * 0.9 + exam_bonus + luck_bonus + 10))

            gp = max(0.0, round(final_score / 10 - 5, 2))
            fail_threshold = balance.fail_threshold
            if final_score < fail_threshold:
                failed_count += 1

            total_credits += credits
            total_gp += gp * credits
            courses_result.append(
                {
                    "name": course.get("name", "未知课程"),
                    "credit": credits,
                    "progress": round(mastery, 1),
                    "grade": round(final_score, 1),
                    "gpa": round(gp, 2),
                }
            )

        term_gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0
        cgpa, gpa_points_total, gpa_credits_total = self._calculate_cumulative_gpa(
            base_stats,
            total_gp,
            total_credits,
            term_gpa,
        )
        previous_highest_gpa = self._safe_float(base_stats.get("highest_gpa"))
        highest_gpa = max(previous_highest_gpa, term_gpa)

        msg = f"期末考试结束！GPA: {term_gpa}"
        if failed_count > 0:
            penalty = balance.fail_sanity_penalty * failed_count
            await self.repo.update_stat_safe("sanity", penalty)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            bonus = balance.pass_all_bonus
            await self.repo.update_stat_safe("sanity", bonus)

        gold_earned = items.calculate_exam_gold(term_gpa, failed_count)
        if gold_earned:
            await self.repo.update_stat_safe("gold", gold_earned)

        # HUD GPA is cumulative; highest_gpa keeps the best single-term GPA.
        await self.repo.update_stats(
            {
                "gpa": str(cgpa),
                "highest_gpa": str(round(highest_gpa, 2)),
                "gpa_points_total": str(round(gpa_points_total, 4)),
                "gpa_credits_total": str(round(gpa_credits_total, 4)),
            }
        )

        # Track persistence so disconnect cleanup can observe failures.
        self._track_task(self._update_db_highest_gpa(highest_gpa))
        new_achievements = await self._check_achievements(
            {"failed_count": failed_count}
        )

        await self.emit(
            "semester_summary",
            {
                "data": {
                    "term_gpa": term_gpa,
                    "cgpa": cgpa,
                    "gold_earned": gold_earned,
                    "failed_count": failed_count,
                    "courses": courses_result,
                    "achievements": new_achievements,
                }
            },
        )

        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """Persist the user's best single-term GPA summary."""
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    update(User)
                    .where(User.id == int(self.user_id))
                    .values(highest_gpa=str(gpa))
                )
                await db.execute(stmt)
                await db.commit()
            await self.repo.update_stats({"highest_gpa": str(gpa)})
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        snapshot = await self.repo.get_snapshot()
        stats = await self._effective_stats(snapshot.stats.model_dump())
        iq = int(stats.get("iq", 90))
        msg = "你暂时没有采取有效的学习动作。"

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except (TypeError, json.JSONDecodeError):
            course_info = []

        difficulty = 1.0
        for c in course_info:
            if str(c.get("id")) == str(course_id):
                difficulty = float(c.get("difficulty", 1.0))
                break

        mastery_delta = 0
        if action_type == "study":
            efficiency = 4.0 + (iq - 100) * 0.1
            mastery_delta = max(1.0, efficiency / (1 + difficulty))
            await self.repo.update_stat_safe("energy", -5)
            await self.repo.update_stat_safe("stress", 2)
            await self.repo.update_stat_safe("sanity", -1)
            msg = f"你埋头苦读，感觉知识暴涨！(擅长度 +{mastery_delta:.1f}%)"
        elif action_type == "fish":
            mastery_delta = 0.2
            await self.repo.update_stat_safe("energy", -1)
            await self.repo.update_stat_safe("stress", -1)
            await self.repo.update_stat_safe("sanity", 1)
            msg = "你在课上摸鱼，虽然学得慢，但心情不错。"
        elif action_type == "skip":
            await self.repo.update_stat_safe("energy", 2)
            await self.repo.update_stat_safe("stress", -3)
            await self.repo.update_stat_safe("sanity", 2)
            msg = "逃课一时爽，一直逃课一直爽！"

        if mastery_delta > 0:
            await self.repo.update_course_mastery(course_id, mastery_delta)
        if action_type in {"study", "fish", "skip"}:
            await self.repo.increment_action_count(action_type)

        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        # Enforce the server-side cooldown before applying an action.
        remaining_cd = await self._check_cooldown(target)
        if remaining_cd > 0:
            msg = f"该操作还在冷却中，请等待 {remaining_cd} 秒后再试。"
            await self._push_update(msg)
            return

        # Load relax-action tuning from the hot-reloadable balance config.
        action_cfg = balance.get_relax_action(target)
        if not action_cfg:
            msg = f"未知的休闲动作: {target}"
            await self._push_update(msg)
            return

        snapshot = await self.repo.get_snapshot()
        base_stats = snapshot.stats.model_dump()
        stats = await self._effective_stats(base_stats)
        msg = ""
        changes: list[dict[str, Any]] = []
        overflow_units = 0
        if target == "gym":
            current_energy = int(stats.get("energy", 0))
            min_energy = action_cfg.get("min_energy_required", 30)

            if current_energy < min_energy:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                # Charm gain is balance-configured and independent of overflow.
                energy_cost = action_cfg.get("energy_cost", -30)
                energy_gain = action_cfg.get("energy_gain", 40)
                sanity_gain = action_cfg.get("sanity_gain", 5)
                stress_change = action_cfg.get("stress_change", -5)

                net_energy = energy_cost + energy_gain
                for field, delta in (
                    ("energy", net_energy),
                    ("sanity", sanity_gain),
                    ("stress", stress_change),
                ):
                    overflow_units += await self._apply_relax_delta(
                        field,
                        int(delta),
                        base_stats,
                        changes,
                    )
                charm_probability = float(
                    action_cfg.get("charm_gain_probability", 0) or 0
                )
                charm_gain = int(action_cfg.get("charm_gain", 0) or 0)
                if charm_gain > 0 and random.random() < charm_probability:
                    overflow_units += await self._apply_relax_delta(
                        "charm",
                        charm_gain,
                        base_stats,
                        changes,
                    )
                await self.repo.set_cooldown(target, time.time())
                await self.repo.increment_action_count(target)
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            energy_cost = action_cfg.get("energy_cost", -5)
            sanity_gain = action_cfg.get("sanity_gain", 20)

            for field, delta in (
                ("energy", energy_cost),
                ("sanity", sanity_gain),
            ):
                overflow_units += await self._apply_relax_delta(
                    field,
                    int(delta),
                    base_stats,
                    changes,
                )
            await self.repo.set_cooldown(target, time.time())
            await self.repo.increment_action_count(target)
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            stress_change = action_cfg.get("stress_change", -10)

            overflow_units += await self._apply_relax_delta(
                "stress",
                int(stress_change),
                base_stats,
                changes,
            )
            await self.repo.set_cooldown(target, time.time())
            await self.repo.increment_action_count(target)
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            # CC98 effects are weighted in the balance config.
            effects = action_cfg.get("effects", [])
            if not effects:
                # Keep a safe fallback if the config omits effects.
                effects = [
                    {"weight": 0.5, "sanity": 8, "stress": -5},
                    {"weight": 0.3, "sanity": -10, "stress": 8},
                    {"weight": 0.2, "sanity": -15, "stress": 15},
                ]

            # Select one effect by weight.
            total_weight = sum(e.get("weight", 0) for e in effects)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            selected_effect = effects[0]

            for effect in effects:
                cumulative += effect.get("weight", 0)
                if roll <= cumulative:
                    selected_effect = effect
                    break

            # Apply the selected stat effects.
            for field in ("sanity", "stress"):
                if field not in selected_effect:
                    continue
                try:
                    delta = int(selected_effect[field])
                except (TypeError, ValueError):
                    continue
                overflow_units += await self._apply_relax_delta(
                    field,
                    delta,
                    base_stats,
                    changes,
                )

            # Pick a prompt trigger that matches the effect direction.
            effect_type = (
                "positive" if selected_effect.get("sanity", 0) > 0 else "negative"
            )
            roll = random.randint(1, 100)

            if effect_type == "positive":
                trigger_words = [
                    "校友糗事分享",
                    "今日开怀",
                    "难绷瞬间",
                    "幽默段子",
                    "校园梗",
                    "甜蜜爱情故事",
                ]
            else:
                trigger_words = [
                    "凡尔赛GPA",
                    "郁闷小屋",
                    "烂坑",
                    "情侣秀恩爱",
                    "渣男渣女",
                ]

            trigger = random.choice(trigger_words)
            if self.mode == GameMode.AI:
                # AI mode bypasses the local post library and uses the LLM path.
                post_content = None
            else:
                # Hybrid and library modes prefer zero-token precompiled posts.
                post_content = pick_cc98_post(effect=effect_type, trigger=trigger)
            if not post_content and self.mode != GameMode.LIBRARY:
                # Non-library modes can fall back to LLM generation on a miss.
                snapshot = await self.repo.get_snapshot()
                stats = await self._effective_stats(snapshot.stats.model_dump())
                post_content, feedback = await generate_cc98_post(
                    stats, effect_type, trigger, llm_override=self.llm_override
                )
                if post_content == "CC98 服务器维护中..." and self.mode == GameMode.AI:
                    self.llm_available = False
                    self.mode = GameMode.HYBRID
                    await self.emit(
                        "mode_changed",
                        {"mode": self.mode, "llm_available": False},
                    )
                    await self.emit(
                        "toast",
                        {
                            "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                            "level": "warning",
                        },
                    )
                    fallback_post = pick_cc98_post(effect=effect_type, trigger=trigger)
                    if fallback_post:
                        post_content = fallback_post
            elif not post_content:
                # Library mode skips the action if the library has no match.
                post_content, feedback = "服务器繁忙，论坛暂时打不开...", ""
            else:
                # Library hits use deterministic feedback by effect direction.
                feedback_map = {
                    "positive": "心情不错，继续冲浪~",
                    "neutral": "就这样吧，继续划水。",
                    "negative": "看得心态有点崩...",
                }
                feedback = feedback_map.get(effect_type, "")
            await self.repo.set_cooldown(target, time.time())
            await self.repo.increment_action_count(target)
            msg = f"你在CC98刷到了：\n{post_content}\n{feedback}"

        if overflow_units > 0:
            await self._transfer_relax_overflow(overflow_units, base_stats, changes)

        await self._push_update(msg)
        if msg:
            title_map = {
                "gym": "健身结果",
                "game": "游戏结果",
                "walk": "散步结果",
                "cc98": "CC98 新帖",
            }
            await self._emit_feedback(
                title_map.get(target, "休闲结果"),
                msg,
                kind="relax",
                auto_close_ms=3000,
                changes=changes,
            )

    # app/game/engine.py

    async def _trigger_random_event(self):
        """Trigger a random event through library-first or LLM fallback flow."""
        if not self.is_running:
            return
        if self._random_event_inflight:
            return

        self._random_event_inflight = True
        try:
            history = await self.repo.get_event_history()
            snapshot = await self.repo.get_snapshot()
            stats = await self._effective_stats(snapshot.stats.model_dump())
            if not self.is_running:
                return
            event_data = None

            if self.mode == GameMode.AI:
                # AI mode bypasses the event library and uses the LLM path.
                if self.llm_available:
                    event_data = await generate_random_event(
                        stats, history, llm_override=self.llm_override
                    )
                    if not self.is_running:
                        return
                if not event_data:
                    if not self.is_running:
                        return
                    self.llm_available = False
                    self.mode = GameMode.HYBRID
                    await self.emit(
                        "mode_changed",
                        {"mode": self.mode, "llm_available": False},
                    )
                    await self.emit(
                        "toast",
                        {
                            "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                            "level": "warning",
                        },
                    )
                    event_data = pick_random_event(
                        sanity=int(stats.get("sanity", self._stat_default("sanity"))),
                        stress=int(stats.get("stress", self._stat_default("stress"))),
                        seen_ids=set(history) if history else None,
                    )
            else:
                # Hybrid and library modes prefer zero-token precompiled events.
                event_data = pick_random_event(
                    sanity=int(stats.get("sanity", self._stat_default("sanity"))),
                    stress=int(stats.get("stress", self._stat_default("stress"))),
                    seen_ids=set(history) if history else None,
                )
                # Hybrid can fall back to LLM generation; library mode skips.
                if (
                    not event_data
                    and self.mode == GameMode.HYBRID
                    and self.llm_available
                ):
                    event_data = await generate_random_event(
                        stats, history, llm_override=self.llm_override
                    )
                    if not self.is_running:
                        return

            if event_data:
                if not self.is_running:
                    return
                # Deduplicate both library and LLM events through a stable event ID.
                event_id = event_data.get("id")
                if not event_id:
                    seed = f"{event_data.get('title', '')}|{event_data.get('desc', '')}"
                    event_id = (
                        f"llm_evt_{hashlib.md5(seed.encode('utf-8')).hexdigest()[:10]}"
                    )
                    event_data["id"] = event_id

                await self.repo.add_event_to_history(event_id)
                if not self.is_running:
                    return
                await self.repo.set_current_event(event_data)
                if not self.is_running:
                    return
                await self.emit("random_event", {"data": event_data})
        except Exception as e:
            logger.error(f"Random event error: {e}", exc_info=True)
        finally:
            self._random_event_inflight = False

    # Per-event effect caps; allowed fields come from stat_definitions.
    _EFFECT_FIELD_MAX_DELTAS = {
        "energy": 50,
        "sanity": 30,
        "stress": 30,
        "eq": 20,
        "luck": 20,
        "charm": 20,
        "reputation": 20,
        "gold": 200,
    }

    def _allowed_effect_fields(self) -> dict[str, int]:
        return {
            field: self._EFFECT_FIELD_MAX_DELTAS.get(field, 20)
            for field in stat_definitions.event_effect_fields
        }

    async def _handle_event_choice(self, data):
        """Apply one validated option from the current server-side random event."""
        option_id = str(data.get("option_id", "")).strip()
        current_event = await self.repo.pop_current_event()
        if not current_event:
            msg = "事件已经过期。"
            await self._push_update(msg)
            await self._emit_feedback("事件结果", msg, kind="event", auto_close_ms=5000)
            return

        selected_option = None
        for option in current_event.get("options", []) or []:
            candidate_id = str(option.get("id", "")).strip()
            legacy_candidate_id = str(option.get(" id", "")).strip()
            if option_id and option_id in {candidate_id, legacy_candidate_id}:
                selected_option = option
                break
        if selected_option is None:
            msg = "无效的事件选项。"
            await self._push_update(msg)
            await self._emit_feedback("事件结果", msg, kind="event", auto_close_ms=5000)
            return

        effects = selected_option.get("effects", {})
        if not isinstance(effects, dict):
            effects = {}
        desc = effects.get("desc", "")
        changes: list[dict[str, Any]] = []
        for key, val in effects.items():
            if key == "desc":
                continue
            # Only stat-registry-approved fields may be changed by events.
            max_delta = self._allowed_effect_fields().get(key)
            if max_delta is None:
                logger.warning(
                    "Blocked illegal effect field '%s' from user %s", key, self.user_id
                )
                continue
            try:
                delta = int(val)
                # Clamp each individual event effect before applying it.
                delta = max(-max_delta, min(max_delta, delta))
                change = await self._apply_stat_delta_for_feedback(key, delta)
                if change:
                    changes.append(change)
            except (ValueError, TypeError):
                continue
        result_msg = f"事件：{desc}"
        await self._push_update(result_msg)
        await self._emit_feedback(
            "事件结果",
            str(desc or "你的选择已经生效。"),
            kind="event",
            auto_close_ms=5000,
            changes=changes,
        )

    async def _trigger_dingtalk_message(self):
        """Trigger a DingTalk message, preferring the M2-her RP pipeline."""
        if not self.is_running:
            return
        if self._dingtalk_inflight:
            return

        # Library mode has no DingTalk library yet, so it skips AI messages.
        if self.mode == GameMode.LIBRARY or not self.llm_available:
            return

        self._dingtalk_inflight = True
        try:
            snapshot = await self.repo.get_snapshot()
            stats = await self._effective_stats(snapshot.stats.model_dump())
            if not self.is_running:
                return

            # Choose a coarse context for role and prompt selection.
            context = "random"
            sanity = int(stats.get("sanity", self._stat_default("sanity")))
            stress = int(stats.get("stress", self._stat_default("stress")))
            gpa = float(stats.get("gpa", 0))

            if sanity < 30:
                context = "low_sanity"
            elif stress > 80:
                context = "high_stress"
            elif gpa > 0 and gpa < 2.0:
                context = "low_gpa"

            state = await self.repo.get_dingtalk_state()
            if not self.is_running:
                return
            reusable_contact = self._choose_reusable_dingtalk_contact(
                state.contacts,
                force=len(state.contacts) >= balance.dingtalk_max_contacts,
            )

            # Prefer M2-her RP unless a general custom LLM should absorb the cost.
            msg_data = None
            rp_override = self.rp_llm_override
            if reusable_contact:
                msg_data = await self._generate_dingtalk_for_existing_contact(
                    reusable_contact,
                    stats,
                    context,
                )
                if not self.is_running:
                    return

            if not msg_data and (rp_override or not self.llm_override):
                try:
                    from app.core.dingtalk_llm import generate_dingtalk_via_m2her

                    msg_data = await generate_dingtalk_via_m2her(
                        stats, context, llm_override=rp_override
                    )
                    if not self.is_running:
                        return
                except Exception as e:
                    logger.warning(f"M2-her dingtalk fallback: {e}")

            # Fall back to the general DingTalk generator.
            if not msg_data:
                msg_data = await generate_dingtalk_message(
                    stats, context, llm_override=self.llm_override
                )
                if not self.is_running:
                    return

            if msg_data:
                if not self.is_running:
                    return
                contact = await self._store_dingtalk_npc_message(msg_data)
                if not self.is_running:
                    return
                if contact:
                    await self._emit_dingtalk_contact_update(contact)
            elif self.mode == GameMode.AI:
                self.llm_available = False
                self.mode = GameMode.HYBRID
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": False},
                )
                await self.emit(
                    "toast",
                    {
                        "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                        "level": "warning",
                    },
                )

        except Exception as e:
            logger.error(f"DingTalk trigger error: {e}", exc_info=True)
        finally:
            self._dingtalk_inflight = False

    def _achievement_payload(self, code: str, item: Any) -> dict[str, Any]:
        data = item if isinstance(item, dict) else {}
        clean_code = str(code or "").strip()
        return {
            "code": clean_code,
            "name": str(data.get("name") or clean_code),
            "desc": str(data.get("desc") or data.get("description") or ""),
            "icon": str(data.get("icon") or "🏅"),
        }

    def _achievement_details(self, codes: list[Any]) -> list[dict[str, Any]]:
        config = self._load_achievement_config()
        details: list[dict[str, Any]] = []
        for raw_code in codes:
            clean_code = str(raw_code or "").strip()
            item = config.get(raw_code) or config.get(clean_code)
            if item is None:
                for candidate_code, candidate in config.items():
                    if str(candidate_code).strip() == clean_code:
                        item = candidate
                        break
            details.append(self._achievement_payload(clean_code, item or {}))
        return details

    async def _check_achievements(
        self,
        context: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Evaluate achievements and emit only newly unlocked details."""
        try:
            context = context or {}
            snapshot = await self.repo.get_snapshot()
            stats = await self._effective_stats(snapshot.stats.model_dump())
            action_counts = await self.repo.get_action_counts()

            # Normalize persisted values before comparing achievement thresholds.
            gpa = float(stats.get("highest_gpa") or 0)
            sanity = int(stats.get("sanity") or 50)
            eq = int(stats.get("eq") or 50)
            charm = int(stats.get("charm") or 50)
            study_count = int(action_counts.get("study") or 0)
            cc98_count = int(action_counts.get("cc98") or 0)
            failed_count = int(context.get("failed_count") or 0)

            ach_config = self._load_achievement_config()
            if not ach_config:
                return []

            unlocked = await self.repo.get_unlocked_achievements()
            newly_unlocked: list[dict[str, Any]] = []

            for code, item in ach_config.items():
                clean_code = str(code).strip()
                normalized_code = clean_code.lower()
                if code in unlocked or clean_code in unlocked:
                    continue

                passed = False
                if normalized_code == "gpa_king" and gpa >= 4.5:
                    passed = True
                elif normalized_code == "broken_heart" and sanity < 10:
                    passed = True
                elif normalized_code == "social_butterfly" and (
                    eq >= 95 or charm >= 95
                ):
                    passed = True
                elif normalized_code == "library_ghost" and study_count > 50:
                    passed = True
                elif normalized_code == "survivor" and failed_count >= 3:
                    passed = True
                elif normalized_code == "water_monster" and cc98_count >= 100:
                    passed = True

                if passed:
                    await self.repo.unlock_achievement(code)
                    payload = self._achievement_payload(clean_code, item)
                    newly_unlocked.append(payload)
                    await self.emit(
                        "achievement_unlocked",
                        {"data": payload},
                    )
            return newly_unlocked
        except Exception as e:
            logger.error(f"Achievement check error: {e}")
            return []

    def _load_achievement_config(self) -> dict[str, Any]:
        if self._achievement_config is not None:
            return self._achievement_config
        if not self.achievement_path.exists():
            self._achievement_config = {}
            return self._achievement_config
        try:
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._achievement_config = data if isinstance(data, dict) else {}
        except Exception as e:
            logger.error("Failed to load achievements config: %s", e)
            self._achievement_config = {}
        return self._achievement_config

    async def _next_semester(self):
        """Advance to the next semester or emit graduation payloads."""
        self.stop()

        async with self.db_factory() as db:
            transition = await self.game_service.process_semester_transition(
                db,
                holiday_event_factory=generate_random_event,
                save_slot=self.save_slot,
            )

        current_semester_idx = transition.get("semester_idx")

        if transition.get("status") == "graduated":
            stats = await self._effective_stats(transition.get("stats") or {})
            achievements = stats.get("achievements")
            if isinstance(achievements, list):
                stats["achievement_details"] = self._achievement_details(achievements)
            # Generate the graduation summary after final stats are known.
            from app.core.llm import generate_wenyan_report

            if self.mode == GameMode.LIBRARY:
                wenyan_report = "学业既成，前程似锦。"
            else:
                wenyan_report = await generate_wenyan_report(
                    stats, llm_override=self.llm_override
                )
            await self.emit(
                "graduation",
                {
                    "data": {
                        "msg": "恭喜你从折姜大学毕业！",
                        "final_stats": stats,
                        "wenyan_report": wenyan_report,
                    }
                },
            )
            # Graduation is terminal, so the loop remains stopped.
            return

        # Re-read Redis after the service writes the new semester state.
        new_snapshot = await self.repo.get_snapshot()
        new_stats = await self._effective_stats(new_snapshot.stats.model_dump())
        semester_idx = int(new_stats.get("semester_idx") or current_semester_idx or 1)
        base_duration = balance.get_semester_duration(semester_idx)
        elapsed = int(new_stats.get("elapsed_game_time", 0) or 0)
        semester_time_left = self._get_semester_time_left(elapsed, base_duration)

        await self.emit(
            "new_semester",
            {
                "data": {
                    "semester_name": new_stats.get(
                        "semester", f"第 {current_semester_idx} 学期"
                    ),
                    "holiday_event": transition.get("holiday_event"),
                    "stats": new_stats,
                    "courses": new_snapshot.courses,
                    "course_states": new_snapshot.course_states,
                    "course_info_json": new_stats.get("course_info_json", "[]"),
                    "semester_time_left": semester_time_left,
                    "energy_recovery": transition.get("energy_recovery"),
                }
            },
        )
        await self._push_update("新学期开始了，加油！")
        self.start()

    async def _probe_llm(self):
        """Probe LLM availability in the background and downgrade if needed."""
        try:
            from app.core.llm import check_llm_availability

            available = await check_llm_availability(self.llm_override)
            self.llm_available = available
            if not available and self.mode == GameMode.AI:
                self.mode = GameMode.HYBRID
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": False},
                )
                await self.emit(
                    "toast",
                    {
                        "message": "LLM API 连接失败，已自动切换到混合模式",
                        "level": "warning",
                    },
                )
        except Exception as e:
            logger.warning(f"LLM probe failed: {e}")

    async def _push_update(self, msg: str | None = None):
        """Push the canonical frontend state payload."""
        try:
            snapshot = await self.repo.get_snapshot()
            new_stats = await self._effective_stats(snapshot.stats.model_dump())
            course_mastery = snapshot.courses
            course_states = snapshot.course_states
            relax_cooldowns = await self._get_relax_cooldowns()

            # Compute remaining time from the persisted virtual elapsed clock.
            semester_idx = int(new_stats.get("semester_idx", 1))
            base_duration = balance.get_semester_duration(semester_idx)
            elapsed = int(new_stats.get("elapsed_game_time", 0))
            semester_time_left = self._get_semester_time_left(elapsed, base_duration)

            # Include derived efficiency in the frontend payload without
            # persisting it into base stats.
            iq_default = self._stat_default("iq")
            efficiency_default = self._stat_default("efficiency")
            iq = int(new_stats.get("iq", iq_default))
            stress = int(new_stats.get("stress", self._stat_default("stress")))
            item_bonuses = new_stats.get("item_bonuses")
            efficiency_bonus = (
                int(item_bonuses.get("efficiency", 0))
                if isinstance(item_bonuses, dict)
                else 0
            )
            # Relative to defaults: IQ adds 1% per point and stress costs 0.5%.
            calculated_efficiency = max(
                10,
                efficiency_default
                + (iq - iq_default)
                - int(stress * 0.5)
                + efficiency_bonus,
            )
            new_stats["efficiency"] = calculated_efficiency

            await self.emit(
                "tick",
                {
                    "stats": new_stats,
                    "courses": course_mastery,
                    "course_states": course_states,
                    "semester_time_left": semester_time_left,
                    "relax_cooldowns": relax_cooldowns,
                },
                msg,
            )
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """Stop the tick loop without cancelling the current caller task."""
        self.is_running = False
        current_task = asyncio.current_task()
        if (
            self._run_task
            and not self._run_task.done()
            and self._run_task is not current_task
        ):
            self._run_task.cancel()
        self._run_task = None

    def shutdown(self):
        """Stop the tick loop and cancel pending background generation tasks."""
        self.stop()
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

    def _get_semester_time_left(
        self, elapsed_game_time: int, duration_seconds: int
    ) -> int:
        try:
            # Coerce defensively because Redis data can be stale or malformed.
            elapsed = int(elapsed_game_time)
            duration = int(duration_seconds)
            return max(0, duration - elapsed)
        except (TypeError, ValueError):
            # Fall back to the configured duration, then a conservative default.
            if isinstance(duration_seconds, (int, float)):
                return int(duration_seconds)
            return 360

    def _build_initial_stats(self, username: str) -> dict:
        from app.schemas.game_state import PlayerStats

        return PlayerStats.build_initial(username=username).model_dump()

    def _coerce_initial_stat(
        self,
        value: Any,
        default: int,
        minimum: int,
        maximum: int,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(maximum, parsed))

    async def _infer_restart_stat_overrides(
        self, stats: dict[str, Any], major_abbr: str
    ) -> dict[str, int]:
        initial_iq = int(stats.get("initial_iq", 0) or 0)
        if initial_iq <= 0:
            iq_buff = 0
            world = getattr(self.game_service, "world", None)
            if world is not None:
                try:
                    assignment = await world.get_major_by_abbr(major_abbr)
                    major_info = (assignment or {}).get("major_info", {})
                    iq_buff = int(major_info.get("iq_buff", 0) or 0)
                except Exception as exc:
                    logger.warning(
                        "Could not infer major IQ buff for restart: %s", exc
                    )
            iq_default = stat_definitions.by_id["iq"].default
            initial_iq = int(stats.get("iq", iq_default) or iq_default) - iq_buff

        overrides: dict[str, int] = {}
        for stat in stat_definitions.allocatable:
            raw_value = stats.get(f"initial_{stat.id}") or stats.get(stat.id)
            if stat.id == "iq":
                raw_value = initial_iq
            overrides[stat.id] = self._coerce_initial_stat(
                raw_value,
                stat.default,
                stat.min,
                stat.max,
            )
        return overrides

    async def _emit_current_init(self):
        snapshot = await self.repo.get_snapshot()
        stats = await self._effective_stats(snapshot.stats.model_dump())
        try:
            semester_idx = int(stats.get("semester_idx", 1) or 1)
        except (TypeError, ValueError):
            semester_idx = 1
        try:
            elapsed = int(stats.get("elapsed_game_time", 0) or 0)
        except (TypeError, ValueError):
            elapsed = 0
        base_duration = balance.get_semester_duration(semester_idx)
        dingtalk_state = await self.repo.get_dingtalk_state()
        items_state = await self._get_items_state_payload()

        await self.emit(
            "init",
            {
                "data": stats,
                "courses": snapshot.courses,
                "course_states": snapshot.course_states,
                "semester_time_left": self._get_semester_time_left(
                    elapsed, base_duration
                ),
                "relax_cooldowns": await self._get_relax_cooldowns(),
                "dingtalk_state": dingtalk_state.model_dump(),
                "items_state": items_state,
            },
        )

    async def _handle_restart(self):
        self.stop()
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        username = safe_username_for_prompt(stats.get("username") or "ZJUer")
        major_abbr = str(
            stats.get("initial_major_abbr") or stats.get("major_abbr") or ""
        ).strip()

        if major_abbr:
            overrides = await self._infer_restart_stat_overrides(stats, major_abbr)
            try:
                await self.game_service.assign_major_and_init(
                    major_abbr,
                    stat_overrides=overrides,
                    username=username,
                )
            except Exception as exc:
                logger.error(
                    "Failed to restart from initial profile for user %s: %s",
                    self.user_id,
                    exc,
                    exc_info=True,
                )
                await self.repo.set_game_data(self._build_initial_stats(username))
        else:
            await self.repo.set_game_data(self._build_initial_stats(username))

        self.speed_multiplier = 1.0
        await self._emit_current_init()
        self.start()

    async def _check_cooldown(self, action_type: str) -> int:
        last_use = await self.repo.get_cooldown_timestamp(action_type)
        if not last_use:
            return 0

        elapsed = time.time() - float(last_use)
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return math.ceil(remaining)

    async def _get_relax_cooldowns(self) -> dict[str, int]:
        cooldowns: dict[str, int] = {}
        for action in balance.relax_actions.keys():
            cooldowns[action] = await self._check_cooldown(action)
        return cooldowns
