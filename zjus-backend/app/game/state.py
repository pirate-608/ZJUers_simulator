"""Redis-backed low-level state access helpers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
This compatibility layer wraps Redis hash operations used by older game-state
paths and keeps async/sync Redis client stubs testable.
"""

import inspect
import logging
from typing import Any, Awaitable, Dict, TypeVar

from app.api.cache import RedisCache
from app.core.input_safety import safe_username_for_prompt
from app.repositories.redis_repo import RedisRepository
from app.schemas.game_state import PlayerStats

logger = logging.getLogger(__name__)
T = TypeVar("T")


async def _await_if_needed(value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


class RedisState:
    """Compatibility facade over `RedisRepository`.

    New game-state code should prefer `RedisRepository` directly. This facade
    remains for auth/startup helpers and older call sites that expect a compact
    state object.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.redis = RedisCache.get_client()
        self.repo = RedisRepository(self.user_id, self.redis)
        self.key = f"player:{user_id}:stats"

    @classmethod
    async def cleanup_orphan_player_keys(cls, ttl_seconds: int, delete: bool = False):
        """Ensure legacy player keys have TTL; optionally delete them."""
        redis = RedisCache.get_client()
        ttl_seconds = RedisCache.normalize_ttl(ttl_seconds)

        cursor = 0
        scanned = 0
        fixed = 0

        while True:
            cursor, keys = await _await_if_needed(
                redis.scan(cursor=cursor, match="player:*", count=200)
            )
            if keys:
                scanned += len(keys)
                for key in keys:
                    ttl = await _await_if_needed(redis.ttl(key))
                    if ttl == -1:
                        if delete:
                            await _await_if_needed(redis.delete(key))
                        else:
                            await _await_if_needed(redis.expire(key, ttl_seconds))
                        fixed += 1
            if cursor == 0:
                break

        if fixed > 0:
            logger.info(
                "Redis cleanup updated %s/%s legacy keys with no TTL", fixed, scanned
            )

    async def clear_all(self):
        """Delete all active Redis data for this player."""
        await self.repo.delete_all()

    async def close(self):
        """Compatibility no-op for callers that used to close per-state clients."""
        pass

    async def exists(self) -> bool:
        """Return whether the legacy stats key exists."""
        return await _await_if_needed(self.redis.exists(self.key)) > 0

    async def init_game(self, username: str) -> Dict[str, Any]:
        """Initialize only the base player stats for a new session."""
        safe_username = safe_username_for_prompt(username)
        initial_stats = PlayerStats.build_initial(username=safe_username).model_dump()
        await self.repo.set_game_data(initial_stats)
        return initial_stats

    async def get_stats(self) -> Dict[str, str]:
        """Return raw Redis stats for legacy callers."""
        return await _await_if_needed(self.redis.hgetall(self.key))

    async def get_stats_typed(self) -> Dict[str, Any]:
        """Return registry-repaired player stats for legacy callers."""
        raw = await _await_if_needed(self.redis.hgetall(self.key))
        return PlayerStats.from_redis(raw).model_dump()
