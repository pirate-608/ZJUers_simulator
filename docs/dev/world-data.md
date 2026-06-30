# 游戏设定维护

本页记录 `zjus-backend/world/`、Admin 世界数据发布页、属性注册表和道具目录的维护流程。目标是让“新增一个属性 / 新增一个道具 / 调整一组数值”尽量只改世界数据和少量明确入口，而不是在前后端重复追字段。

## 数据边界

| 类型 | 事实源 | 运行时消费 | 是否需要 OpenAPI |
| ---- | ------ | ---------- | ---------------- |
| 平衡参数 | `world/game_balance.json` | `app/game/balance.py`、`GameEngine`、Admin `/admin/balance` | 否 |
| 属性定义 | `world/stat_definitions.json` | `PlayerStats`、Redis、道具/事件白名单、前端生成元数据 | 可分配属性变化时通常需要 |
| 道具目录 | `world/items.json` | `app/game/items.py`、Redis `items_state`、前端道具页、Admin `/admin/items` | 否 |
| 专业/课程 | `world/majors.json`、`world/courses/**` | `WorldService`、角色初始化、学期切换 | 视 HTTP 响应是否变化 |
| 角色/向量 | `world/characters.json`、`character_embeddings.csv` | 钉钉角色检索、M2-her/generic LLM 上下文 | 否 |
| 校园关键词 | `world/keywords.json` | 随机事件、钉钉、毕业总结和内容库生成语境 | 否 |
| 事件/CC98 库 | `world/event_library*.json`、`world/cc98_library*.json` | `library` / `hybrid` 内容生成 | 否 |
| 毕业评价 | `world/graduation_comments.json` | 算法模式或 LLM 不可用时的毕业典礼兜底文案 | 否 |

生产 Compose 会挂载 `./zjus-backend/world:/app/world`。因此服务器上的 Admin 数值/道具发布和手工编辑都会落到挂载目录；不要把生产配置只改在镜像内部。

## 数值平衡管理

`/admin/balance` 只编辑 `world/game_balance.json` 既有结构中的数字和短文本字段，不支持任意 JSON 节点、速度档位增删或休闲动作增删。

保存流程：

1. SQLAdmin 登录态校验。
2. 表单转换为完整配置。
3. 后端校验范围和必填字段。
4. 临时文件写入后用 `os.replace` 原子替换。
5. 调用 `balance.reload()` 热重载。
6. 写入 `admin_audit_logs`，操作类型为 `balance_update`。

“恢复上一版”会读取最近一次 `balance_update` 的旧配置，校验后写回，并记录 `balance_restore`。恢复的是上一次保存前的完整 `game_balance.json`，不是 Git 版本回退。

注意：

- `tick.interval_seconds` 是 `GameEngine.run_loop()` 的真实 tick 间隔。
- 默认 3 秒只是不改变当前手感的默认值；调低会增加 Redis/WS 频率，调高会改变玩家体感。
- 学期时长、随机事件概率、钉钉概率和休闲冷却都属于运营平衡参数，改动后至少做一局 smoke。

## 属性定义注册表

`world/stat_definitions.json` 是属性单一事实源。每个属性包含：

| 字段 | 作用 |
| ---- | ---- |
| `id` | 稳定字段名，进入 Redis/存档/前端 payload |
| `label` / `icon` | 前端展示和反馈弹窗文案 |
| `default` / `min` / `max` | 初始值、修复值、clamp 范围 |
| `positive_endpoint` | 休闲收益溢出判断的正向端点，`max` 或 `min` |
| `allocatable` | 是否参与角色创建初始点数预算 |
| `allow_item_effect` | 是否允许道具被动加成影响 |
| `allow_event_effect` | 是否允许随机事件/钉钉结算影响 |
| `llm_context` | 是否进入 LLM 状态摘要 |
| `show_in_character_create` / `show_in_hud` | 前端创建页和 HUD 展示开关 |

