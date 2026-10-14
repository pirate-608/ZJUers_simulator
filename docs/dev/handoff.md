# 项目接手研究报告

> 本页用于新接手开发时快速建立全局上下文。它记录当前架构、合同边界、验证基线和后续改动默认策略。

## 当前系统画像

ZJUers Simulator 是一个 Vue 3 + FastAPI 的校园模拟文字游戏。前端负责玩家入口、存档选择、角色创建、实时仪表盘和弹窗；后端负责认证、WebSocket 游戏循环、Redis 实时状态、PostgreSQL 持久化存档、世界观数据加载和内容生成降级。

当前玩家入口流程为：

```text
login -> save_select -> character_create -> loading -> playing -> ended
```

前端挂载后立即根据现有凭证、存档摘要和 `game_started` 执行入口分流。登录前序章已移至仓库根目录 `archive/prologue/`，不参与运行或构建；旧的 `localStorage.zjus_prologue_seen_v1` 标记不再读写。

没有入学考试或招生考试流程。新玩家通过邀请码登录后选择专业并分配 `world/stat_definitions.json` 中 `allocatable=true` 的初始属性；老玩家通过昵称、邀请码和长期学生凭证登录后选择已有存档或新开一局。

## 关键合同

### 玩家入口与存档

- `POST /api/auth` 只接收昵称、邀请码和可选长期学生凭证；新用户返回 JWT 与 `user_token`，老用户返回 JWT 与存档摘要。
- `POST /api/init_character` 校验 `world/stat_definitions.json` 中可分配属性的范围和总预算；当前默认 `IQ` / `EQ` / `Luck` / `魅力` 每项 `50-150`，总和必须为 `300`。请求体推荐使用 `stats` 映射，旧显式字段仍兼容；专业 IQ 加成在服务端初始化时额外叠加。
- WebSocket 首条消息必须携带 `{ token }`，可选 `load_save_slot`、会话级 `custom_llm_*` 字段和钉钉 RP 专用 `custom_rp_api_key`。
- 指定 `load_save_slot` 时，若 Redis 活跃状态的 `save_slot` 相同，优先复用活跃状态，避免重连倒退；否则等待该槽位后台写入后从 PostgreSQL 恢复，存档不存在则返回 `auth_error`。
- `auth_ok` 只表示连接可用，前端不应自动发送 `resume`；后端在上下文初始化完成后启动引擎。

### 游戏引擎与状态

- `GameEngine` 负责 tick、暂停/恢复、期末考试、学期推进、随机事件、休闲冷却、反馈弹窗、毕业和 Game Over。
- Redis 是单局实时状态源，PostgreSQL 是持久化存档源；运行时保存使用 `SaveService.schedule_save()` 捕获快照并按用户/槽位 FIFO upsert。写入使用独立 SQL session 与 12 秒期限，不因 socket 断开取消；自动保存失败只发 toast，不发手动保存的 `save_result`。
- `init` 与 `tick` 都应携带 `relax_cooldowns`，前端据此禁用休闲按钮并显示剩余秒数；`init` 还会携带 `items_state`，购买/出售后通过独立 `items_state` 消息同步。
- WebSocket 出站消息由 `ConnectionManager.send_personal_message()` 按用户串行发送；保存并退出成功路径应先发 `save_result(success=true)`，再发 `exit_confirmed`，随后清理 Redis 并关闭连接。
- 暂停只使用 `GameEngine.is_running`：为 `false` 时后端也会拒绝休闲、考试、事件选择、钉钉回复、道具买卖和课程策略变更；`next_semester` 仅在期末结算完成后允许。
- 属性定义来自 `world/stat_definitions.json`，前端属性元数据由 `scripts/sync_stat_definitions.py` 生成。HUD、右侧状态卡、角色创建、道具页和结局页应通过 `src/utils/statDisplay.ts` / `statDefinitions.generated.ts` 获取标签、默认值和范围，不再手写属性上限。道具配置来自 `world/items.json`，其 effect 字段必须通过属性定义允许；背包在 Redis `items_state` 与 `game_saves.items_data` 间同步。道具持有即生效，但加成作为 effective stats 计算，不直接写入基础属性。
- 随机事件和休闲结果同时保留 `event` 日志，并通过 `feedback` 展示短时弹窗；休闲结果应附带本次实际数值变化。
- 新学期切换重置课程和学期计时，并将精力向属性定义中的默认精力回调一半，保留经营压力但避免低精力锁死。
- 学期切换先准备课程，再用 Redis CAS 原子提交学期编号、课程、策略、时间、考试标记和假期状态；随后发送 `new_semester` / `tick`、排队自动保存并启动新循环，不等待 SQL/LLM。客户端携带可选 `expected_semester_idx`，保留成绩单直到确认，并在 5 秒后请求状态、15 秒后解除等待以便重试。
- 假期使用 `app/schemas/holiday.py`、`app/content/holiday_library.py` 与 `world/holiday_events.json`。状态 `pending -> ready -> resolved` 存在 Redis `holiday_state`，并以私有 `_holiday_state` 写入存档 stats JSON；假期选择的效果与 resolved 标记原子提交。`semester_summary` 同样保存在 Redis 与存档 `_semester_summary` 中，重连不重新考试。
- 期末考试同时维护单学期 GPA 和累计加权 GPA：`stats.gpa` 是累计 GPA，`highest_gpa` 是最高单学期 GPA，成绩单 payload 会携带本学期新解锁成就。

