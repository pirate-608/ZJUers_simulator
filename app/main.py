from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
from app.core.config import settings
import logging
from starlette.middleware.sessions import SessionMiddleware
from app.core.database import engine, Base
from app.api import auth, game
from app.models.user import User
from app.models.game_save import GameSave
from app.models.admin import UserRestriction, UserBlacklist, AdminAuditLog
from app.game.state import RedisState
from app.admin import setup_admin
from app.websockets.manager import manager

templates = Jinja2Templates(directory="templates")

logger = logging.getLogger(__name__)

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(SessionMiddleware, secret_key=settings.ADMIN_SESSION_SECRET)

# 挂载 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(game.router)

setup_admin(app)

# 挂载静态资源 (确保 static 目录在根目录下)
app.mount("/static", StaticFiles(directory="static"), name="static")
# 新增：公开 world 目录为静态资源
app.mount("/world", StaticFiles(directory="world"), name="world")


# 页面路由
@app.get("/")
async def read_index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/dashboard.html")
async def read_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/admission")
async def read_admission(request: Request):
    return templates.TemplateResponse("admission.html", {"request": request})


@app.get("/end")
async def read_end(request: Request):
    return templates.TemplateResponse("end.html", {"request": request})


# 启动事件：快速初始化数据库表 (开发用，生产建议用 Alembic)
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        await RedisState.cleanup_orphan_player_keys(settings.REDIS_PLAYER_TTL_SECONDS)
    except Exception as e:
        logger.warning("Redis startup cleanup skipped: %s", e)

    # 启动全局心跳检测（单例任务）
    manager.start_heartbeat_checker()
    logger.info("Global heartbeat checker registered at startup")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