新增属性建议流程：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe scripts\scaffold_game_stat.py add <stat_id>
```

脚手架会输出定义模板和人工复核清单。确认设计后：

1. 编辑 `world/stat_definitions.json`。
2. 如果允许道具效果，按需编辑 `world/items.json`。
3. 如果允许事件效果，检查事件库和 LLM prompt 是否需要补充说明。
4. 生成前端元数据：

```powershell
..\.venv\Scripts\python.exe scripts\sync_stat_definitions.py --write
```

5. 校验世界数据：

```powershell
..\.venv\Scripts\python.exe scripts\validate_world_data.py
```

6. 若 `allocatable=true` 或角色创建请求模型变化，按 Compose-first 流程重新生成 OpenAPI 类型。
7. 补 focused tests：属性定义加载、角色创建预算、前端创建页、HUD/反馈/道具展示。

删除属性比新增更危险。删除前要确认：

- Redis 旧存档缺字段时能被默认值/修复逻辑接住。
- `items.json`、事件库、成就条件、LLM 上下文和前端展示没有残留字段。
- 前端生成元数据已同步，且没有组件手写该字段标签或上限。

## 道具目录维护

`world/items.json` 包含 `economy` 和 `items` 两部分。

`/admin/items` 可图形化编辑同一个文件，并在保存后立即调用 `items.reload()` 热重载。页面支持：

- 调整初始金币和期末金币公式。
- 修改已有道具的名称、分类、说明、价格、出售价、标签和被动效果。
- 新增道具，或勾选删除已有道具。
- 从最近一次 `items_update` 审计记录恢复上一版完整配置，恢复后记录 `items_restore`。

已有道具的 `id` 在后台页面中只读，因为存档背包只保存 `item_id`；若要替换 ID，推荐新增新道具，再视情况逐步下架旧道具。

单个道具字段：

| 字段 | 说明 |
| ---- | ---- |
| `id` | 稳定唯一 ID，存档只保存它 |
| `name` | 展示名称 |
| `category` | 分类筛选与视觉分组 |
| `description` | 道具说明 |
| `price` | 购买价格 |
| `sell_price` | 可选；缺省时为 `price * 0.5` |
| `tags` | 搜索和标签展示 |
| `effects` | 持有即生效的被动加成 |

新增普通道具流程：

1. 确认 `effects` 只使用 `allow_item_effect=true` 的属性。
2. 通过 `/admin/items` 新增道具，或直接编辑 `world/items.json`，保持 `id` 稳定且唯一。
3. 运行：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe scripts\validate_world_data.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_items.py
```

4. 若只是新增普通道具或通过 `/admin/items` 调价，不需要数据库迁移、OpenAPI 生成或前端类型生成。
5. 如果新增了道具影响的新属性，先走属性定义流程，再编辑道具。

道具效果不会直接写入基础 `PlayerStats`。后端通过 `items.apply_bonuses_to_stats()` 生成 effective stats；出售后加成消失，保存/加载不会重复叠加。

## 校园关键词维护

`world/keywords.json` 用于给随机事件、钉钉消息、毕业总结和离线内容库提供校园语境。关键词不直接改变数值结算，但会影响文本生成是否像“浙大校园生活”。

单个关键词字段：

| 字段 | 说明 |
| ---- | ---- |
| `keyword` | 关键词或梗名 |
| `category` | 校园文化、学业、建筑、校园生活等分类 |
| `desc` | 给模型使用的解释 |
| `examples` | 典型用法或短语 |

维护建议：

1. 先编辑 `world/keywords.json`。
2. 运行 `validate_world_data.py`。
3. 如关键词用于大规模离线内容生产，重新生成事件库/CC98 库前先抽样检查关键词语气。
4. 同步更新[校园关键词](/world/keywords)文档表。

## 毕业评价维护

`world/graduation_comments.json` 提供毕业典礼的非 AI 兜底文案。算法模式会直接使用它；AI/混合模式在文言文总结调用失败或返回空内容时，也会按最终累计 GPA 分支选择一段评价。

当前分支使用 `min_gpa` / `max_gpa` 判断区间，文本放在 `paragraphs` 数组中。普通文案调整不需要数据库迁移、OpenAPI 生成或前端类型生成。

建议修改后运行：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe -m pytest tests\unit\test_graduation_comments.py
```

## 内容库与效果字段

随机事件、钉钉结算和道具效果都受属性注册表约束：

- 道具：`allow_item_effect=true`
- 事件/钉钉：`allow_event_effect=true`
- LLM 状态摘要：`llm_context=true`

离线事件库生产后，应运行 `validate_world_data.py` 检查 effects 字段；不要把未注册字段直接放入事件库或 LLM prompt。事件库偏负或偏正时优先调整库数据和平衡参数，不要在引擎里写临时补丁。

## 推荐验收

| 改动 | 最小检查 |
| ---- | -------- |
| 只调 `game_balance.json` | `pytest tests\unit\test_balance.py`，后台保存 smoke |
| 改属性定义 | `sync_stat_definitions.py --write`，`validate_world_data.py`，前端 `vue-tsc --noEmit` |
| 新增普通道具 | `validate_world_data.py`，`pytest tests\unit\test_items.py tests\unit\test_admin_items_config.py` |
| 改可分配属性 | Docker Compose 后端，OpenAPI 生成，角色创建 focused tests |
| 改事件库/CC98 库 | `validate_world_data.py`，抽样 smoke 内容模式 |

交付前仍建议根据影响面补跑 `pytest tests\unit`、`ruff check app tests\unit`、前端 `vitest run` 和文档 `npm run build`。
