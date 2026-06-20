# ZJUers Simulator 前端项目结构与逻辑总览

> **项目概览**：基于 Vue 3 + Vite + Pinia 构建的单页应用。前端负责邀请码登录、存档选择、角色创建、实时游戏界面和结局展示，通过 WebSocket 与后端游戏引擎同步状态。

---

## 目录结构

```text
zjus-frontend/src/
├── App.vue                  # Phase 路由中枢 + 全局 Toast/反馈弹窗挂载
├── api/
│   └── client.ts            # HTTP API 薄封装，类型来自 OpenAPI
├── data/
│   └── prologue.ts          # 登录前序章文本、图片映射和 localStorage key
├── types/
│   ├── api.generated.ts     # 从后端 /openapi.json 生成
│   ├── game.ts              # GamePhase, PlayerStats
│   ├── course.ts            # 课程类型
│   ├── modal.ts             # 弹窗数据类型
│   └── websocket.ts         # WsMessage + 工具函数
├── stores/
│   └── gameStore.ts         # Pinia 全局状态
├── composables/
│   └── useGameWebSocket.ts  # WebSocket 连接、鉴权、消息分发
├── data/
│   └── statDefinitions.generated.ts # 从后端属性定义生成的前端元数据
└── components/
    ├── PrologueScene.vue    # 首次访问登录前序章
    ├── LoginView.vue        # 邀请码登录 + 自定义通用/RP 模型配置
    ├── SaveSelect.vue       # 老玩家存档选择 / 新游戏入口
    ├── CharacterCreate.vue  # 专业选择 + 初始属性分配
    ├── TopNav.vue           # 保存/退出
    ├── HudBar.vue           # 顶部属性栏
    ├── CourseList.vue       # 课程列表 + 策略切换
    ├── MidPanel.vue         # 事件日志 + 钉钉联系人/私聊 + 道具背包
    ├── RightPanel.vue       # 属性面板 + 摸鱼动作 + 内容模式
    ├── EndScreen.vue        # 结局界面
    └── modals/              # 成绩单、随机事件、反馈、退出确认
```

---

## Phase 流程

`GamePhase` 当前为：

```ts
login | save_select | character_create | loading | playing | ended
```

登录前序章不是 `GamePhase`，而是 `App.vue` 启动时的前置 gate。首次访问会先渲染 `PrologueScene.vue`，播放或跳过后写入 `localStorage.zjus_prologue_seen_v1`，随后才执行下面的入口分流。

```mermaid
graph TD
    Login["login<br>邀请码登录"] -->|"new_user"| Create["character_create<br>选择专业/分配属性"]
    Login -->|"returning"| Saves["save_select<br>加载存档/新游戏"]
    Saves -->|"加载存档"| Loading["loading<br>WebSocket 连接"]
    Saves -->|"开始新游戏"| Create
    Create --> Loading
    Loading --> Playing["playing<br>游戏主界面"]
    Playing --> Ended["ended<br>毕业/Game Over"]
```

### `App.vue`

- 启动时先检查 `zjus_prologue_seen_v1`；未看过序章时暂不执行鉴权分流，也不建立 WebSocket。
- 序章完成后读取 `localStorage`：
  - `zju_jwt` / `zju_token`：JWT，用于 HTTP/WS 鉴权。
  - `zju_user_token`：长期学生凭证，用于老玩家登录。
  - `zju_saves`：老玩家登录返回的存档摘要。
  - `game_started`：是否可以直接连接游戏。
  - `selected_save_slot`：选择加载的存档槽位。
- 当阶段进入 `loading` 时建立 WebSocket。
- 首次进入 `playing` 且 WebSocket 已连接后启动新手引导；引导期间通过 `pause` / `resume` 冻结后端 tick，并用 `isGuideActive` 冻结前端本地倒计时。
- 如果旧版本误把长期凭证写入 `zju_token`，启动时会迁移到 `zju_user_token` 并要求重新登录。

---

## HTTP API 层

### `api.generated.ts`

- 从后端 OpenAPI 自动生成。
- 作为后端契约类型来源。
- 不手写修改。

### `client.ts`

- 手写薄封装，负责 `fetch()` 调用。
- 类型别名引用 `components['schemas']`：
  - `AuthRequest` / `AuthResponse`
  - `SaveSummary`
  - `MajorOption`
  - `InitCharacterRequest` / `InitCharacterResponse`
  - `AdmissionInfoResponse`

主要函数：

| 函数 | 端点 | 用途 |
|---|---|---|
| `auth()` | `POST /api/auth` | 邀请码认证，新用户返回学生凭证，老用户返回存档列表 |
| `fetchMajors()` | `GET /api/majors` | 获取全部可选专业 |
| `initCharacter()` | `POST /api/init_character` | 创建新游戏角色 |
| `getAdmissionInfo()` | `GET /api/admission_info` | 兼容查询用户信息/学生凭证 |

---

## 关键组件

### `LoginView.vue`

- 表单字段：昵称、邀请码、老玩家学生凭证。
- 可选自定义通用 LLM 配置和钉钉 RP MiniMax Key，用户确认安全提示后保存到 `sessionStorage`。
- 新玩家成功后：
  - 保存 JWT 到 `zju_token` / `zju_jwt`。
  - 保存长期学生凭证到 `zju_user_token`。
  - 进入 `character_create`。
