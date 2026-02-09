# ZJUers Simulator 框架说明

## 架构总览
- **后端**：FastAPI + SQLAlchemy Async + Redis。WebSocket 用于实时游戏交互，HTTP 提供考试、认证、配置接口。
- **前端**：静态 HTML + Bootstrap + 原生 JS。通过 REST 完成登录/考试，WebSocket 传输游戏状态与事件。
- **存储**：
  - PostgreSQL：用户/存档/管理后台数据（异步驱动 asyncpg）。
  - Redis：游戏实时状态与缓存（事件池、CC98 帖子池、TTL 管理）。
- **反向代理**：Nginx 终止 TLS，转发 HTTP/WebSocket。
- **LLM 集成**：OpenAI 兼容接口；支持会话级自定义模型与密钥（前端传入，不落库）。
- **部署**：Docker 多容器（backend/db/redis/nginx/migrate），Alembic 负责数据库迁移。

## 代码目录
- `app/`
  - `main.py`：FastAPI 入口，路由注册、静态文件挂载、全局心跳启动。
  - `api/`：HTTP 路由（exam/auth/assign_major）、WebSocket 路由（game）。
  - `game/`：游戏引擎、状态、数值配置适配。
  - `core/`：配置、数据库、事件、LLM 适配、权限安全。
  - `models/`：SQLAlchemy ORM 模型（User、GameSave、Admin 相关）。
  - `services/`：游戏、存档、限制、世界数据服务。
  - `repositories/`：Redis 数据读写封装。
  - `websockets/`：连接管理器（心跳、广播、重复连接剔除）。
- `static/`：前端 JS/CSS、WebSocket 客户端、考试逻辑。
- `templates/`：Jinja2 页面（index/admission/dashboard 等）。
- `world/`：游戏世界配置、课程数据、事件关键词等。
- `nginx/`：反向代理与 WebSocket 配置。
- `alembic/`：迁移脚本与环境。
- `docker-compose.yml`：多容器编排（含 migrate 服务）。

## 数据流
1. **入学考试/登录**：前端调用 `/api/exam/questions` → `/api/exam/submit` 或 `/api/exam/quick_login`，获取 JWT。
2. **分配专业**：持 JWT 调用 `/api/assign_major`，生成初始存档并回写 Redis。
3. **游戏连接**：前端发起 WebSocket `/ws/game`，首条消息携带 JWT（及可选自定义 LLM）。后端验证、加载 Redis 状态、启动引擎循环。
4. **实时交互**：客户端发送 action（ping/save/exit/操作指令）；服务器推送 tick、事件、通知。
5. **存档**：显式保存或退出时持久化到 PostgreSQL；Redis 作为运行态缓存。

## 配置与安全
- 必填环境：`DATABASE_URL`（asyncpg）、`SECRET_KEY`、`ADMIN_PASSWORD`、`ADMIN_SESSION_SECRET`。
- 可选环境：`LLM_API_KEY`、`LLM_BASE_URL`、`LLM`（默认模型名）。
- 启动安全校验：`app/core/config.py` 检测默认弱密钥，生产禁止启动。
- HTTPS：生产建议在 Nginx 层启用 TLS；WebSocket 通过 `wss` 转发。

## 迁移与部署
- 迁移：`docker compose run --rm migrate alembic revision --autogenerate -m "msg"` 生成脚本，`docker compose up -d migrate` 或 `alembic upgrade head` 应用。
- 启动：`docker compose up -d --build`（migrate 完成后 backend 启动）。
- 日志：`docker compose logs -f backend`。

## 会话级自定义 LLM
- 用户在登录页输入自定义模型/API Key，仅存于浏览器会话（sessionStorage），不落库。
- WebSocket 首条消息携带该配置；后端仅在本次连接使用，失败则回退默认模型。

## 心跳与连接管理
- 全局心跳任务每 30s 清理超时 WebSocket；重复登录会踢旧连接。
- 前端心跳 `ping` 间隔 25s，后端回复 `pong` 并刷新 TTL。

## 已知关键配置
- WebSocket 代理：`nginx/conf.d/default.conf` 已开启 `/ws/` 升级头。
- Tick 间隔：3s；消息限流：最小间隔 50ms；Redis 玩家 TTL 默认 24h（可在 config 中调整）。
