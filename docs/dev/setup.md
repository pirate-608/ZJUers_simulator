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
       当前链路会在 `migrate` 后自动执行一次 `seed_embeddings`，将 `world/character_embeddings.csv` 导入 pgvector 表。
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

## 本地预构建资产流程（预构建检索模式必做）

当前内容链路已经从“运行时大模型全量生成”切换为“离线预构建 + 运行时检索”。
因此在本地开发或更新 world 设定时，需要先生成两类资产：

1. 事件库/CC98 JSON 库（本地 AI 生成）
2. 角色向量 CSV + 查询向量 JSON（本地向量化导出）

### 1) 运行本地 AI 生成 JSON 内容库

在 `zjus-backend` 目录执行：

```bash
python scripts/generate_content_library.py --events 300 --cc98 500
```

说明：
- 脚本会输出 `world/event_library.json` 与 `world/cc98_library.json`。
- API 配置来自环境变量：`OPENAI_API_BASE`、`OPENAI_API_KEY`、`OPENAI_API_MODEL`。
- 如只更新其中一类内容，可使用：
   - `python scripts/generate_content_library.py --events-only 300`
   - `python scripts/generate_content_library.py --cc98-only 500`

### 2) 运行向量化导出 CSV（本地 embedding）

先确保本机已启动 Ollama 并安装 `bge-m3`：

```bash
ollama serve
ollama pull bge-m3
```

然后在 `zjus-backend` 目录执行：

```bash
python scripts/embed_world_data.py --csv-only
```

说明：
- 该命令会导出：
   - `world/query_embeddings.json`（运行时检索查询向量）
   - `world/character_embeddings.csv`（角色 embedding 备份）
- 使用 `--csv-only` 时不会写数据库，适合本地预构建与提交资产。

### 3) 部署时导入 pgvector（本地/云端一致）

`docker compose up -d` 现在包含以下启动顺序：

1. `migrate`（执行 Alembic）
2. `seed_embeddings`（导入 `character_embeddings.csv` 到 `character_embeddings` 表）
3. `backend`（开始运行检索逻辑）

如需手动导入，可执行：

```bash
cd zjus-backend
python scripts/import_character_embeddings.py
```

### 4) 预构建资产检查清单

提交或发布前，请确认以下文件存在且为最新：

- `zjus-backend/world/event_library.json`
- `zjus-backend/world/cc98_library.json`
- `zjus-backend/world/query_embeddings.json`
- `zjus-backend/world/character_embeddings.csv`

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