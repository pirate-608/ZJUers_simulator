# API 文档

当前后端入口分为两类：

- HTTP API：认证、角色初始化、配置查询。
- WebSocket：实时游戏循环、保存/退出、动作指令。

前端类型来源为后端 OpenAPI：`zjus-frontend/src/types/api.generated.ts`。该文件应从运行中的后端 `/openapi.json` 生成，不手写维护。

## 认证与角色初始化 (`app/api/auth.py`)

### POST `/api/auth`

作用：使用昵称 + 邀请码认证用户，并返回 WebSocket/HTTP 使用的 JWT。新用户会额外获得长期学生凭证；老用户需提供学生凭证。

请求体：

```json
{
  "username": "折大人",
  "invite_code": "INVITE_CODE",
  "token": "老玩家学生凭证，可选"
}
```

新用户响应：

```json
{
  "status": "new_user",
  "jwt": "<JWT>",
  "user_token": "<长期学生凭证>",
  "username": "折大人",
  "user_id": 1,
  "saves": []
}
```

老用户响应：

```json
{
  "status": "returning",
  "jwt": "<JWT>",
  "username": "折大人",
  "user_id": 1,
  "saves": [
    {
      "save_slot": 1,
      "major": "计算机科学与技术",
      "major_abbr": "CS",
      "semester": "大二春夏",
      "semester_idx": 4,
      "gpa": "3.7",
      "saved_at": "2026-05-28T16:30:00",
      "total_play_time": 0
    }
  ]
}
```

错误以 `status: "error"` 和 `message` 返回。常见原因包括邀请码无效、昵称被占用但未提供正确学生凭证、用户或凭证被黑名单限制。

### GET `/api/majors`

作用：返回 `world/majors.json` 中所有可选专业，供角色创建页展示。

响应：

```json
[
  {
    "name": "计算机科学与技术",
    "abbr": "CS",
    "iq_buff": 15,
    "stress_base": 25,
    "desc": "头发与薪资成反比，紫金港卷王聚集地"
  }
]
```

### POST `/api/init_character`

作用：新游戏初始化。玩家选择专业并分配 `IQ` / `EQ` / `Luck` 基础属性。

请求体：

```json
{
  "token": "<JWT>",
  "major_abbr": "CS",
  "iq": 100,
  "eq": 100,
  "luck": 50
}
```

服务端约束：

- `iq`、`eq`、`luck` 每项必须在 `50-150`。
- 三项总和必须等于 `250`。
- 专业 IQ 增益在 `GameService.assign_major_and_init()` 中额外叠加，不计入 250 点预算。

响应：

```json
{
  "success": true,
  "major": "计算机科学与技术",
  "major_abbr": "CS",
  "courses": []
}
```

### GET `/api/admission_info`

保留兼容接口，用于查询当前用户昵称、已分配专业和长期学生凭证。

认证：`Authorization: Bearer <JWT>`

响应：

```json
{
  "username": "折大人",
  "assigned_major": "计算机科学与技术",
  "token": "<长期学生凭证>"
}
```

## 游戏配置 (`app/api/game.py`)

### GET `/config`

作用：返回前端所需的数值平衡配置，包括学期时长、课程状态、冷却、tick 间隔等。

## WebSocket (`app/api/game.py`)

### 路径 `/ws/game`

连接建立后，客户端必须在 10 秒内发送首条鉴权消息。

新游戏/继续当前 Redis 状态：

```json
{
  "token": "<JWT>",
  "custom_llm_provider": "openai",
  "custom_llm_model": "gpt-4o-mini",
  "custom_llm_api_key": "sk-..."
}
```

加载指定持久化存档：

```json
{
  "token": "<JWT>",
  "load_save_slot": 1
}
```

鉴权通过后服务端会：

1. 检查账号限制。
2. 踢掉同用户旧连接。
3. 若提供 `load_save_slot`，从 `game_saves` 指定槽位恢复到 Redis。
4. 启动 `GameEngine` 与事件转发协程。
5. 推送 `auth_ok`、`init` 和当前 `dingtalk_state`。

