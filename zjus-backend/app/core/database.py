"""Async SQLAlchemy engine and session factory.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The production path expects Alembic migrations; optional metadata creation is
kept for explicitly configured local/bootstrap scenarios only.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


def _is_production() -> bool:
    return settings.ENVIRONMENT.lower() in {"production", "prod"}


def _database_echo_enabled() -> bool:
    if settings.DATABASE_ECHO is not None:
        return settings.DATABASE_ECHO
    return not _is_production()


engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=_database_echo_enabled(),
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for SQLAlchemy ORM models."""

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session
