"""FastAPI application factory and process-level startup hooks.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
This module mounts HTTP routers, admin UI, static world data, and optional
startup tasks for migrations-free local development.
"""

import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.admin import setup_admin
from app.api import auth, game
from app.core.config import settings
from app.core.database import Base, engine
from app.core.logging_config import setup_logging
from app.game.state import RedisState
from app.models import admin as admin_models
from app.models import game_save as game_save_model
from app.models import user as user_model
from app.websockets.manager import manager

_MODEL_MODULES = (admin_models, game_save_model, user_model)

# Logging must be configured before modules start emitting startup records.
setup_logging(environment=settings.ENVIRONMENT)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SESSION_SECRET)

app.include_router(auth.router, prefix="/api")
app.include_router(game.router)

setup_admin(app)

# Public world data is intentionally exposed for developer reference.
app.mount("/world", StaticFiles(directory="world"), name="world")


def _create_all_on_startup() -> bool:
    """Return whether startup should create tables without Alembic."""
    if settings.CREATE_ALL_ON_STARTUP is not None:
        return settings.CREATE_ALL_ON_STARTUP
    return settings.ENVIRONMENT.lower() not in {"production", "prod"}


@app.on_event("startup")
async def startup():
    """Run process-level startup hooks."""
    if _create_all_on_startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        logger.info("Skipping Base.metadata.create_all in production startup")

    try:
        await RedisState.cleanup_orphan_player_keys(settings.REDIS_PLAYER_TTL_SECONDS)
    except Exception as e:
        logger.warning("Redis startup cleanup skipped: %s", e)

    manager.start_heartbeat_checker()
    logger.info("Global heartbeat checker registered at startup")


@app.on_event("shutdown")
async def shutdown():
    """Close shared outbound clients during application shutdown."""
    try:
        from app.core.dingtalk_llm import close_m2her_client
        from app.core.llm import close_llm_clients

        await close_m2her_client()
        await close_llm_clients()
    except Exception as e:
        logger.warning("LLM client shutdown skipped: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
