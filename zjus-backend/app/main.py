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

# 初始化结构化日志（必须在使用 logger 前调用）
setup_logging(environment=settings.ENVIRONMENT)

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SESSION_SECRET)

# 挂载 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(game.router)

setup_admin(app)

# 新增：公开 world 目录为静态资源
app.mount("/world", StaticFiles(directory="world"), name="world")


def _create_all_on_startup() -> bool:
    if settings.CREATE_ALL_ON_STARTUP is not None:
        return settings.CREATE_ALL_ON_STARTUP
    return settings.ENVIRONMENT.lower() not in {"production", "prod"}


# 启动事件：快速初始化数据库表 (开发用，生产建议用 Alembic)
@app.on_event("startup")
async def startup():
    if _create_all_on_startup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        logger.info("Skipping Base.metadata.create_all in production startup")

    try:
        await RedisState.cleanup_orphan_player_keys(settings.REDIS_PLAYER_TTL_SECONDS)
    except Exception as e:
        logger.warning("Redis startup cleanup skipped: %s", e)

    # 启动全局心跳检测（单例任务）
    manager.start_heartbeat_checker()
    logger.info("Global heartbeat checker registered at startup")


@app.on_event("shutdown")
async def shutdown():
    try:
        from app.core.dingtalk_llm import close_m2her_client

        await close_m2her_client()
    except Exception as e:
        logger.warning("M2-her client shutdown skipped: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