### 内容生成

- 内容模式为 `library`、`hybrid`、`ai`。
- 事件和 CC98 优先使用本地预构建 JSON 库；离线生成脚本 `zjus-backend/scripts/generate_content_library.py` 使用 OpenAI-compatible `chat/completions`，可指向云端模型或 Ollama `/v1`，而角色/query 向量仍由本地 Ollama `bge-m3` 生成。`--holidays N --append` 同时支持季节均分、严格效果校验、标题去重和原子批次检查点；不生成假期向量。
- 钉钉消息默认优先走 pgvector 角色检索 + MiniMax M2-her；若玩家提供 `custom_rp_api_key`，使用玩家 MiniMax key 调用 M2-her；若玩家只配置通用自定义 LLM，则不再使用平台默认 M2-her，而是回退到通用自定义 LLM。联系人私聊状态随存档保存，三次玩家回复后结算一轮数值影响，允许对魅力等社交属性产生轻量变化；联系人列表默认最多 12 位，并优先复用已结束轮次的旧联系人。
- AI/LLM 不可用时，AI 模式要向 hybrid/library 降级，并通过 `mode_changed` 或 `toast` 告知前端。
- 用户自定义 LLM 配置只在浏览器 `sessionStorage` 和当前 WebSocket 会话中使用，不落库；自定义 LLM 生成内容不进入全局 Redis 内容池，自定义 client 调用后即关闭。

## 运行与验证基线

接手基线在 Windows 工作区验证如下：

| 检查 | 命令 | 当前结果 |
|---|---|---|
| 后端单元测试 | `..\.venv\Scripts\python.exe -m pytest tests\unit` | `202 passed`（2026-10-14） |
| 后端引擎语法 | `..\.venv\Scripts\python.exe -m py_compile app\game\engine.py` | 通过 |
| 前端类型检查 | `.\node_modules\.bin\vue-tsc.cmd --noEmit` | 通过 |
| 前端单测 | `.\node_modules\.bin\vitest.cmd run` | `47 passed`（2026-10-14） |
| 文档构建 | `cd docs; npm run build` | 通过 |

当前检查使用虚拟环境中的 Ruff。Codex 沙箱中若 Python 导入或 Vite 原生进程遇到权限限制，应在批准后原样重跑，不据此判断用户环境损坏。

## 后续开发默认策略

- 后端集成、迁移和 OpenAPI 生成使用根目录 Docker Compose，不用裸 `uvicorn` 做集成验证。
- 后端 HTTP 模型或路由变化后，启动 Docker Compose 后端，等待 `/openapi.json` 可访问，再重新生成 `zjus-frontend/src/types/api.generated.ts`；不要手写生成文件，`src/api/client.ts` 保持手写薄封装。
- 入口流、WebSocket 合同、存档结构、Redis 快照或内容生成模式变更后，同步更新 `docs/dev/api.md`、前后端框架文档和相关用户文档。
- 涉及玩家入口或 UI 行为时，增加 focused tests 或浏览器 smoke，至少覆盖登录、存档选择、角色创建、WebSocket 消息分发、暂停/引导和反馈弹窗。
- 世界观数据位于 `zjus-backend/world/`，它既是游戏运行数据，也是文档和内容生成的产品表面；改数据时同步检查文档引用。
