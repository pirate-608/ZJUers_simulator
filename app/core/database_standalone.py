"""
单机版数据库配置（SQLite）
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config_standalone import standalone_settings

# 创建 SQLite 异步引擎
engine = create_async_engine(
    standalone_settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},  # SQLite 特定配置
)

# 创建会话工厂
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


async def get_db():
    """数据库会话依赖注入"""
    async with AsyncSessionLocal() as session:
        yield session