- 老玩家成功后：
  - 保存 JWT 和存档摘要。
  - 清除 `game_started` / `selected_save_slot`。
  - 进入 `save_select`。

### `SaveSelect.vue`

- 从 `localStorage.zju_saves` 读取存档摘要。
- 加载存档：写入 `selected_save_slot`，设置 `game_started=1`，进入 `loading`。
- 开始新游戏：清除 `selected_save_slot` / `game_started`，进入 `character_create`。

### `CharacterCreate.vue`

- 调 `fetchMajors()` 展示专业。
- 从 `statDefinitions.generated.ts` 读取 `allocatable=true` 的属性并动态渲染 slider。
- 当前可分配属性为 `IQ` / `EQ` / `Luck` / `魅力`，每项范围 50-150，总和必须等于 300。
- 调 `initCharacter()` 时推荐提交 `stats` 映射，同时保留旧显式字段兼容；成功后设置 `game_started=1` 并进入 `loading`。

### `RightPanel.vue`

- 渲染学习效率、休闲动作、学期倒计时、期末考试和内容生成模式。
- 从 `gameStore.relaxCooldowns` 读取 `gym` / `game` / `walk` / `cc98` 剩余冷却。
- 冷却中或暂停时锁定休闲按钮；冷却中按钮文案显示剩余秒数。
- 本地倒计时只在 `!isPaused && !isGuideActive && currentPhase === 'playing'` 时流逝，后端 `semester_time_left` 到达时会校准。

### `FeedbackModal.vue`

- 展示服务端 `feedback` 消息。
- 随机事件结果默认 5 秒自动关闭；休闲动作结果默认 3 秒自动关闭。
- 用户可以点击按钮、关闭图标或背景手动关闭。

### `useGameWebSocket.ts`

WebSocket 首条消息包含：

```ts
{
  token,
  load_save_slot?,
  custom_llm_provider?,
  custom_llm_model?,
  custom_llm_api_key?,
  custom_rp_api_key?
}
```

`custom_rp_api_key` 只用于钉钉 M2-her RP。若配置了通用自定义 LLM 但没有配置 RP key，钉钉内容会回退到通用自定义 LLM，而不是继续使用平台默认 M2-her。

- `auth_ok` 后只启动心跳并记录连接日志；后端负责启动引擎，避免自动 `resume` 干扰引导或暂停。
- `auth_error` 会清理当前游戏标记；若是存档错误则回到 `save_select`，否则回到 `login`。
- `init` 将阶段切到 `playing` 并初始化课程、属性、剩余时间、`relax_cooldowns`、钉钉状态和道具状态。
- `tick` 持续同步课程、属性、剩余时间和 `relax_cooldowns`。
- `feedback` 调用 `gameStore.showFeedback()` 展示结果弹窗。
- `dingtalk_state` 恢复钉钉联系人、私聊历史、未读数和回复选项。
- `dingtalk_thread_update` 更新单个联系人线程；旧 `dingtalk_message` 会兼容映射到联系人线程。
- `items_state` 恢复道具目录、已拥有道具、当前加成和更新时间；`item_buy` / `item_sell` 只走 WebSocket，不进入 OpenAPI。
- `achievement_unlocked` 写入 `gameStore.unlockedAchievements`，同时展示 toast/feedback；`semester_summary` 和 `graduation` 可携带成就详情用于成绩单和毕业页。
- `save_result` / `exit_confirmed` 负责退出时清理 JWT 和本局标记。
- EndScreen 的“回到首页”应调用 WebSocket `disconnect()`，关闭重连并清理本局 JWT/slot 标记；长期学生凭证继续保留。

---

## 状态管理

`gameStore.ts` 管理：

| 状态 | 说明 |
|---|---|
| `currentPhase` | 当前页面阶段 |
| `currentStats` | 玩家属性 |
| `courseMetadata` | 当前学期课程元数据 |
| `currentCourseStates` | 课程策略 |
| `semesterTimeLeft` | 学期剩余秒数 |
| `isPaused` / `isGuideActive` | 后端暂停状态 / 前端引导冻结状态 |
| `relaxCooldowns` | 休闲动作剩余冷却秒数 |
| `eventLogs` | 事件日志 |
| `dingtalkContacts` / `unreadDingtalk` | 钉钉联系人线程和未读数 |
| `unlockedAchievements` | 本局已解锁成就详情 |
| `itemCatalog` / `ownedItems` / `itemBonuses` | 道具目录、已拥有道具和持有加成 |
| `gameMode` / `llmAvailable` | 内容生成模式状态 |
| `activeModal` / `modalData` | 当前弹窗 |
| `feedbackModal` | 结果反馈弹窗 |
| `endType` / `endData` | 结局数据 |

---

## 开发命令

```bash
npm run dev
npm run build
npm run type-check
npm run lint
npm test
```

OpenAPI 类型生成需在根目录通过 Docker Compose 启动后端，并等待 `/openapi.json` 可访问后执行：

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
