# 重构完成：统一玩家状态初始化逻辑

## 变更总结

将 3 处独立的 `_build_initial_stats` 硬编码定义统一收敛到 `PlayerStats.build_initial()` 单一来源。

## 修改文件

### 1. [game_state.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/schemas/game_state.py) — 新增权威定义

新增两个方法：
- `build_initial(username, **overrides)` — 全局唯一的初始状态工厂
- `get_repair_fields()` — 统一的字段补全逻辑

render_diffs(file:///d:/projects/ZJUers_simulator/zjus-backend/app/schemas/game_state.py)

---

### 2. [game_service.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/services/game_service.py) — 委托调用

- `_build_initial_stats` → 1 行委托
- `_ensure_base_fields` → 委托 `get_repair_fields()`，减少 18 行→7 行

render_diffs(file:///d:/projects/ZJUers_simulator/zjus-backend/app/services/game_service.py)

---

### 3. [engine.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/engine.py) — 委托 + 修复 bug

- `_build_initial_stats` → 1 行委托
- **修复**：原定义缺少 `elapsed_game_time` 字段，现在通过 `build_initial()` 自动包含

render_diffs(file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/engine.py)

---

### 4. [state.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/state.py) — 委托调用

- `init_game` → 委托 `PlayerStats.build_initial()`
- **修复**：原定义缺少 `highest_gpa` 字段，现自动包含

render_diffs(file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/state.py)

---

## 验证结果

| 检查项 | 结果 |
|---|---|
| `build_initial` 定义唯一性 | ✅ 仅在 `schemas/game_state.py` 定义 |
| 3 处消费者均委托调用 | ✅ `engine.py` / `game_service.py` / `state.py` |
| 无残留硬编码字段字典 | ✅ `grep "course_plan_json": ""` 返回 0 结果 |
| `get_repair_fields` 被正确使用 | ✅ `game_service.py._ensure_base_fields` 调用 |

> [!IMPORTANT]
> 项目无自动化测试，建议在开发环境手动验证：新用户考试→ 分配专业→ WebSocket 游戏 → 存档/读档 → restart 动作。
