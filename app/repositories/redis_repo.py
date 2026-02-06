import logging
from typing import Dict, Any, List, Optional
from redis import asyncio as aioredis
from app.core.config import settings
from app.api.cache import RedisCache
from app.schemas.game_state import GameStateSnapshot

logger = logging.getLogger(__name__)


class RedisRepository:
    """处理玩家状态在 Redis 中的原子读写"""

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
        }
        self.ttl = RedisCache.normalize_ttl(
            getattr(settings, "REDIS_PLAYER_TTL_SECONDS", 86400)
        )

    def all_keys(self) -> List[str]:
        return list(self.keys.values())

    def _normalize_stats_update(self, stats: Dict) -> Dict:
        if not stats:
            return {}
        int_fields = {
            "semester_idx",
            "semester_start_time",
            "energy",
            "sanity",
            "stress",
            "iq",
            "eq",
            "luck",
            "reputation",
        }
        str_fields = {
            "username",
            "major",
            "major_abbr",
            "semester",
            "gpa",
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
        normalized = {}
        for key, value in (data or {}).items():
            try:
                normalized[str(key)] = cast_type(value)
            except (TypeError, ValueError):
                normalized[str(key)] = cast_type(0)
        return normalized

    async def exists(self) -> bool:
        return await self.redis.exists(self.keys["stats"]) > 0

    async def get_all_game_data(self) -> Dict[str, Any]:
        """批量获取玩家所有核心数据"""
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
        return data

    async def get_snapshot(self) -> GameStateSnapshot:
        """返回已规范化的快照对象"""
        async with self.redis.pipeline() as pipe:
            pipe.hgetall(self.keys["stats"])
            pipe.hgetall(self.keys["courses"])
            pipe.hgetall(self.keys["course_states"])
            pipe.smembers(self.keys["achievements"])
            results = await pipe.execute()

        return GameStateSnapshot.from_redis_data(
            results[0], results[1], results[2], results[3]
        )

    async def set_game_data(
        self,
        stats: Dict,
        courses: Optional[Dict] = None,
        states: Optional[Dict] = None,
        achievements: Optional[List[str]] = None,
    ):
        """写入玩家状态并刷新 TTL"""
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
            for key in self.keys.values():
                pipe.expire(key, self.ttl)
            await pipe.execute()

    async def delete_all(self):
        await self.redis.delete(*self.keys.values())

    async def touch_ttl(self):
        await RedisCache.touch_ttl(self.all_keys(), self.ttl)

    async def update_courses_and_states(
        self,
        stats_update: Dict,
        courses: Optional[Dict] = None,
        states: Optional[Dict] = None,
    ):
        """更新学期课程数据并刷新 TTL（不清空成就/历史等）"""
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

    async def update_stat_safe(
        self, field: str, delta: int, min_val: int = 0, max_val: int = 200
    ) -> int:
        script = """
        local current = tonumber(redis.call('HGET', KEYS[1], ARGV[1]) or 0)
        local delta = tonumber(ARGV[2])
        local new_val = current + delta
        if new_val < tonumber(ARGV[3]) then new_val = tonumber(ARGV[3]) end
        if new_val > tonumber(ARGV[4]) then new_val = tonumber(ARGV[4]) end
        redis.call('HSET', KEYS[1], ARGV[1], new_val)
        return new_val
        """
        result = await self.redis.eval(
            script, 1, self.keys["stats"], field, delta, min_val, max_val
        )
        return int(result)

    async def update_stat(self, field: str, delta: int) -> int:
        return await self.redis.hincrby(self.keys["stats"], field, delta)

    async def update_course_mastery(self, course_id: str, delta: float) -> float:
        return await self.redis.hincrbyfloat(self.keys["courses"], course_id, delta)

    async def batch_update_course_mastery(self, updates: Dict[str, float]):
        if not updates:
            return
        async with self.redis.pipeline() as pipe:
            for c_id, delta in updates.items():
                pipe.hincrbyfloat(self.keys["courses"], c_id, delta)
            await pipe.execute()

    async def set_course_state(self, course_id: str, state_val: int):
        await self.redis.hset(self.keys["course_states"], course_id, state_val)

    async def increment_action_count(self, action_type: str) -> int:
        return await self.redis.hincrby(self.keys["actions"], action_type, 1)

    async def unlock_achievement(self, code: str) -> int:
        return await self.redis.sadd(self.keys["achievements"], code)

    async def set_cooldown(self, action_type: str, timestamp: float):
        await self.redis.hset(self.keys["cooldowns"], action_type, timestamp)

    async def add_event_to_history(self, title: str, limit: int = 10):
        async with self.redis.pipeline() as pipe:
            pipe.lpush(self.keys["history"], title)
            pipe.ltrim(self.keys["history"], 0, limit - 1)
            await pipe.execute()

    async def increment_semester(self) -> int:
        return await self.redis.hincrby(self.keys["stats"], "semester_idx", 1)