`auth_ok` 只表示连接可用；后端会在 WebSocket 上下文初始化后启动 `GameEngine`。前端不应在 `auth_ok` 后主动发送 `resume`，否则可能破坏新手引导或手动暂停状态。

### 服务端消息

| 类型 | 说明 |
|---|---|
| `auth_ok` | 鉴权通过 |
| `auth_error` | JWT 无效、账号受限或选择的存档不存在 |
| `init` | 初始状态包：玩家属性、课程进度、课程策略、学期剩余时间、休闲动作冷却、钉钉状态 |
| `tick` | 高频状态更新，包含 `relax_cooldowns` |
| `event` | 事件日志 |
| `feedback` | 结果反馈弹窗，包含 `title`、`message`、`kind`、`auto_close_ms` |
| `random_event` | 随机事件弹窗 |
| `semester_summary` | 期末成绩单 |
| `dingtalk_state` | 钉钉联系人、私聊历史、未读数和待回复选项的全量状态 |
| `dingtalk_thread_update` | 单个钉钉联系人线程更新 |
| `dingtalk_effect` | 三次回复一轮后的钉钉对话结算 |
| `dingtalk_message` | 旧版钉钉单条消息格式，前端仅做兼容映射 |
| `new_semester` | 新学期课程载入 |
| `graduation` | 毕业结算 |
| `save_result` | 保存结果 |
| `exit_confirmed` | 不保存退出确认 |
| `mode_changed` / `toast` | 内容生成模式和提示 |

`relax_cooldowns` 为动作到剩余秒数的映射，例如：

```json
{
  "gym": 12,
  "game": 0,
  "walk": 0,
  "cc98": 7
}
```

`feedback` 用于随机事件结果和休闲动作结果。日志仍由 `event` 消息保留；前端应同时展示日志和弹窗。

钉钉联系人只在有消息后显示。可回复角色包括 `roommate`、`classmate`、`friend`、`teaching_assistant`、`teacher`、`crush`。玩家通过回复选项完成三次回复后，后端生成 NPC 第三条回复并结算本轮数值影响，影响字段只允许 `energy` / `sanity` / `stress` / `eq` / `luck` / `reputation`。

### 客户端动作

| 动作 | 说明 |
|---|---|
| `ping` | 心跳，刷新 Redis TTL |
| `start` / `pause` / `resume` | 游戏运行状态 |
| `get_state` | 请求当前状态 |
| `set_speed` | 调整倍速 |
| `change_course_state` | 切换课程策略 |
| `relax` | 健身、打游戏、散步、CC98 |
| `exam` | 期末考试结算 |
| `next_semester` | 进入下一学期 |
| `event_choice` | 随机事件选项 |
| `save_game` | 保存但不退出 |
| `save_and_exit` | 保存并退出，持久化后清 Redis |
| `exit_without_save` | 不保存退出，清 Redis |
| `set_mode` | 内容生成模式：`library` / `hybrid` / `ai` |
| `dingtalk_mark_read` | 标记指定钉钉联系人已读 |
| `dingtalk_reply` | 选择指定钉钉回复选项 |

## OpenAPI 类型生成

后端必须通过根目录 Docker Compose 启动后再生成前端 API 类型：

```bash
docker compose up -d --build backend
cd zjus-frontend
npx openapi-typescript http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

`api.generated.ts` 只保存后端契约类型；`src/api/client.ts` 是手写薄封装，负责调用 `fetch()` 并引用生成类型。

## 会话级自定义 LLM

- 前端登录时可填写 `custom_llm_provider` / `custom_llm_model` / `custom_llm_api_key`，但这些字段不发送给 `POST /api/auth`。
- 配置保存在浏览器 `sessionStorage`，并在 WebSocket 首条鉴权消息中传给后端。
- 后端只在当前 `GameEngine` 会话中使用 `llm_override`，不落库。
