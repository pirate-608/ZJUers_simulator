"""Redis repository for active player-session state.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The repository normalizes Redis payloads, refreshes TTLs, and provides atomic
updates for stats, courses, cooldowns, achievements, DingTalk, and items.
"""

import inspect
import json
import logging
from typing import Any, Awaitable, Dict, Iterable, List, Optional, Set, TypeVar

from redis import asyncio as aioredis

from app.api.cache import RedisCache
from app.core.config import settings
from app.game.stat_definitions import stat_definitions
from app.schemas.dingtalk import DingTalkState
from app.schemas.game_state import GameStateSnapshot
from app.schemas.holiday import HolidayState

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def _await_if_needed(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


class RedisRepository:
    """Atomic Redis gateway for one player's active game session."""

    def __init__(self, user_id: str, redis_client: aioredis.Redis):
        self.user_id = user_id
        self.redis = redis_client
        self.keys = {
            "stats": f"player:{user_id}:stats",
            "courses": f"player:{user_id}:courses",
            "course_states": f"player:{user_id}:course_states",
            "actions": f"player:{user_id}:actions",
            "achievements": f"player:{user_id}:achievements",
            "history": f"player:{user_id}:event_history",
            "cooldowns": f"player:{user_id}:cooldowns",
            "current_event": f"player:{user_id}:current_event",
            "dingtalk": f"player:{user_id}:dingtalk_state",
            "items": f"player:{user_id}:items_state",
            "holiday": f"player:{user_id}:holiday_state",
            "save_slot": f"player:{user_id}:save_slot",
            "transcript": f"player:{user_id}:semester_summary",
        }
        self.ttl = RedisCache.normalize_ttl(
            getattr(settings, "REDIS_PLAYER_TTL_SECONDS", 86400)
        )

    def all_keys(self) -> List[str]:
        """Return every Redis key owned by this player session."""
        return list(self.keys.values())

    def _normalize_stats_update(self, stats: Dict) -> Dict:
        """Convert registry-backed stat updates into Redis-friendly values."""
        if not stats:
            return {}
        int_fields = {
            "semester_idx",
            "semester_start_time",
            "elapsed_game_time",
            "exam_completed",
        } | stat_definitions.redis_int_fields
        str_fields = {
            "username",
            "major",
            "major_abbr",
            "initial_major_abbr",
            "semester",
            "gpa",
            "highest_gpa",
            "gpa_points_total",
            "gpa_credits_total",
            "course_plan_json",
            "course_info_json",
        }
        normalized = {}
        for key, value in stats.items():
            if key in int_fields:
                try:
                    normalized[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key in str_fields:
                normalized[key] = "" if value is None else str(value)
            else:
                normalized[key] = value
        return normalized

    def _normalize_course_map(self, data: Optional[Dict], cast_type):
        """Normalize course IDs and values before writing Redis hashes."""
        normalized = {}
        for key, value in (data or {}).items():
            try:
                normalized[str(key)] = cast_type(value)
            except (TypeError, ValueError):
                normalized[str(key)] = cast_type(0)
        return normalized

    async def exists(self) -> bool:
        """Return whether this player has an active Redis stats hash."""
        return await _await_if_needed(self.redis.exists(self.keys["stats"])) > 0

    async def get_all_game_data(self) -> Dict[str, Any]:
        """Fetch all active game data for startup or save handoff."""
        async with self.redis.pipeline() as pipe:
            pipe.hgetall(self.keys["stats"])
            pipe.hgetall(self.keys["courses"])
            pipe.hgetall(self.keys["course_states"])
            pipe.smembers(self.keys["achievements"])
            results = await pipe.execute()

        snapshot = GameStateSnapshot.from_redis_data(
            results[0], results[1], results[2], results[3]
        )
        data = snapshot.model_dump()
        data["stats"] = snapshot.stats.model_dump()
        data["items_state"] = await self.get_items_state()
        return data

    async def get_snapshot(self) -> GameStateSnapshot:
        """Return a normalized typed snapshot of active game state."""
        async with self.redis.pipeline() as pipe:
            pipe.hgetall(self.keys["stats"])
            pipe.hgetall(self.keys["courses"])
            pipe.hgetall(self.keys["course_states"])
            pipe.smembers(self.keys["achievements"])
            results = await pipe.execute()

        return GameStateSnapshot.from_redis_data(
            results[0], results[1], results[2], results[3]
        )

    async def get_action_counts(self) -> Dict[str, str]:
        """Return accumulated action counters for achievements and analytics."""
        return await _await_if_needed(self.redis.hgetall(self.keys["actions"]))

    async def get_unlocked_achievements(self) -> Set[str]:
        """Return unlocked achievement codes."""
        res = await _await_if_needed(self.redis.smembers(self.keys["achievements"]))
        return set(res) if res else set()

    async def get_event_history(self) -> List[str]:
        """Return recent event IDs used to reduce immediate repeats."""
        return await _await_if_needed(self.redis.lrange(self.keys["history"], 0, -1))

    async def get_dingtalk_state(self) -> DingTalkState:
        """Read DingTalk inbox state with corruption-tolerant fallback."""
        raw = await _await_if_needed(self.redis.get(self.keys["dingtalk"]))
        if not raw:
            return DingTalkState()
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = {}
        return DingTalkState.from_raw(parsed)

    async def get_items_state(self) -> Dict[str, Any]:
        """Read persisted item inventory state for this active session."""
        raw = await _await_if_needed(self.redis.get(self.keys["items"]))
        if not raw:
            return {"version": 1, "owned": [], "updated_at": 0}
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            parsed = {}
        return parsed if isinstance(parsed, dict) else {}

    async def set_items_state(self, state: Dict[str, Any]):
        """Persist item inventory state and refresh its TTL."""
        await _await_if_needed(
            self.redis.set(
                self.keys["items"],
                json.dumps(state or {}, ensure_ascii=False),
                ex=self.ttl,
            )
        )

    async def get_active_save_slot(self) -> int | None:
        """Identify the active slot so reconnects do not rewind a live session."""
        raw = await _await_if_needed(self.redis.get(self.keys["save_slot"]))
        try:
            slot = int(raw) if raw is not None else 0
            return slot if slot > 0 else None
        except (TypeError, ValueError):
            return None

    async def set_active_save_slot(self, save_slot: int) -> None:
        await _await_if_needed(
            self.redis.set(self.keys["save_slot"], str(save_slot), ex=self.ttl)
        )

    async def get_holiday_state(self) -> HolidayState:
        raw = await _await_if_needed(self.redis.get(self.keys["holiday"]))
        return HolidayState.from_raw(raw)

    async def get_semester_summary(self) -> dict | None:
        """Read the completed transcript without rerunning exam settlement."""
        raw = await _await_if_needed(self.redis.get(self.keys["transcript"]))
        try:
            data = json.loads(raw) if raw else None
            return data if isinstance(data, dict) else None
        except (TypeError, ValueError):
            return None

    async def set_semester_summary(self, data: dict | None) -> None:
        if data is None:
            await _await_if_needed(self.redis.delete(self.keys["transcript"]))
        else:
            await _await_if_needed(
                self.redis.set(
                    self.keys["transcript"],
                    json.dumps(data, ensure_ascii=False),
                    ex=self.ttl,
                )
            )

    async def set_holiday_state(self, state: HolidayState) -> None:
        await _await_if_needed(
            self.redis.set(self.keys["holiday"], state.model_dump_json(), ex=self.ttl)
        )

    async def update_holiday_if_current(self, state: HolidayState) -> bool:
        """Reject late generation from an old semester or restarted game."""
        script = """
        local raw = redis.call('GET', KEYS[2])
        if not raw then return 0 end
        local holiday = cjson.decode(raw)
        if holiday.token ~= ARGV[1] or holiday.status ~= 'pending' then return 0 end
        if tonumber(redis.call('HGET', KEYS[1], 'semester_idx')) ~= tonumber(ARGV[2])
           or tonumber(redis.call('HGET', KEYS[1], 'exam_completed') or 0) ~= 0
        then return 0 end
        redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[4])
        return 1
        """
        return bool(
            await _await_if_needed(
                self.redis.eval(
                    script,
                    2,
                    self.keys["stats"],
                    self.keys["holiday"],
                    state.token,
                    state.semester_idx,
                    state.model_dump_json(),
                    self.ttl,
                )
            )
        )

    async def commit_semester_transition(
        self,
        expected_semester_idx: int,
        stats_update: dict[str, Any],
        courses: dict[str, Any] | None,
        states: dict[str, Any] | None,
        holiday: HolidayState,
    ) -> bool:
        """CAS the complete term state, preserving it when another request won.

        Course preparation happens before this script. Readers therefore see
        either the complete old term or the complete new term, never a mixture.
        """
        payload = {
            "stats": self._normalize_stats_update(stats_update),
            "courses": self._normalize_course_map(courses, float),
            "states": self._normalize_course_map(states, int),
            "replace_courses": courses is not None,
        }
        script = """
        local idx = tonumber(redis.call('HGET', KEYS[1], 'semester_idx') or 1)
        if idx ~= tonumber(ARGV[1])
           or tonumber(redis.call('HGET', KEYS[1], 'exam_completed') or 0) ~= 1
        then return 0 end
        local data = cjson.decode(ARGV[2])
        for field, value in pairs(data.stats) do
            redis.call('HSET', KEYS[1], field, value)
        end
        if data.replace_courses then
            redis.call('DEL', KEYS[2], KEYS[3])
            for id, value in pairs(data.courses) do
                redis.call('HSET', KEYS[2], id, value)
            end
            for id, value in pairs(data.states) do
                redis.call('HSET', KEYS[3], id, value)
            end
        end
        redis.call('DEL', KEYS[4], KEYS[6])
        redis.call('SET', KEYS[5], ARGV[3], 'EX', ARGV[4])
        for _, key in ipairs(KEYS) do redis.call('EXPIRE', key, ARGV[4]) end
        return 1
        """
        return bool(
            await _await_if_needed(
                self.redis.eval(
                    script,
                    6,
                    self.keys["stats"],
                    self.keys["courses"],
                    self.keys["course_states"],
                    self.keys["current_event"],
                    self.keys["holiday"],
                    self.keys["transcript"],
                    expected_semester_idx,
                    json.dumps(payload, ensure_ascii=False),
                    holiday.model_dump_json(),
                    self.ttl,
                )
            )
        )

    async def set_dingtalk_state(self, state: DingTalkState | Dict[str, Any]):
        """Persist compact DingTalk state and refresh its TTL."""
        normalized = DingTalkState.from_raw(state).compact()
        await _await_if_needed(
            self.redis.set(
                self.keys["dingtalk"],
                json.dumps(normalized.model_dump(), ensure_ascii=False),
                ex=self.ttl,
            )
        )

    async def mark_dingtalk_read(self, contact_id: str) -> DingTalkState:
        """Clear unread count for one DingTalk contact."""
        state = await self.get_dingtalk_state()
        contact = state.contacts.get(contact_id)
        if contact:
            contact.unread_count = 0
            await self.set_dingtalk_state(state)
        return state

    async def get_cooldown_timestamp(self, action_type: str) -> Optional[float]:
        """Return a relax-action cooldown timestamp if present."""
        value = await _await_if_needed(
            self.redis.hget(self.keys["cooldowns"], action_type)
        )
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def get_cooldown_timestamps(
        self, action_types: Iterable[str]
    ) -> dict[str, float]:
        """Return cooldown timestamps for multiple relax actions in one read."""
        actions = [str(action) for action in action_types]
        if not actions:
            return {}
        values = await _await_if_needed(
            self.redis.hmget(self.keys["cooldowns"], actions)
        )
        result: dict[str, float] = {}
        for action, value in zip(actions, values or [], strict=False):
            if value is None:
                continue
            try:
                result[action] = float(value)
            except (TypeError, ValueError):
                continue
        return result

    async def set_game_data(
        self,
        stats: Dict,
        courses: Optional[Dict] = None,
        states: Optional[Dict] = None,
        achievements: Optional[List[str]] = None,
        items_state: Optional[Dict[str, Any]] = None,
    ):
        """Replace the active session with a complete game snapshot."""
        stats = self._normalize_stats_update(stats)
        courses = self._normalize_course_map(courses, float)
        states = self._normalize_course_map(states, int)
        async with self.redis.pipeline() as pipe:
            pipe.delete(*self.keys.values())
            pipe.hset(self.keys["stats"], mapping=stats)
            if courses:
                pipe.hset(self.keys["courses"], mapping=courses)
            if states:
                pipe.hset(self.keys["course_states"], mapping=states)
            if achievements:
                pipe.sadd(self.keys["achievements"], *achievements)
            if items_state is not None:
                pipe.set(
                    self.keys["items"],
                    json.dumps(items_state, ensure_ascii=False),
                    ex=self.ttl,
                )
            for key in self.keys.values():
                pipe.expire(key, self.ttl)
            await pipe.execute()

    async def delete_all(self):
        """Delete every active Redis key for this player."""
        await _await_if_needed(self.redis.delete(*self.keys.values()))

    async def touch_ttl(self):
        """Refresh all active-session TTLs."""
        await RedisCache.touch_ttl(self.all_keys(), self.ttl)

    async def update_courses_and_states(
        self,
        stats_update: Dict,
        courses: Optional[Dict] = None,
        states: Optional[Dict] = None,
    ):
        """Replace semester courses while preserving achievements/history."""
        stats_update = self._normalize_stats_update(stats_update)
        courses = self._normalize_course_map(courses, float)
        states = self._normalize_course_map(states, int)
        async with self.redis.pipeline() as pipe:
            if stats_update:
                pipe.hset(self.keys["stats"], mapping=stats_update)
            pipe.delete(self.keys["courses"], self.keys["course_states"])
            if courses:
                pipe.hset(self.keys["courses"], mapping=courses)
            if states:
                pipe.hset(self.keys["course_states"], mapping=states)
            for key in self.keys.values():
                pipe.expire(key, self.ttl)
            await pipe.execute()

    async def update_stats(self, stats_update: Dict):
        """Patch player stats without touching other Redis structures."""
        stats_update = self._normalize_stats_update(stats_update)
        if not stats_update:
            return
        async with self.redis.pipeline() as pipe:
            pipe.hset(self.keys["stats"], mapping=stats_update)
            pipe.expire(self.keys["stats"], self.ttl)
            await pipe.execute()

    async def update_stat_safe(
        self,
        field: str,
        delta: int,
        min_val: int | None = None,
        max_val: int | None = None,
    ) -> int:
        """Atomically update a stat while clamping it to registry bounds."""
        definition = stat_definitions.by_id.get(field)
        if min_val is None:
            min_val = definition.min if definition else 0
        if max_val is None:
            max_val = definition.max if definition else 200
        script = """
        local current = tonumber(redis.call('HGET', KEYS[1], ARGV[1]) or 0)
        local delta = tonumber(ARGV[2])
        local new_val = current + delta
        if new_val < tonumber(ARGV[3]) then new_val = tonumber(ARGV[3]) end
        if new_val > tonumber(ARGV[4]) then new_val = tonumber(ARGV[4]) end
        redis.call('HSET', KEYS[1], ARGV[1], new_val)
        return new_val
        """
        result = await _await_if_needed(
            self.redis.eval(
                script,
                1,
                self.keys["stats"],
                field,
                delta,
                min_val,
                max_val,
            )
        )
        return int(result)

    async def update_stat(self, field: str, delta: int) -> int:
        """Increment one stat without clamping; prefer `update_stat_safe`."""
        return await _await_if_needed(
            self.redis.hincrby(self.keys["stats"], field, delta)
        )

    async def update_course_mastery(self, course_id: str, delta: float) -> float:
        """Increment mastery for one course."""
        return await _await_if_needed(
            self.redis.hincrbyfloat(self.keys["courses"], course_id, delta)
        )

    async def batch_update_course_mastery(self, updates: Dict[str, float]):
        """Increment mastery for multiple courses in one pipeline."""
        if not updates:
            return
        async with self.redis.pipeline() as pipe:
            for c_id, delta in updates.items():
                pipe.hincrbyfloat(self.keys["courses"], c_id, delta)
            await pipe.execute()

    async def set_course_state(self, course_id: str, state_val: int):
        """Set one course strategy value."""
        await _await_if_needed(
            self.redis.hset(self.keys["course_states"], course_id, str(state_val))
        )

    async def increment_action_count(self, action_type: str) -> int:
        """Increment the counter for a player action."""
        return await _await_if_needed(
            self.redis.hincrby(self.keys["actions"], action_type, 1)
        )

    async def unlock_achievement(self, code: str) -> int:
        """Add an achievement code and return Redis `sadd` result."""
        return await _await_if_needed(self.redis.sadd(self.keys["achievements"], code))

    async def set_cooldown(self, action_type: str, timestamp: float):
        """Store the next-available timestamp for a relax action."""
        await _await_if_needed(
            self.redis.hset(self.keys["cooldowns"], action_type, str(timestamp))
        )

    async def add_event_to_history(self, event_id: str, limit: int = 10):
        """Record a recent event ID while keeping history bounded."""
        async with self.redis.pipeline() as pipe:
            pipe.lpush(self.keys["history"], event_id)
            pipe.ltrim(self.keys["history"], 0, limit - 1)
            await pipe.execute()

    async def increment_semester(self) -> int:
        """Atomically increment and return the current semester index."""
        return await _await_if_needed(
            self.redis.hincrby(self.keys["stats"], "semester_idx", 1)
        )

    async def set_current_event(self, event_data: Dict[str, Any]):
        """Cache the currently pending random event choice payload."""
        await _await_if_needed(
            self.redis.set(
                self.keys["current_event"],
                json.dumps(event_data, ensure_ascii=False),
                ex=self.ttl,
            )
        )

    async def pop_current_event(self) -> Optional[Dict[str, Any]]:
        """Consume and return the pending random event choice payload."""
        raw = await _await_if_needed(self.redis.getdel(self.keys["current_event"]))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None

    async def get_current_event(self) -> dict[str, Any] | None:
        """Read an event without consuming a still-unvalidated choice."""
        raw = await _await_if_needed(self.redis.get(self.keys["current_event"]))
        try:
            data = json.loads(raw) if raw else None
            return data if isinstance(data, dict) else None
        except (TypeError, ValueError):
            return None

    async def consume_event_choice(self, event_id: str, option_id: str) -> dict | None:
        """Atomically accept one matching choice and complete holiday metadata."""
        script = """
        local raw = redis.call('GET', KEYS[1])
        if not raw then return nil end
        local event = cjson.decode(raw)
        if (event.id or '') ~= ARGV[1] then return nil end
        if event.semester_idx and tonumber(event.semester_idx) ~=
           tonumber(redis.call('HGET', KEYS[2], 'semester_idx')) then return nil end
        if tonumber(redis.call('HGET', KEYS[2], 'exam_completed') or 0) ~= 0 then
            return nil
        end
        local selected = nil
        for _, option in ipairs(event.options or {}) do
            if option.id == ARGV[2] or option[' id'] == ARGV[2] then
                selected = option
            end
        end
        if not selected then return nil end
        if event.kind == 'holiday' then
            local holiday_raw = redis.call('GET', KEYS[3])
            if not holiday_raw then return nil end
            local holiday = cjson.decode(holiday_raw)
            if holiday.token ~= ARGV[1] or holiday.status ~= 'ready' then return nil end
            local bounds = cjson.decode(ARGV[4])
            event._applied_effects = {}
            for field, value in pairs(selected.effects or {}) do
                local config = bounds[field]
                local delta = tonumber(value)
                if config and delta then
                    delta = math.max(-10, math.min(10, math.floor(delta)))
                    local before = tonumber(redis.call('HGET', KEYS[2], field))
                        or config.default
                    local after = math.max(config.min,
                        math.min(config.max, before + delta))
                    redis.call('HSET', KEYS[2], field, after)
                    event._applied_effects[field] = {
                        delta = after - before, value = after
                    }
                end
            end
            holiday.status = 'resolved'
            holiday.event = cjson.null
            redis.call('SET', KEYS[3], cjson.encode(holiday), 'EX', ARGV[3])
            redis.call('EXPIRE', KEYS[2], ARGV[3])
        end
        redis.call('DEL', KEYS[1])
        return cjson.encode(event)
        """
        raw = await _await_if_needed(
            self.redis.eval(
                script,
                3,
                self.keys["current_event"],
                self.keys["stats"],
                self.keys["holiday"],
                event_id,
                option_id,
                self.ttl,
                json.dumps(
                    {
                        stat.id: {
                            "min": stat.min,
                            "max": stat.max,
                            "default": stat.default,
                        }
                        for stat in stat_definitions.stats
                        if stat.allow_event_effect
                    }
                ),
            )
        )
        return json.loads(raw) if raw else None
