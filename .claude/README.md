# Shared `.claude/` in `ZJUers Simulator` Project.

This directory contains Claude Code handoff material for ZJUers Simulator.

## Read Order

1. `CLAUDE.md` - main project instructions and current architecture.
2. `Changelog.md` - recent development state and handoff notes.
3. `skills/code-review-skill/SKILL.md` - path-aware review and validation workflow.
4. MkDocs developer docs under `docs/dev/` for detailed contracts.

## Current Project Shape

- Backend: FastAPI + WebSocket + Redis + PostgreSQL in `zjus-backend/`.
- Frontend: Vue 3 + TypeScript + Vite + Pinia in `zjus-frontend/`.
- Runtime services: use root `docker compose`, especially for backend integration and OpenAPI.
- Generated API types: `zjus-frontend/src/types/api.generated.ts`; never edit manually.
- Thin API client: `zjus-frontend/src/api/client.ts`; keep hand-written and schema-backed.

## Important Historical Drift

Older notes may mention an entrance exam or `admission` phase. That flow has been removed.

Current entry flow is:

```text
login -> save_select -> character_create -> loading -> playing -> ended
```

New players choose a major and allocate base stats. Returning players choose an existing save or start a new game.

## Conventions For Claude Code

- Prefer concise, surgical edits.
- Preserve unrelated dirty worktree changes.
- Use root Docker Compose for backend service startup and OpenAPI generation.
- Use project-local frontend binaries such as `.\node_modules\.bin\vue-tsc.cmd`.
- Treat Pylance reports in backend source as worth investigating; many can be fixed with type narrowing without changing behavior.
- Keep `.claude` content focused on handoff and workflows. Put user/developer product docs in `docs/`.

## Skills

The local Claude skill currently present is:

- `skills/code-review-skill/SKILL.md`: selects backend/frontend checks based on changed paths.

Codex-side project skills in `.codex/skills/` are not Claude-native skills, but they are useful reference material when maintaining equivalent Claude workflows.
