# 属性定义

配置来源：`world/stat_definitions.json`。

该文件是游戏属性的单一事实源，用来减少新增属性或道具效果时的重复手工修改。后端从这里读取属性默认值、初始分配规则、效果白名单、数值 clamp 范围和展示标签；前端属性元数据由脚本同步生成。

## 当前属性

| 字段 | 名称 | 默认值 | 范围 | 正向端点 | 初始分配 | 道具效果 | 事件/钉钉效果 | HUD |
| ---- | ---- | ------ | ---- | -------- | -------- | -------- | -------------- | --- |
| `energy` | 精力 | 100 | 0-200 | 上限 | 否 | 是 | 是 | 是 |
| `sanity` | 心态 | 80 | 0-200 | 上限 | 否 | 是 | 是 | 是 |
| `stress` | 压力 | 0 | 0-200 | 下限 | 否 | 是 | 是 | 是 |
| `iq` | IQ | 100 | 50-150 | 上限 | 是 | 是 | 否 | 是 |
| `eq` | EQ | 100 | 50-150 | 上限 | 是 | 是 | 是 | 是 |
| `luck` | 运气 | 50 | 50-150 | 上限 | 是 | 是 | 是 | 是 |
| `charm` | 魅力 | 50 | 50-150 | 上限 | 是 | 是 | 是 | 是 |
| `reputation` | 声望 | 0 | 0-200 | 上限 | 否 | 是 | 是 | 否 |
| `efficiency` | 效率 | 100 | 0-300 | 上限 | 否 | 是 | 否 | 否 |
| `gold` | 金币 | 0 | 0-999999 | 上限 | 否 | 否 | 是 | 是 |

`positive_endpoint` 用于判断“正向收益已经到顶”。例如压力的正向端点是下限，所以降低压力才是正向收益；精力、心态、魅力等则以上限为正向端点。

## 字段含义

| 字段 | 说明 |
| ---- | ---- |
| `id` | 稳定字段名，进入 Redis、PostgreSQL 存档和 WebSocket payload |
| `label` / `icon` | 前端展示、反馈弹窗和道具效果摘要 |
| `default` | 新游戏默认值、旧存档修复值和新学期精力回调基准 |
| `min` / `max` | Redis `update_stat_safe()` 和前端进度条范围 |
| `positive_endpoint` | 休闲正向收益溢出转移的端点 |
| `allocatable` | 是否参与角色创建初始预算 |
| `allow_item_effect` | 是否允许 `world/items.json` 的道具 effects 使用 |
| `allow_event_effect` | 是否允许随机事件和钉钉结算 effects 使用 |
| `llm_context` | 是否进入 LLM 玩家状态摘要 |
| `show_in_character_create` / `show_in_hud` | 是否在角色创建页和 HUD 展示 |

## 新增或调整属性

新增或调整属性时，先修改 `zjus-backend/world/stat_definitions.json`，再运行：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe scripts\sync_stat_definitions.py --write
..\.venv\Scripts\python.exe scripts\validate_world_data.py
```

如果新增的是可初始分配属性，还需要通过 Docker Compose 后端重新生成 OpenAPI 类型，并补充角色创建页测试。

普通道具新增只需要改 `world/items.json` 并跑 `validate_world_data.py`；道具 `effects` 字段必须出现在属性定义中且 `allow_item_effect=true`。

推荐顺序：

1. 先用 `scripts\scaffold_game_stat.py add <stat_id>` 查看模板和复核清单。
2. 修改 `stat_definitions.json`。
3. 如需影响道具，修改 `items.json`；如需影响事件，检查事件库 effects。
4. 运行 `sync_stat_definitions.py --write` 生成 `zjus-frontend/src/data/statDefinitions.generated.ts`。
5. 运行 `validate_world_data.py`。
6. 若请求模型变化，走 Compose-first OpenAPI 生成。
7. 补充后端属性/事件/道具测试和前端创建页/HUD/反馈展示测试。

删除属性前要先清理所有引用：道具、事件库、成就条件、LLM 上下文、前端组件和旧存档修复逻辑。不要只从 JSON 中删字段。

## 运行时消费

- 后端 `PlayerStats` 初始值、Redis `update_stat_safe()`、道具 effective stats、事件库检索、钉钉/LLM 上下文都会读取该定义。
- 前端 `CharacterCreate.vue`、`HudBar.vue`、`RightPanel.vue`、`MidPanel.vue`、`EndScreen.vue` 和新手引导文案通过 `src/data/statDefinitions.generated.ts` 或 `src/utils/statDisplay.ts` 获取展示信息。
- 组件中不应重新写死属性中文名、默认值或范围；如果页面显示不符合设定，优先检查生成文件是否同步。

更完整的世界数据维护流程见[游戏设定维护](/dev/world-data)。
