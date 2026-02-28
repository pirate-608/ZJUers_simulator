from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.api.cache import RedisCache
from app.repositories.redis_repo import RedisRepository
from app.services.world_service import WorldService
from app.services.game_service import GameService
from app.services.save_service import SaveService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_redis() -> Redis:
    """获取 Redis 客户端"""
    return RedisCache.get_client()


def get_settings():
    """获取全局配置"""
    return settings


async def get_current_user_info(token: str) -> dict:
    """从 Token 解析用户信息 (适用于 HTTP 和 WS)"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if not user_id:
            raise JWTError("Invalid user_id")
        return {
            "user_id": user_id,
            "username": payload.get("username"),
            "tier": payload.get("tier"),
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        )


def get_world_service() -> WorldService:
    """WorldService 通常是全局单例或带缓存的实例"""
    return WorldService()


def get_redis_repo(
    user_info: dict = Depends(get_current_user_info),
    redis: Redis = Depends(get_redis),
) -> RedisRepository:
    """根据当前用户注入 Redis 仓库"""
    return RedisRepository(user_info["user_id"], redis)


def get_game_service(
    user_info: dict = Depends(get_current_user_info),
    repo: RedisRepository = Depends(get_redis_repo),
    world: WorldService = Depends(get_world_service),
) -> GameService:
    """注入游戏业务服务"""
    return GameService(user_info["user_id"], repo, world)


def get_save_service() -> SaveService:
    """注入存档服务"""
    return SaveService()
