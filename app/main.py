from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
templates = Jinja2Templates(directory="templates")
from app.core.config import settings
from app.core.database import engine, Base
from app.api import auth, game

app = FastAPI(title=settings.PROJECT_NAME)

# 挂载 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(game.router)

# 挂载静态资源 (确保 static 目录在根目录下)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 页面路由
# 页面路由
@app.get("/")
async def read_index():
    return FileResponse("templates/index.html")

@app.get("/dashboard.html")
async def read_dashboard():
    return FileResponse("templates/dashboard.html")

# 补充录取通知书路由
@app.get("/admission")
async def read_admission(request: Request):
    return templates.TemplateResponse("admission.html", {"request": request})

# 启动事件：快速初始化数据库表 (开发用，生产建议用 Alembic)
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)