# 开发环境搭建指南

## 前置要求
- Python 3.11+
- Docker / Docker Compose（推荐）
- PostgreSQL 15+，Redis 7+

## 本地开发（非 Docker）
1. 复制配置模板，设置环境变量（.env）
   ```bash
   cp .env.example .env  # 如无模板，可手动创建
   # 关键变量
   # DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/zjuers
   # SECRET_KEY=xxxx
   # ADMIN_PASSWORD=xxxx
   # ADMIN_SESSION_SECRET=xxxx
   # LLM_API_KEY=可选
   # LLM_BASE_URL=可选
   # LLM=可选默认模型名
   ```
2. 安装依赖
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. 数据库准备
   ```bash
   createdb zjuers  # 或使用 psql/GUI 创建
   alembic upgrade head
   ```
4. 运行服务
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   如果需要运行前端，可以进入`zjus-frontend`目录，然后运行`npm run dev`
5. 访问
   - 前端：`http://localhost:3000`
   - API 文档：`http://localhost:8000/docs`

## Docker 开发/部署 (推荐)
1. 准备 `.env`（同上，务必填写安全密钥与数据库密码）。
2. Docker Compose 方式：
   - **生产环境拉起**：
     ```bash
     docker compose up -d
     ```
     （注意：线上环境不再需要本地 build，`docker-compose.yml` 默认拉取线上的预构建镜像 `pirate608/zjus-backend` 和 `pirate608/zjus-frontend`）。
   - **本地热更新开发拉起**：
     如果你要修改代码并实时预览，运行：
     ```bash
     docker compose up -d --build
     ```
     （本地存在 `docker-compose.override.yml`，这会让 Docker 自动在本地重新 build 前后端，并挂载对应目录以支持热更新）。
3. 纯宿主机开发（Vue Vite + Uvicorn）：
   推荐前后端分离启动，获得最极致的热更新体验。具体细节请参考 [纯宿主机本地部署指南](../user/local_deploy_bare.md)。
4. 查看日志
   ```bash
   docker compose logs -f backend
   docker compose logs -f migrate
   ```
5. 停止/清理
   ```bash
   docker compose down
   ```

## Alembic 迁移操作
*注：使用默认的配置文件启动docker后，会自动执行一次数据库迁移*

手动迁移：
- 生成迁移：
  ```bash
  docker compose run --rm migrate alembic revision --autogenerate -m "add_xxx"
  ```
- 应用迁移：
  ```bash
  docker compose up -d migrate
  # 或本地：alembic upgrade head
  ```

## 测试账户与安全
- 默认无内置账户；考试通过后会生成用户凭证 token。
- 管理后台管理员凭证由环境变量 `ADMIN_USERNAME`/`ADMIN_PASSWORD` 决定。
- 生产务必使用强随机的 SECRET_KEY、ADMIN_PASSWORD、ADMIN_SESSION_SECRET。

## 目录速览
- 后端：`zjus-backend/app/`
- 前端 (Vue3)：`zjus-frontend/src/`
- 世界/数值数据：`zjus-backend/world/`
- 反代与证书：`nginx/`

## 常见问题
- **启动提示默认密钥不安全**：检查 .env 是否被正确加载到容器（compose 中已使用 `env_file`）。
- **WS 连接失败**：确认 Nginx 已配置 `/ws/` 升级，前后端协议一致（http+ws / https+wss）。
- **数据库连不上**：确认 `DATABASE_URL` 使用 asyncpg 驱动前缀 `postgresql+asyncpg://`。