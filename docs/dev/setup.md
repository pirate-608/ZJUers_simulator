# 开发环境搭建指南

## 前置要求

- Python 3.11+
- Node.js 18+
- Docker / Docker Compose V2（推荐）
- PostgreSQL 15+ 与 Redis 7+（仅纯宿主机开发时需要手动准备）

## Docker 开发/部署（推荐）

1. 准备 `.env`：

```bash
cp .env.template .env
```

关键变量：

```ini
ENVIRONMENT=development
SECRET_KEY=your-secret
DATABASE_URL=postgresql+asyncpg://zju:password@db:5432/zjus
POSTGRES_PASSWORD=password
ADMIN_USERNAME=admin
ADMIN_PASSWORD=strong-password
ADMIN_SESSION_SECRET=admin-session-secret
INVITE_CODES=LOCAL_TEST_CODE,ANOTHER_CODE
LLM_API_KEY=optional
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM=your-model
MINIMAX_API_KEY=optional
MINIMAX_MODEL=M2-her
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
```

2. 从项目根目录启动：

```bash
docker compose up -d --build
```

本地开发应保留 `docker-compose.override.yml`；它会把后端映射到宿主机 `127.0.0.1:8000`。生产基础 `docker-compose.yml` 不发布后端端口，只允许 Nginx 通过 Docker 内网访问 `backend:8000`。

生产环境下后端默认关闭 SQL echo，并跳过 `Base.metadata.create_all`；数据库结构由 `migrate` 服务执行 Alembic 迁移。若确需覆盖，可设置 `DATABASE_ECHO` 或 `CREATE_ALL_ON_STARTUP`，但常规生产不建议开启。

该命令会构建并启动：

- PostgreSQL + pgvector
- Redis
- `migrate`（Alembic）
- `seed_embeddings`
- FastAPI backend
- Nginx frontend

3. 常用命令：

```bash
docker compose logs -f backend
docker compose down
docker compose down -v
```

## 前后端分离开发

如果要调试前端热更新，推荐仍用 Docker 起底座：

```bash
docker compose up -d db redis migrate seed_embeddings backend
```

然后进入前端目录：

```bash
cd zjus-frontend
npm install
npm run dev
```

Vite 会把 `/api`、`/ws`、`/world` 代理到后端。

## 纯宿主机开发

纯宿主机开发需要自己启动 PostgreSQL、Redis，并确保 `.env` 使用 localhost 地址。详细步骤见[原生部署指南](../user/local_deploy_bare.md)。

后端常用命令：

```bash
cd zjus-backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## OpenAPI 类型生成

后端 API 变更后，先用根目录 Docker Compose 启动后端，等待 `/openapi.json` 可访问，再生成前端类型：

```powershell
docker compose up -d --build backend
$openapi = $null
for ($i = 0; $i -lt 30; $i++) {
    try {
        $openapi = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json
        if ($openapi.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $openapi -or $openapi.StatusCode -ne 200) {
    throw "Backend did not serve /openapi.json in time."
}
cd zjus-frontend
.\node_modules\.bin\openapi-typescript.cmd http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

上述 `127.0.0.1:8000` 来自本地 `docker-compose.override.yml` 的端口映射；在生产基础 compose 中后端不会暴露到宿主机。

不要手写 `src/types/api.generated.ts`；如果类型不对，先修后端 Pydantic/FastAPI 契约再重新生成。前端 HTTP 调用封装放在 `src/api/client.ts`，保持手写薄封装。

## 本地预构建资产流程

当前内容链路为“离线预构建 + 运行时检索”。更新世界设定时，需要维护两类资产：

1. 事件库/CC98 JSON 库。
2. 角色向量 CSV + 查询向量 JSON。

### 生成事件库与 CC98 库

`zjus-backend/scripts/generate_content_library.py` 使用 OpenAI SDK 的兼容 `chat/completions` 接口。文本模型可以是云端兼容端点，也可以是本地 Ollama 的 OpenAI 兼容端点；角色向量仍由下一节的本地 Ollama `bge-m3` 单独生成。

云端模型示例：

```bash
cd zjus-backend
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1 \
OPENAI_API_KEY=your-api-key \
OPENAI_API_MODEL=qwen-plus \
python scripts/generate_content_library.py --events 300 --cc98 500
```

本地 Ollama 文本模型示例：

```bash
cd zjus-backend
OPENAI_API_BASE=http://localhost:11434/v1 \
OPENAI_API_KEY=ollama \
OPENAI_API_MODEL=qwen3.5:4b \
python scripts/generate_content_library.py --events 300 --cc98 500
```

如果目标端点不支持 `response_format={"type":"json_object"}`，可加 `--no-json-mode`，脚本仍会从普通文本中提取 JSON。

CC98 帖子生成会按 `positive / neutral / negative` 三类尽量均衡产出；生产库发布前仍建议抽样检查正负反馈比例，避免算法模式体感过于惩罚。

输出：

- `world/event_library.json`
- `world/cc98_library.json`

### 导出角色向量

先启动 Ollama 并安装 `bge-m3`：

```bash
ollama serve
ollama pull bge-m3
```

再执行：

```bash
cd zjus-backend
python scripts/embed_world_data.py --csv-only
```

输出：

- `world/query_embeddings.json`
- `world/character_embeddings.csv`

### 部署时导入 pgvector

`docker compose up -d` 已包含启动顺序：

```text
migrate -> seed_embeddings -> backend
```

如需手动导入：

```bash
cd zjus-backend
python scripts/import_character_embeddings.py
```

## Alembic 迁移

生成迁移：

```bash
docker compose run --rm migrate alembic revision --autogenerate -m "message"
```

应用迁移：

```bash
docker compose up -d migrate
```

## 测试与检查

后端：

```bash
cd zjus-backend
python -m pytest
python -m ruff format .
python -m ruff check --fix .
```

前端：

```bash
cd zjus-frontend
npm run type-check
npm test
```

## 测试账户与安全

- 默认无内置玩家账户。
- 登录必须使用 `.env` 中的 `INVITE_CODES`。
- 新玩家首次登录会生成长期学生凭证。
- 管理后台账号由 `ADMIN_USERNAME` / `ADMIN_PASSWORD` 控制。
- `/admin/balance` 可图形化调整 `world/game_balance.json` 的既有数值项，保存后热重载并记录审计日志；该页面不修改玩家 API，也不需要 OpenAPI 生成或 Alembic 迁移。
- 生产务必使用强随机的 `SECRET_KEY`、`ADMIN_PASSWORD`、`ADMIN_SESSION_SECRET`。
