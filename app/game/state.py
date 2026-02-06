import logging
import random
from typing import Optional, Dict, Any, Set, List
from redis import asyncio as aioredis
from app.core.config import settings
from app.api.cache import RedisCache
from app.schemas.game_state import PlayerStats
from app.repositories.redis_repo import RedisRepository

logger = logging.getLogger(__name__)


class RedisState:
    _connection_pool: Optional[aioredis.ConnectionPool] = None

    def __init__(self, user_id: str):
        self.user_id = user_id

        if RedisState._connection_pool is None:
            RedisState._connection_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL, decode_responses=True, max_connections=100
            )

        self.redis = aioredis.Redis(connection_pool=RedisState._connection_pool)
        self.repo = RedisRepository(self.user_id, self.redis)
        self.key = f"player:{user_id}:stats"
        self.course_key = f"player:{user_id}:courses"
        self.course_state_key = f"player:{user_id}:course_states"  # [新增] 存储课程状态
        self.action_key = f"player:{user_id}:actions"
        self.achievement_key = f"player:{user_id}:achievements"
        self.history_key = f"player:{user_id}:event_history"  # [新增] 历史记录 Key
        self.cooldown_key = f"player:{user_id}:cooldowns"  # [新增] 冷却时间 Key

    @classmethod
    async def cleanup_orphan_player_keys(cls, ttl_seconds: int, delete: bool = False):
        """Ensure legacy player keys have TTL; optionally delete them."""
        redis = RedisCache.get_client()
        ttl_seconds = RedisCache.normalize_ttl(ttl_seconds)

        cursor = 0
        scanned = 0
        fixed = 0

        while True:
            cursor, keys = await redis.scan(cursor=cursor, match="player:*", count=200)
            if keys:
                scanned += len(keys)
                for key in keys:
                    ttl = await redis.ttl(key)
                    if ttl == -1:
                        if delete:
                            await redis.delete(key)
                        else:
                            await redis.expire(key, ttl_seconds)
                        fixed += 1
            if cursor == 0:
                break

        if fixed > 0:
            logger.info(
                "Redis cleanup updated %s/%s legacy keys with no TTL", fixed, scanned
            )

    async def clear_all(self):
        """清空玩家所有存档数据"""
        await self.repo.delete_all()

    async def close(self):
        await self.redis.aclose()

    async def exists(self) -> bool:
        return await self.redis.exists(self.key) > 0

    # ==========================================
    # 2. 游戏初始化逻辑
    # ==========================================
    async def init_game(self, username: str, tier: str) -> Dict[str, Any]:
        import time

        # 只初始化基础信息，不分配专业
        initial_stats = {
            "username": username,
            "major": "",
            "major_abbr": "",
            "semester": "大一秋冬",
            "semester_idx": 1,
            "semester_start_time": int(time.time()),  # 记录学期开始时间
            "energy": 100,
            "sanity": 80,
            "stress": 0,
            "iq": 0,
            "eq": random.randint(60, 90),
            "luck": random.randint(0, 100),
            "gpa": "0.0",
            "reputation": 0,
            "course_plan_json": "",
            "course_info_json": "",
        }
        await self.repo.set_game_data(initial_stats)
        return initial_stats

    # ==========================================
    # 3. 数值操作
    # ==========================================
    async def get_stats(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.key)

    async def get_stats_typed(self) -> Dict[str, Any]:
        raw = await self.redis.hgetall(self.key)
        return PlayerStats.from_redis(raw).model_dump()

    async def update_stat_safe(
        self, field: str, delta: int, min_val: int = 0, max_val: int = 200
    ) -> int:
        return await self.repo.update_stat_safe(field, delta, min_val, max_val)

    async def update_stat(self, field: str, delta: int) -> int:
        return await self.repo.update_stat(field, delta)

    # ==========================================
    # 4. 课程状态与进度管理 (核心改动)
    # ==========================================
    async def get_courses_mastery(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.course_key)

    async def get_courses_mastery_typed(self) -> Dict[str, float]:
        raw = await self.redis.hgetall(self.course_key)
        typed = {}
        for k, v in (raw or {}).items():
            try:
                typed[str(k)] = float(v)
            except (TypeError, ValueError):
                typed[str(k)] = 0.0
        return typed

    async def update_course_mastery(self, course_id: str, delta: float) -> float:
        """单门课程更新 (保留用于特殊事件)"""
        return await self.repo.update_course_mastery(course_id, delta)

    async def batch_update_course_mastery(self, updates: Dict[str, float]):
        """[新增] 批量更新课程擅长度 (Pipeline 优化)"""
        await self.repo.batch_update_course_mastery(updates)

    async def set_course_state(self, course_id: str, state_val: int):
        """[新增] 设置课程状态: 0=摆, 1=摸, 2=卷"""
        await self.repo.set_course_state(course_id, state_val)

    async def get_all_course_states(self) -> Dict[str, str]:
        """[新增] 获取所有课程当前状态"""
        return await self.redis.hgetall(self.course_state_key)

    async def get_all_course_states_typed(self) -> Dict[str, int]:
        raw = await self.redis.hgetall(self.course_state_key)
        typed = {}
        for k, v in (raw or {}).items():
            try:
                typed[str(k)] = int(v)
            except (TypeError, ValueError):
                typed[str(k)] = 1
        return typed

    # ==========================================
    # 5. 动作与成就
    # ==========================================
    async def increment_action_count(self, action_type: str) -> int:
        return await self.repo.increment_action_count(action_type)

    async def get_action_counts(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.action_key)

    async def get_unlocked_achievements(self) -> Set[str]:
        res = await self.redis.smembers(self.achievement_key)
        return set(res) if res else set()

    async def unlock_achievement(self, code: str) -> int:
        return await self.repo.unlock_achievement(code)

    # ==========================================
    # 5.5. 冷却系统 (CD System)
    # ==========================================

    async def check_cooldown(self, action_type: str) -> int:
        """检查冷却时间，返回剩余秒数（0=可用）"""
        import time
        from app.game.balance import balance

        last_use = await self.redis.hget(self.cooldown_key, action_type)
        if not last_use:
            return 0

        elapsed = time.time() - float(last_use)
        # 从配置文件读取冷却时间
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return int(remaining)

    async def set_cooldown(self, action_type: str):
        """记录动作使用时间"""
        import time

        await self.repo.set_cooldown(action_type, time.time())

    # ==========================================
    # 6. 事件历史记录 (新增)
    # ==========================================

    async def get_event_history(self) -> List[str]:
        """获取最近 10 个事件的标题"""
        # 获取 Redis 列表中所有的标题
        return await self.redis.lrange(self.history_key, 0, -1)

    async def add_event_to_history(self, title: str):
        """记录新发生的事件，并保持队列长度为 10"""
        await self.repo.add_event_to_history(title, limit=10)

    # ==========================================
    # 6. 学期循环
    # ==========================================
    async def increment_semester(self) -> int:
        return await self.repo.increment_semester()

    async def get_semester_time_left(self, duration_seconds: int) -> int:
        """计算学期剩余时间（秒）"""
        import time

        start_time_str = await self.redis.hget(self.key, "semester_start_time")
        if not start_time_str:
            return duration_seconds  # 如果没有开始时间，返回完整时长

        start_time = int(start_time_str)
        elapsed = int(time.time()) - start_time
        remaining = max(0, duration_seconds - elapsed)
        return remaining
