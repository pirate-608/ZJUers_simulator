---
name: code-review
description: Path-aware full-stack review workflow for ZJUers Simulator. Use when reviewing changes, running checks, triaging regressions, validating frontend/backend edits, or deciding which focused tests/type checks to run.
argument-hint: "[--push true|false] [--tag <tagname>]"
---

# ZJUS Code Review Skill

## Purpose

Review changes without wasting time on unrelated stacks. Prefer focused checks first, then widen only when the touched code affects shared contracts, gameplay state, auth, saves, or generated API types.

## Scope Detection

Inspect changed or discussed file paths:

- `zjus-backend/` -> set `RUN_BACKEND = true`.
- `zjus-frontend/` -> set `RUN_FRONTEND = true`.
- `docs/`, `.claude/`, `.codex/skills/` -> set `RUN_DOCS = true`.
- Backend HTTP schema/route changes in `zjus-backend/app/api/*.py`, Pydantic models, auth/init-character responses, or endpoint fields -> set `RUN_OPENAPI = true`.

When both frontend and backend changed, check backend first, then OpenAPI if needed, then frontend.

## Backend Pipeline

Run from `zjus-backend/`. Use the workspace virtual environment:

```powershell
..\.venv\Scripts\python.exe -m py_compile app\path\changed_file.py
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m pytest tests\unit\test_relevant_file.py
```

Choose focused tests based on risk:

- Auth, invite codes, returning users, character creation, stat budget, save selection: `tests\unit\test_onboarding_flow.py` and `tests\unit\test_auth_validation.py`.
- Redis state and snapshot logic: `tests\unit\test_game_state.py`.
- Broad service/API changes: run `..\.venv\Scripts\python.exe -m pytest`.

For Pylance-only cleanup, a `py_compile` check is usually enough unless logic changed.

## Frontend Pipeline

Run from `zjus-frontend/`. Prefer local binaries, not global npm tooling:

```powershell
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\vite.cmd build
```

Use `vue-tsc` for component/store/composable/type changes. Run Vitest when behavior, state transitions, API wrappers, or WebSocket handling changed. Build when routing, bundling, or production assets may be affected.

If `npm run ...` fails only because of the agent sandbox, do not diagnose the user's npm installation; retry with project-local binaries or report the sandbox limitation.

## OpenAPI Pipeline

Use only when backend HTTP contracts changed or generated frontend types may be stale.

Run from the repository root:

```powershell
docker compose up -d --build backend
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json
```

The `127.0.0.1:8000` URL depends on the local `docker-compose.override.yml` backend port mapping. Production base compose keeps backend access internal to Nginx and the Docker network.

Then run from `zjus-frontend/`:

```powershell
.\node_modules\.bin\openapi-typescript.cmd http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

Rules:

- Do not start a bare local `uvicorn` server for OpenAPI.
- Do not hand-edit `src/types/api.generated.ts`.
- Keep `src/api/client.ts` as the hand-written thin wrapper.

## Docs Pipeline

Run from `docs/` when docs or handoff files changed:

```powershell
npm run build
```

If VitePress reports broken links or Markdown/Vue compilation errors, fix the source page, route, or component before reporting success.

## Review Focus

Prioritize findings in this order:

1. Real user-facing regressions.
2. Auth, token, save-slot, or character-state corruption.
3. Client/server contract drift.
4. WebSocket lifecycle, pause/resume, guide, cooldown, or feedback bugs.
5. Performance leaks such as duplicate engine loops, unbounded background tasks, repeated LLM calls, or Redis TTL churn.
6. Missing focused tests for risky behavior.

## Constraints

- Preserve unrelated dirty worktree changes.
- Never delete or weaken tests to pass checks.
- Do not remove runtime validation to satisfy static typing.
- Do not remove `await` from Redis/DB/LLM calls just because a stub says a method is non-awaitable.
- Avoid full test suites for tiny docs or type-only edits unless the change touches shared behavior.

## Reporting

Report:

1. Changed scope detected.
2. Checks run and results.
3. Findings ordered by severity with file/line references when reviewing.
4. Residual risks or skipped checks.
