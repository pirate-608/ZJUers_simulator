"""FastAPI dependency providers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
This module exposes shared async database/session dependencies used by the
HTTP routers and admin views.
"""

from typing import AsyncGenerator

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.cache import RedisCache
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.redis_repo import RedisRepository
from app.services.game_service import GameService
from app.services.save_service import SaveService
from app.services.world_service import WorldService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session for one request scope."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> Redis:
    """Return the shared async Redis client."""
    return RedisCache.get_client()


def get_settings():
    """Return process-wide application settings."""
    return settings


async def get_current_user_info(token: str) -> dict:
    """Decode user identity from a JWT for HTTP and WebSocket entry points."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_raw = payload.get("sub")
        if not isinstance(user_id_raw, str) or not user_id_raw:
            raise JWTError("Invalid user_id")
        username_raw = payload.get("username")
        return {
            "user_id": user_id_raw,
            "username": str(username_raw) if username_raw is not None else user_id_raw,
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from None


def get_world_service() -> WorldService:
    """Create a world-data service instance."""
    return WorldService()


def get_redis_repo(
    user_info: dict = Depends(get_current_user_info),
    redis: Redis = Depends(get_redis),
) -> RedisRepository:
    """Build a Redis repository scoped to the authenticated user."""
    return RedisRepository(user_info["user_id"], redis)


def get_game_service(
    user_info: dict = Depends(get_current_user_info),
    repo: RedisRepository = Depends(get_redis_repo),
    world: WorldService = Depends(get_world_service),
) -> GameService:
    """Build the game service for the authenticated user."""
    return GameService(user_info["user_id"], repo, world)


def get_save_service() -> SaveService:
    """Build the save service dependency."""
    return SaveService()
