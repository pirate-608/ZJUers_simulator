# 属性定义

配置来源：`world/stat_definitions.json`。

该文件是游戏属性的单一事实源，用来减少新增属性或道具效果时的重复手工修改。后端从这里读取属性默认值、初始分配规则、效果白名单、数值 clamp 范围和展示标签；前端属性元数据由脚本同步生成。

## 当前属性

| 字段 | 名称 | 默认值 | 范围 | 初始分配 | 道具效果 | 事件/钉钉效果 |
| ---- | ---- | ------ | ---- | -------- | -------- | -------------- |
| `energy` | 精力 | 100 | 0-200 | 否 | 是 | 是 |
| `sanity` | 心态 | 80 | 0-200 | 否 | 是 | 是 |
| `stress` | 压力 | 0 | 0-200 | 否 | 是 | 是 |
| `iq` | IQ | 100 | 50-150 | 是 | 是 | 否 |
| `eq` | EQ | 100 | 50-150 | 是 | 是 | 是 |
| `luck` | 运气 | 50 | 50-150 | 是 | 是 | 是 |
| `charm` | 魅力 | 50 | 50-150 | 是 | 是 | 是 |
| `reputation` | 声望 | 0 | 0-200 | 否 | 是 | 是 |
| `efficiency` | 效率 | 100 | 0-300 | 否 | 是 | 否 |
| `gold` | 金币 | 0 | 0-999999 | 否 | 否 | 是 |

## 维护流程

新增或调整属性时，先修改 `zjus-backend/world/stat_definitions.json`，再运行：

```powershell
cd zjus-backend
..\.venv\Scripts\python.exe scripts\sync_stat_definitions.py --write
..\.venv\Scripts\python.exe scripts\validate_world_data.py
```

如果新增的是可初始分配属性，还需要通过 Docker Compose 后端重新生成 OpenAPI 类型，并补充角色创建页测试。

普通道具新增只需要改 `world/items.json` 并跑 `validate_world_data.py`；道具 `effects` 字段必须出现在属性定义中且 `allow_item_effect=true`。

## 运行时消费

- 后端 `PlayerStats` 初始值、Redis `update_stat_safe()`、道具 effective stats、事件库检索、钉钉/LLM 上下文都会读取该定义。
- 前端 `CharacterCreate.vue`、`HudBar.vue`、`RightPanel.vue`、`MidPanel.vue`、`EndScreen.vue` 和新手引导文案通过 `src/data/statDefinitions.generated.ts` 或 `src/utils/statDisplay.ts` 获取展示信息。
- 组件中不应重新写死属性中文名、默认值或范围；如果页面显示不符合设定，优先检查生成文件是否同步。
