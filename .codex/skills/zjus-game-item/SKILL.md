---
name: zjus-game-item
description: "Add, adjust, remove, or review ZJUers Simulator items. Use when editing world/items.json, item prices, categories, tags, passive effects, sell prices, item balance, item frontend display, or when a user asks to create new purchasable items or item effects."
---

# ZJUS Game Item

## Purpose

Maintain items through the world-data pipeline while respecting stat effect allowlists and validation.

## Source Of Truth

- Item config: `zjus-backend/world/items.json`
- Stat effect allowlist: `zjus-backend/world/stat_definitions.json`
- Item loader and validator: `zjus-backend/app/game/items.py`
- World validator: `zjus-backend/scripts/validate_world_data.py`

## Item Shape

Each item in `items` uses this v1 shape:

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

Rules:

- `id` should be stable snake_case and unique.
- `price` must be positive; `sell_price` is optional and defaults to 50% in runtime logic, but prefer explicit values for balance clarity.
- Effects must use stats where `allow_item_effect=true` in `stat_definitions.json`.
- v1 items are one-owned-copy max, hold-to-activate passive bonuses.
- Do not use `gold` as an item passive effect unless the stat definition is intentionally changed first.

## Add Or Change An Item

1. Inspect current items and nearby category balance:

```powershell
Get-Content zjus-backend\world\items.json
```

2. Edit only `zjus-backend/world/items.json` for ordinary item additions. Keep descriptions concise and in the project’s campus tone.

3. Validate from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe scripts\validate_world_data.py
```

4. Run focused backend tests from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe -m py_compile app\game\items.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_items.py tests\unit\test_game_state.py
..\.venv\Scripts\python.exe -m ruff check app tests\unit scripts
```

5. Run frontend checks from `zjus-frontend/` if item display, labels, or stats metadata changed:

```powershell
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
```

## Balance Heuristics

- Keep passive bonuses modest. Typical single-stat bonuses should usually be `3-8`.
- Avoid stacking too many effects on one cheap item.
- Price stronger mixed-effect items higher than narrow single-effect items.
- Negative `stress` means stress reduction and is beneficial; positive `stress` is a drawback.
- `efficiency` is powerful because it affects study throughput; price accordingly.

## Documentation

Update docs when player-facing item behavior changes:

- `docs/user/rules.md` or item guide pages if present
- `docs/world/stat_definitions.md` if new effect fields are enabled
- `AGENTS.md` and `.claude/CLAUDE.md` if the item workflow changes

## Guardrails

- Do not edit database migrations for ordinary item additions.
- Do not regenerate OpenAPI for ordinary item additions; items are WebSocket/world-data behavior, not HTTP schema.
- Do not hand-add unsupported effect fields; change `stat_definitions.json` first, then regenerate metadata and validate.
