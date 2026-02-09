# API 文档

## 认证与考试 (app/api/auth.py)

### GET /api/exam/questions
- 作用：获取入学考试题库。
- 请求参数：无。
- 响应示例：
  ```json
  [
    {"id": "1", "content": "题目内容", "score": 10},
    ...
  ]
  ```
- 备注：若题库加载失败，返回兜底题目，避免前端报错。

### POST /api/exam/submit
- 作用：提交考试答案，判分并颁发登录凭证。
- 请求体 (application/json)：
  ```json
  {
    "username": "用户昵称",
    "answers": {"1": "A", "2": "B"},
    "token": "可选，老用户凭证",
    "custom_llm_model": "可选，会话级自定义模型",
    "custom_llm_api_key": "可选，会话级自定义 API Key"
  }
  ```
- 响应 (success)：
  ```json
  {"status": "success", "score": 90, "tier": "TIER_1", "token": "<JWT>"}
  ```
- 错误场景：用户名被占用且未提供正确 token、黑名单、分数未达标、凭证错误等。

### POST /api/exam/quick_login
- 作用：老用户免试登录，验证用户名 + 凭证。
- 请求体：
  ```json
  {"username": "用户昵称", "token": "老用户凭证", "custom_llm_model": "可选", "custom_llm_api_key": "可选"}
  ```
- 响应：
  ```json
  {"status": "success", "token": "<JWT>", "username": "...", "assigned_major": "..."}
  ```
- 备注：黑名单/限制用户将被拒绝。

### POST /api/assign_major
- 作用：考试通过后分配专业并初始化游戏存档。
- 请求体：
  ```json
  {"token": "<JWT>"}
  ```
- 响应：
  ```json
  {"success": true, "major": "计算机科学", "major_abbr": "CS", "courses": [...]} 
  ```
- 备注：若 Redis 中不存在存档，将创建初始存档后再分配专业。

### GET /api/admission_info
- 作用：查询当前用户用户名与已分配专业。
- 认证：`Authorization: Bearer <JWT>`
- 响应：
  ```json
  {"username": "...", "assigned_major": "...", "token": "老用户凭证"}
  ```

## 游戏 WebSocket (app/api/game.py)

### 路径：/ws/game
- 握手：先 `accept()`，10s 内首条消息需提供鉴权信息。
- 首条消息 JSON：
  ```json
  {
    "token": "<JWT>",
    "custom_llm_model": "可选，会话级自定义模型",
    "custom_llm_api_key": "可选，会话级自定义 Key"
  }
  ```
- 鉴权失败：返回 `{"type": "auth_error", "message": "无效凭证"}` 并关闭。
- 账号受限：返回 `auth_error` 并关闭。
- 连接管理：同一用户重复连接会踢掉旧连接；心跳超时会清理。
- 消息频率：最小间隔 0.05s。

#### 服务端推送消息类型
- `auth_ok`：鉴权通过。
- `init`：初始状态包，包含玩家统计、课程等。
- `event` / `random_event` / `tick` / `save_result` / `exit_confirmed` 等（详见游戏引擎）。

#### 客户端发送动作
- 心跳：`{"action": "ping"}` → 返回 `pong` 并刷新 TTL。
- 保存并退出：`{"action": "save_and_exit"}` → 返回 `save_result`，清理 Redis 后断开。
- 仅保存：`{"action": "save_game"}` → 返回 `save_result`。
- 不保存退出：`{"action": "exit_without_save"}` → 返回 `exit_confirmed`，清理后断开。
- 其他游戏动作：`engine.process_action` 处理（如 relax/event_choice/next_semester 等）。

## 公共/依赖 (app/api/deps.py)
- `get_db()`：注入异步数据库会话。
- `get_redis()`：获取 Redis 客户端。
- `get_current_user_info(token)`：解析 JWT，失败抛 403。
- `get_world_service()`：世界数据服务。
- `get_redis_repo(user_info, redis)`：按用户构造 Redis 仓库。
- `get_game_service(user_info, repo, world)`：构造游戏业务服务。
- `get_save_service()`：构造存档服务。

## Redis 工具 (app/api/cache.py)
- `RedisCache.get_client()`：获取共享连接池。
- 列表操作：`lpop`、`rpush`、`rpush_with_limit`、`rpush_many_with_limit`、`llen`。
- KV 操作：`set/get/delete/exists/expire`。
- TTL 刷新：`touch_ttl(keys, ttl_seconds)`。
- 玩家 key 构造：`build_player_keys(user_id)`。

## 认证方式说明
- 登录成功后获取 JWT；所有受保护接口/WS 首消息需携带 JWT。
- `get_current_user_info` 在 HTTP 路由中可作为依赖；WS 中由首条消息手动解析。
- 黑名单/限制用户会在各入口被拒绝。

## 会话级自定义 LLM
- 前端可在登录页提供 `custom_llm_model` / `custom_llm_api_key`，仅在当次会话传递，不落库。
- WS 首条消息携带后，后端在本连接中使用该配置，若无效则回退默认环境配置。
