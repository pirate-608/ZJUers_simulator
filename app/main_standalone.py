"""
单机版主程序入口
使用 SQLite + fakeredis，适合打包成独立可执行文件
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request
import sys
import webbrowser
import threading
import time
from pathlib import Path

# 单机版配置
from app.core.config_standalone import standalone_settings, get_base_path
from app.core.database_standalone import engine, Base

# 导入路由（需要修改以使用单机版数据库和缓存）
# 这里我们先导入原版，后续需要适配
from app.api import auth, game

app = FastAPI(title=standalone_settings.PROJECT_NAME)

# 获取资源路径
base_path = get_base_path()
static_path = base_path / "static"
templates_path = base_path / "templates"
world_path = base_path / "world"

# 创建模板引擎
templates = Jinja2Templates(directory=str(templates_path))

# 挂载 API 路由
app.include_router(auth.router, prefix="/api")
app.include_router(game.router)

# 挂载静态资源（确保资源文件存在）
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

if world_path.exists():
    app.mount("/world", StaticFiles(directory=str(world_path)), name="world")


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


# 自动打开浏览器
def open_browser():
    """延迟几秒后自动打开浏览器"""
    time.sleep(3)  # 等待服务器完全启动
    url = "http://localhost:8000"
    print(f"🌐 正在打开浏览器: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"⚠️  自动打开浏览器失败: {e}")
        print(f"请手动访问: {url}")


# 启动事件：初始化数据库
@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print(f"✅ 单机版启动成功！")
    print(f"📂 数据库路径：{standalone_settings.DATABASE_URL}")
    print(f"🌐 访问地址：http://localhost:8000")

    # 自动打开浏览器（在后台线程中）
    if standalone_settings.AUTO_OPEN_BROWSER:
        browser_thread = threading.Thread(target=open_browser, daemon=True)
        browser_thread.start()


# 关闭事件
@app.on_event("shutdown")
async def shutdown():
    print("👋 单机版正在关闭...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main_standalone:app",
        host="127.0.0.1",  # 单机版只监听本地
        port=8000,
        reload=False,  # 打包版本禁用热重载
    )
