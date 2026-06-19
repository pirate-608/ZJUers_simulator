# 项目接手研究报告

> 本页用于新接手开发时快速建立全局上下文。它记录当前架构、合同边界、验证基线和后续改动默认策略。

## 当前系统画像

ZJUers Simulator 是一个 Vue 3 + FastAPI 的校园模拟文字游戏。前端负责玩家入口、存档选择、角色创建、实时仪表盘和弹窗；后端负责认证、WebSocket 游戏循环、Redis 实时状态、PostgreSQL 持久化存档、世界观数据加载和内容生成降级。

当前玩家入口流程为：

```text
login -> save_select -> character_create -> loading -> playing -> ended
```

首次访问站点时，前端会在上述 `GamePhase` 流程前播放一次可跳过的登录前序章，并用 `localStorage.zjus_prologue_seen_v1` 记录已看过；序章期间不执行登录分流，也不建立 WebSocket。

没有入学考试或招生考试流程。新玩家通过邀请码登录后选择专业并分配 `IQ` / `EQ` / `Luck`；老玩家通过昵称、邀请码和长期学生凭证登录后选择已有存档或新开一局。

## 关键合同

### 玩家入口与存档

- `POST /api/auth` 只接收昵称、邀请码和可选长期学生凭证；新用户返回 JWT 与 `user_token`，老用户返回 JWT 与存档摘要。
- `POST /api/init_character` 校验 `IQ` / `EQ` / `Luck` 每项 `50-150`，总和必须为 `250`；专业 IQ 加成在服务端初始化时额外叠加。
- WebSocket 首条消息必须携带 `{ token }`，可选 `load_save_slot`、会话级 `custom_llm_*` 字段和钉钉 RP 专用 `custom_rp_api_key`。
- 指定 `load_save_slot` 时，后端必须强制从 PostgreSQL 存档恢复；存档不存在则返回 `auth_error`。
- `auth_ok` 只表示连接可用，前端不应自动发送 `resume`；后端在上下文初始化完成后启动引擎。

### 游戏引擎与状态

- `GameEngine` 负责 tick、暂停/恢复、期末考试、学期推进、随机事件、休闲冷却、反馈弹窗、毕业和 Game Over。
- Redis 是单局实时状态源，PostgreSQL 是持久化存档源；保存/学期推进通过 `SaveService.persist_to_db()` upsert。
- `init` 与 `tick` 都应携带 `relax_cooldowns`，前端据此禁用休闲按钮并显示剩余秒数；`init` 还会携带 `items_state`，购买/出售后通过独立 `items_state` 消息同步。
- 道具配置来自 `world/items.json`，背包在 Redis `items_state` 与 `game_saves.items_data` 间同步。道具持有即生效，但加成作为 effective stats 计算，不直接写入基础属性。
- 随机事件和休闲结果同时保留 `event` 日志，并通过 `feedback` 展示短时弹窗。
- 新学期切换重置课程和学期计时，并将精力向 100 回调一半，保留经营压力但避免低精力锁死。

### 内容生成

- 内容模式为 `library`、`hybrid`、`ai`。
- 事件和 CC98 优先使用本地预构建 JSON 库；离线生成脚本 `zjus-backend/scripts/generate_content_library.py` 使用 OpenAI-compatible `chat/completions`，可指向云端模型或 Ollama `/v1`，而角色/query 向量仍由本地 Ollama `bge-m3` 生成。
- 钉钉消息默认优先走 pgvector 角色检索 + MiniMax M2-her；若玩家提供 `custom_rp_api_key`，使用玩家 MiniMax key 调用 M2-her；若玩家只配置通用自定义 LLM，则不再使用平台默认 M2-her，而是回退到通用自定义 LLM。联系人私聊状态随存档保存，三次玩家回复后结算一轮数值影响。
- AI/LLM 不可用时，AI 模式要向 hybrid/library 降级，并通过 `mode_changed` 或 `toast` 告知前端。
- 用户自定义 LLM 配置只在浏览器 `sessionStorage` 和当前 WebSocket 会话中使用，不落库。

## 运行与验证基线

接手基线在 Windows 工作区验证如下：

| 检查 | 命令 | 当前结果 |
|---|---|---|
| 后端单元测试 | `..\.venv\Scripts\python.exe -m pytest tests\unit` | `76 passed` |
| 后端引擎语法 | `..\.venv\Scripts\python.exe -m py_compile app\game\engine.py` | 通过 |
| 前端类型检查 | `.\node_modules\.bin\vue-tsc.cmd --noEmit` | 通过 |
| 前端单测 | `.\node_modules\.bin\vitest.cmd run` | `3 passed` |
| 文档构建 | `cd docs; npm run build` | 通过 |

当前本地 `.venv` 如果缺少 `ruff`，先安装后端 `requirements.txt`，再运行 `python -m ruff check .`。pytest 可能出现 Pydantic v2 `Config` 弃用警告或本地 `.pytest_cache` 写入警告，这些不是当前功能失败。

## 后续开发默认策略

- 后端集成、迁移和 OpenAPI 生成使用根目录 Docker Compose，不用裸 `uvicorn` 做集成验证。
- 后端 HTTP 模型或路由变化后，启动 Docker Compose 后端，等待 `/openapi.json` 可访问，再重新生成 `zjus-frontend/src/types/api.generated.ts`；不要手写生成文件，`src/api/client.ts` 保持手写薄封装。
- 入口流、WebSocket 合同、存档结构、Redis 快照或内容生成模式变更后，同步更新 `docs/dev/api.md`、前后端框架文档和相关用户文档。
- 涉及玩家入口或 UI 行为时，增加 focused tests 或浏览器 smoke，至少覆盖登录、存档选择、角色创建、WebSocket 消息分发、暂停/引导和反馈弹窗。
- 世界观数据位于 `zjus-backend/world/`，它既是游戏运行数据，也是文档和内容生成的产品表面；改数据时同步检查文档引用。
