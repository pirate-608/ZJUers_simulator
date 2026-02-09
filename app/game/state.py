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
    """
    轻量级游戏状态门面。

    核心读写逻辑统一在 RedisRepository 中实现。
    本类仅保留：
      - 全局工具方法（cleanup_orphan_player_keys）
      - 游戏初始化（init_game）
      - 便捷方法（get_stats 等仅在 auth.py 中少量使用的快捷接口）

    不再维护独立连接池，统一使用 RedisCache 的连接池。
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        # 统一使用 RedisCache 连接池（不再创建独立的 ConnectionPool）
        self.redis = RedisCache.get_client()
        self.repo = RedisRepository(self.user_id, self.redis)
        self.key = f"player:{user_id}:stats"

    # ==========================================
    # 全局工具方法
    # ==========================================
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

    # ==========================================
    # 生命周期
    # ==========================================
    async def clear_all(self):
        """清空玩家所有存档数据"""
        await self.repo.delete_all()

    async def close(self):
        """关闭 Redis 连接（使用共享池时实际为 noop，保留兼容性）"""
        # 使用共享连接池时不需要关闭，保留接口以兼容旧调用方
        pass

    async def exists(self) -> bool:
        return await self.redis.exists(self.key) > 0

    # ==========================================
    # 游戏初始化逻辑
    # ==========================================
    async def init_game(self, username: str, tier: str) -> Dict[str, Any]:
        import time

        initial_stats = {
            "username": username,
            "major": "",
            "major_abbr": "",
            "semester": "大一秋冬",
            "semester_idx": 1,
            "semester_start_time": int(time.time()),
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
    # 便捷查询接口（auth.py 等少量外部引用）
    # ==========================================
    async def get_stats(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.key)

    async def get_stats_typed(self) -> Dict[str, Any]:
        raw = await self.redis.hgetall(self.key)
        return PlayerStats.from_redis(raw).model_dump()
