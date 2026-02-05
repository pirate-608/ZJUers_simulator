"""
单机版缓存配置（fakeredis）
"""

import fakeredis.aioredis
from app.core.config_standalone import standalone_settings

# 创建 fakeredis 异步客户端（纯内存）
redis_client = fakeredis.aioredis.FakeRedis(decode_responses=True, encoding="utf-8")


async def get_redis():
    """获取 Redis 客户端"""
    return redis_client


async def close_redis():
    """关闭 Redis 连接（fakeredis 无需真正关闭）"""
    pass
