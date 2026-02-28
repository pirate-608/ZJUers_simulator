import asyncio
import logging
from redis import asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisCache:
    _connection_pool = None

    @staticmethod
    def normalize_ttl(ttl_seconds: int) -> int:
        try:
            ttl_int = int(ttl_seconds)
        except (TypeError, ValueError):
            return 86400
        return max(60, ttl_int)

    @staticmethod
    def build_player_keys(user_id: str):
        return [
            f"player:{user_id}:stats",
            f"player:{user_id}:courses",
            f"player:{user_id}:course_states",
            f"player:{user_id}:actions",
            f"player:{user_id}:achievements",
            f"player:{user_id}:event_history",
            f"player:{user_id}:cooldowns",
        ]

    @classmethod
    def get_client(cls):
        if cls._connection_pool is None:
            cls._connection_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL, decode_responses=True, max_connections=20
            )
        return aioredis.Redis(connection_pool=cls._connection_pool)

    @classmethod
    async def lpop(cls, key: str):
        redis = cls.get_client()
        return await redis.lpop(key)

    @classmethod
    async def rpush(cls, key: str, value):
        redis = cls.get_client()
        return await redis.rpush(key, value)

    @classmethod
    async def rpush_with_limit(
        cls, key: str, value, max_len: int = None, ttl_seconds: int = None
    ):
        redis = cls.get_client()
        async with redis.pipeline() as pipe:
            pipe.rpush(key, value)
            if max_len:
                pipe.ltrim(key, -int(max_len), -1)
            if ttl_seconds:
                pipe.expire(key, int(ttl_seconds))
            result = await pipe.execute()
        return result

    @classmethod
    async def rpush_many_with_limit(
        cls, key: str, values, max_len: int = None, ttl_seconds: int = None
    ):
        if not values:
            return None
        redis = cls.get_client()
        async with redis.pipeline() as pipe:
            pipe.rpush(key, *values)
            if max_len:
                pipe.ltrim(key, -int(max_len), -1)
            if ttl_seconds:
                pipe.expire(key, int(ttl_seconds))
            result = await pipe.execute()
        return result

    @classmethod
    async def llen(cls, key: str):
        redis = cls.get_client()
        return await redis.llen(key)

    @classmethod
    async def set(cls, key: str, value, ex: int = None):
        redis = cls.get_client()
        return await redis.set(key, value, ex=ex)

    @classmethod
    async def get(cls, key: str):
        redis = cls.get_client()
        return await redis.get(key)

    @classmethod
    async def delete(cls, key: str):
        redis = cls.get_client()
        return await redis.delete(key)

    @classmethod
    async def exists(cls, key: str):
        redis = cls.get_client()
        return await redis.exists(key)

    @classmethod
    async def expire(cls, key: str, seconds: int):
        redis = cls.get_client()
        return await redis.expire(key, seconds)

    @classmethod
    async def touch_ttl(cls, keys, ttl_seconds: int):
        if not keys:
            return None
        ttl_seconds = cls.normalize_ttl(ttl_seconds)
        redis = cls.get_client()
        async with redis.pipeline() as pipe:
            for key in keys:
                pipe.expire(key, ttl_seconds)
            result = await pipe.execute()
        return result


# 用法示例：
# await RedisCache.lpop('cc98:posts')
# await RedisCache.rpush('cc98:posts', '一条新段子')
# await RedisCache.set('foo', 'bar', ex=60)
# await RedisCache.get('foo')
