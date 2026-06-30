---
name: zjus-game-stat
description: Add, adjust, or remove ZJUers Simulator gameplay stats through the stat registry pipeline. Use when the user asks Claude to create a new attribute, change an attribute range/default, expose a stat to item/event effects, or update character creation allocatable stats.
argument-hint: "<stat_id_or_name> [--allocatable] [--item-effect] [--event-effect] [--hud]"
---

# ZJUS Game Stat

## Argument Handling

Read `$ARGUMENTS` first. Treat the first positional token as the requested stat id or Chinese display name. If no argument is supplied, infer the target from the user message; ask only if the target stat cannot be inferred safely.

Normalize a new stat id to lowercase snake_case. Preserve user-provided Chinese labels for `label`.

## Workflow

1. Inspect `zjus-backend/world/stat_definitions.json`.
2. Use `zjus-backend/scripts/scaffold_game_stat.py` from `zjus-backend/` to draft additions:

```powershell
..\.venv\Scripts\python.exe scripts\scaffold_game_stat.py add <stat_id> --label "<label>" --icon "<icon>"
```

3. Add flags intentionally:

- `--allocatable` for character creation budget stats.
- `--allow-item-effect` for item passive bonuses.
- `--allow-event-effect` for random event and DingTalk settlement effects.
- `--llm-context` for model prompts.
- `--show-in-hud` for visible HUD stats.
- `--positive-endpoint min|max|none` for beneficial direction.

4. If `--write` is used or JSON is edited manually, regenerate frontend metadata:

```powershell
..\.venv\Scripts\python.exe scripts\sync_stat_definitions.py --write
```

5. Validate:

```powershell
..\.venv\Scripts\python.exe scripts\validate_world_data.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_stat_definitions.py tests\unit\test_auth_validation.py tests\unit\test_game_state.py
..\.venv\Scripts\python.exe -m ruff check app tests\unit scripts
```

6. If the init-character HTTP schema changes, regenerate `zjus-frontend/src/types/api.generated.ts` through Docker Compose as described in `AGENTS.md`; never edit it by hand.

## Files Usually Touched

- `zjus-backend/world/stat_definitions.json`
- `zjus-frontend/src/data/statDefinitions.generated.ts`
- `zjus-backend/world/items.json` or `event_library.json` only if the new stat is used there
- `docs/world/stat_definitions.md`
- `AGENTS.md` and `.claude/CLAUDE.md` if the workflow itself changes

## Guardrails

- Keep allocatable defaults summing to `initial_budget`.
- Do not weaken backend validation to make a new stat fit.
- Do not add unsupported item/event effect fields without enabling them in `stat_definitions.json`.
