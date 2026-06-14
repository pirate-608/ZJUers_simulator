# 2C2G 生产资源优化计划

## 状态

2026-06-08 已执行第一批不收紧并发的代码层优化。目标是在不改变玩家可感知手感的前提下，降低 2 核 2G 生产服务器的常驻日志、启动开销、重复 Redis 读取、静态文件 IO 和外部请求建连压力。

现阶段继续保留当前 HTTP API、WebSocket 合同、数据库结构、游戏 tick 节奏、随机事件概率和钉钉触发概率。数据库连接池、Redis 连接池、PostgreSQL `max_connections` 等并发收紧项暂缓。

## 已执行的第一批优化

- 生产环境默认关闭 SQLAlchemy SQL echo，可用 `DATABASE_ECHO` 显式覆盖。
- 生产环境默认跳过 `Base.metadata.create_all`，继续依赖 Compose 中的 `migrate` 服务执行 Alembic；开发环境默认保留 `create_all`。
- `GameEngine.run_loop` 复用同一 tick 已读取的 snapshot，并让 `check_and_trigger_gameover` 支持传入 stats，减少 tick 内重复 Redis snapshot 读取。
- `dingtalk_llm.py` 缓存 `characters.json`，`llm.py` 缓存 `keywords.json`，`GameEngine` 缓存 `achievements.json`。
- MiniMax M2-her 使用共享 OpenAI SDK 异步客户端，并在 FastAPI shutdown 时关闭，减少频繁创建客户端和建连成本。

## 优化方向

### 后端生产瘦身

- 将 SQLAlchemy `echo=True` 改为环境控制，生产默认关闭 SQL echo。（已执行）
- 新增数据库连接池环境参数，生产默认收紧为小池，例如 `pool_size=3`、`max_overflow=2`、`pool_timeout=10`、`pool_recycle=1800`、`pool_pre_ping=true`。（暂缓，属于并发收紧）
- Redis 连接池最大连接数改为环境变量控制，生产默认从固定 `20` 收敛到较小值，例如 `10`。（暂缓，属于并发收紧）

### 启动与数据库

- 生产环境跳过 `Base.metadata.create_all`，继续依赖 Compose 中的 `migrate` 服务执行 Alembic。（已执行）
- 保留开发环境自动 `create_all`，避免影响本地调试。
- PostgreSQL Compose 增加轻量生产参数，降低 `max_connections`、`work_mem`、`maintenance_work_mem` 等小机常驻内存风险。（暂缓，涉及并发与数据库运行参数）

### 游戏循环低风险优化

- 在 `GameEngine.run_loop` 内复用同一 tick 已读取的 snapshot，减少每 tick 重复 Redis `get_snapshot()` 调用。（已执行）
- `check_and_trigger_gameover` 增加可选 stats 入参，避免 tick 内额外读取；外部调用保持兼容。（已执行）
- 不改变 tick interval、学期时长、事件概率、推送消息结构或前端展示节奏。

### 静态数据与外部请求

- 给 `dingtalk_llm.py` 的 `characters.json` 加进程内缓存，避免每次联系人或回复查询重复读文件。（已执行）
- 给 `llm.py` 的 `keywords.json` 加进程内缓存。（已执行）
- 缓存 `achievements.json`，避免成就检查反复读文件。（已执行）
- MiniMax M2-her 使用共享 OpenAI SDK 异步客户端，并在 FastAPI shutdown 时关闭，减少频繁建连和文件描述符压力。（已执行）

### 生产 Compose

- 删除生产 `backend` 的 `./zjus-backend/app:/app/app` 挂载，避免宿主机源码覆盖 Docker Hub 镜像，也减少额外 bind mount 依赖。（暂缓，本阶段聚焦代码层优化）
- 保留 `./zjus-backend/world:/app/world` 和 Nginx `/world/` 挂载，因为 world 数据需要公开供参考和拉取。
- 基础 Compose 继续不发布后端宿主机 `8000`；本地 override 继续补回 `127.0.0.1:8000:8000`。

## 暂不执行

- 不降低 tick 频率。
- 不减少随机事件或钉钉触发概率。
- 不改变 WebSocket 消息结构或前端生成类型。
- 不修改数据库 schema，不新增迁移。
- 不引入本机模型推理或额外常驻服务。
- 暂不收紧数据库连接池、Redis 连接池或 PostgreSQL 最大连接数。

## 测试与验收

后端检查：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe -m py_compile app\core\database.py app\api\cache.py app\game\engine.py app\core\dingtalk_llm.py app\core\llm.py app\main.py
..\.venv\Scripts\python.exe -m ruff check app\core app\api app\game app\services app\repositories
```

Focused tests：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe -m pytest tests\unit\test_dingtalk_state.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_game_state.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_onboarding_flow.py
```

Compose 检查：

```powershell
docker compose -f docker-compose.yml config --no-interpolate
docker compose config --no-interpolate
```

验收点：

- 生产基础 Compose 中 `backend` 无宿主机 `8000` 发布。
- 后续执行 Compose 瘦身时，再验收生产基础 Compose 无 `./zjus-backend/app:/app/app` 挂载。
- 合并本地 override 后仍有 `127.0.0.1:8000:8000`，方便 OpenAPI 生成和前端代理。
- `migrate -> seed_embeddings -> backend -> nginx` 启动顺序正常。
- 首页、登录、进入游戏、保存、钉钉消息或降级路径 smoke 正常。
- 文档站构建 `cd docs; npm run build` 通过。

## 假设

- 当前优化目标是轻量生产，不追求高并发。
- 2C2G 服务器主要服务小规模活跃在线玩家；若在线人数上升，再考虑低资源模式或升级到 2C4G。
- `/world/` 目录继续公开，但 world 目录不得放密钥、真实用户数据或内部私密配置。
