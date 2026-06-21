"""Redis connection lifecycle and cache utility helpers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The backend treats Redis as the active game-state store, so this module keeps
connection creation, teardown, TTL normalization, and async-call compatibility
in one place.
"""

import inspect
import logging
from typing import Any, Awaitable, Optional, Sequence, TypeVar

from redis import asyncio as aioredis
from redis.asyncio.connection import ConnectionPool

from app.core.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def _await_if_needed(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


class RedisCache:
    """Shared Redis client pool and small cache/list helper methods."""

    _connection_pool: ConnectionPool | None = None

    @staticmethod
    def normalize_ttl(ttl_seconds: int) -> int:
        """Clamp Redis TTLs to a practical minimum."""
        try:
            ttl_int = int(ttl_seconds)
        except (TypeError, ValueError):
            return 86400
        return max(60, ttl_int)

    @staticmethod
    def build_player_keys(user_id: str) -> list[str]:
        """Return legacy active-state keys for one player."""
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
    def get_client(cls) -> aioredis.Redis:
        """Return a Redis client backed by a process-wide connection pool."""
        if cls._connection_pool is None:
            cls._connection_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL, decode_responses=True, max_connections=20
            )
        return aioredis.Redis(connection_pool=cls._connection_pool)

    @classmethod
    async def lpop(cls, key: str) -> Any | None:
        """Pop one value from the left side of a Redis list."""
        redis = cls.get_client()
        return await _await_if_needed(redis.lpop(key))

    @classmethod
    async def rpush(cls, key: str, value: Any) -> int:
        """Append one value to the right side of a Redis list."""
        redis = cls.get_client()
        return await _await_if_needed(redis.rpush(key, value))

    @classmethod
    async def rpush_with_limit(
        cls,
        key: str,
        value: Any,
        max_len: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ) -> list[Any]:
        """Append one value to a list, trim it, and optionally refresh TTL."""
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
        cls,
        key: str,
        values: Sequence[Any],
        max_len: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ) -> list[Any] | None:
        """Append many values to a list, trim it, and optionally refresh TTL."""
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
    async def llen(cls, key: str) -> int:
        """Return the length of a Redis list."""
        redis = cls.get_client()
        return await _await_if_needed(redis.llen(key))

    @classmethod
    async def set(cls, key: str, value: Any, ex: Optional[int] = None) -> bool:
        """Set a Redis string value with an optional expiry."""
        redis = cls.get_client()
        return await _await_if_needed(redis.set(key, value, ex=ex))

    @classmethod
    async def get(cls, key: str) -> Any | None:
        """Get a Redis string value."""
        redis = cls.get_client()
        return await _await_if_needed(redis.get(key))

    @classmethod
    async def delete(cls, key: str) -> int:
        """Delete one Redis key."""
        redis = cls.get_client()
        return await _await_if_needed(redis.delete(key))

    @classmethod
    async def exists(cls, key: str) -> int:
        """Return Redis existence count for one key."""
        redis = cls.get_client()
        return await _await_if_needed(redis.exists(key))

    @classmethod
    async def expire(cls, key: str, seconds: int) -> bool:
        """Set a key expiry in seconds."""
        redis = cls.get_client()
        return await _await_if_needed(redis.expire(key, seconds))

    @classmethod
    async def touch_ttl(cls, keys: Sequence[str], ttl_seconds: int) -> list[Any] | None:
        """Refresh TTL on a group of keys using one Redis pipeline."""
        if not keys:
            return None
        ttl_seconds = cls.normalize_ttl(ttl_seconds)
        redis = cls.get_client()
        async with redis.pipeline() as pipe:
            for key in keys:
                pipe.expire(key, ttl_seconds)
            result = await pipe.execute()
        return result
