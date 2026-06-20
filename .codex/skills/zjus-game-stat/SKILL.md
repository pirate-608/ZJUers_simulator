---
name: zjus-game-stat
description: "Add, adjust, or remove ZJUers Simulator gameplay stats. Use when working on world/stat_definitions.json, generated frontend stat metadata, character creation allocatable stats, item/event effect allowlists, Redis/PlayerStats stat flow, or when a user asks to create a new player attribute such as charm-like, currency-like, or HUD-visible stats."
---

# ZJUS Game Stat

## Purpose

Maintain gameplay attributes through the stat registry pipeline instead of hand-editing every backend/frontend surface.

## Source Of Truth

- Main config: `zjus-backend/world/stat_definitions.json`
- Backend loader: `zjus-backend/app/game/stat_definitions.py`
- Generated frontend metadata: `zjus-frontend/src/data/statDefinitions.generated.ts`
- Helper script: `zjus-backend/scripts/scaffold_game_stat.py`
- World validator: `zjus-backend/scripts/validate_world_data.py`

## Add Or Change A Stat

1. Inspect current definitions:

```powershell
Get-Content zjus-backend\world\stat_definitions.json
```

2. If adding a stat, draft it with the scaffold script from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe scripts\scaffold_game_stat.py add <stat_id> --label "<label>" --icon "<icon>"
```

Use `--write` only after reviewing the generated JSON. Choose flags deliberately:

- `--allocatable`: appears in character creation and counts toward the initial budget.
- `--allow-item-effect`: items may use this stat in `effects`.
- `--allow-event-effect`: random events, DingTalk settlements, and generation prompts may use this stat.
- `--llm-context`: include in LLM context.
- `--show-in-hud`: frontend HUD should consider it displayable.
- `--positive-endpoint min|max|none`: good direction for overflow/feedback reasoning.

3. If an allocatable stat changes, make the defaults of all allocatable stats sum to `initial_budget`. Preserve legacy compatibility for existing explicit fields unless intentionally changing a public contract.

4. Regenerate frontend metadata from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe scripts\sync_stat_definitions.py --write
```

5. Validate world data from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe scripts\validate_world_data.py
```

## Contract Checks

Run focused backend checks from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe -m py_compile app\game\stat_definitions.py app\schemas\game_state.py app\api\auth.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_stat_definitions.py tests\unit\test_auth_validation.py tests\unit\test_game_state.py
..\.venv\Scripts\python.exe -m ruff check app tests\unit scripts
```

If `POST /api/init_character` schema changes, regenerate OpenAPI using the compose-first flow from `AGENTS.md`; never hand-edit `zjus-frontend/src/types/api.generated.ts`.

Run frontend checks from `zjus-frontend/` when metadata, character creation, HUD, feedback, or item display changes:

```powershell
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
```

## Documentation

Update at least:

- `docs/world/stat_definitions.md`
- `docs/dev/api.md` if init-character contract changes
- `docs/dev/framework/backend_framework.md` and `frontend_framework.md` for workflow changes
- `AGENTS.md` and `.claude/CLAUDE.md` when agent handoff rules change

## Guardrails

- Do not convert `PlayerStats` into a pure `Record` unless explicitly requested.
- Keep existing explicit core fields compatible.
- Do not allow item/event effects by accident; those booleans are gameplay balance decisions.
- Do not bypass `validate_world_data.py`.
