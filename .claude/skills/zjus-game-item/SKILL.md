---
name: zjus-game-item
description: Add, adjust, remove, or review ZJUers Simulator items in world/items.json. Use when the user asks Claude to create a new purchasable item, tune item prices/effects, add item categories or tags, or check item balance against the stat registry.
argument-hint: "<item_id_or_name> [--category <name>] [--price <gold>] [--effects field:delta,...]"
---

# ZJUS Game Item

## Argument Handling

Read `$ARGUMENTS` first. Treat the first positional token as the requested item id or display name. Parse optional hints such as `--category`, `--price`, and `--effects`; if missing, infer a balanced item from the user message and existing catalog.

Normalize new item ids to lowercase snake_case. Keep item names in Chinese unless the user explicitly requests otherwise.

## Item Shape

Edit `zjus-backend/world/items.json` for ordinary item additions:

```json
{
  "id": "snake_case_id",
  "name": "中文名",
  "category": "学习",
  "description": "一句有校园质感的说明。",
  "price": 100,
  "sell_price": 50,
  "tags": ["学习", "效率"],
  "effects": {
    "iq": 4,
    "stress": -2
  }
}
```

## Rules

- Effects must use fields with `allow_item_effect=true` in `zjus-backend/world/stat_definitions.json`.
- v1 items are one-owned-copy max and passive while owned.
- `sell_price` may be omitted, but prefer explicit half-price or tuned values.
- Do not add migrations or OpenAPI changes for ordinary items.
- Keep descriptions concise, flavorful, and campus-specific.

## Balance Heuristics

- Typical single-stat passive bonuses should usually be `3-8`.
- Multi-effect items should cost more than narrow items.
- `stress: -N` is beneficial; `stress: +N` is a drawback.
- `efficiency` is powerful and should be priced conservatively.
- Avoid cheap items with several strong positive effects.

## Validation

Run from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe scripts\validate_world_data.py
..\.venv\Scripts\python.exe -m py_compile app\game\items.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_items.py tests\unit\test_game_state.py
..\.venv\Scripts\python.exe -m ruff check app tests\unit scripts
```

Run frontend checks from `zjus-frontend/` if item display or stat metadata changed:

```powershell
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
```

## Documentation

Update user or world docs when item behavior changes. Update `AGENTS.md` and `.claude/CLAUDE.md` only if the maintenance workflow changes.
