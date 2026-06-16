# CLAUDE.md

This file is the handoff guide for AI agents when working in this repository.

## Project Snapshot

ZJUers Simulator (折姜大学模拟器) is a Vue 3 + FastAPI campus simulation game.

- Frontend: `zjus-frontend/`, Vue 3, TypeScript, Vite, Pinia.
- Backend: `zjus-backend/`, FastAPI, WebSocket, SQLAlchemy async, PostgreSQL, Redis.
- Runtime data: `zjus-backend/world/`, including courses, majors, achievements, balance, event libraries, and CC98 libraries.
- Docs: VitePress under `docs/`, with theme/components/static assets isolated in `docs/.vitepress/` and `docs/public/`.

Current player entry flow:

```text
login -> save_select -> character_create -> loading -> playing -> ended
```

On a browser's first visit, the frontend may show a skippable pre-login prologue before this `GamePhase` flow. It is stored with `localStorage.zjus_prologue_seen_v1`; while it is active, App startup must not route to login/save/character pages or open the WebSocket.

There is no entrance-exam/admission-test flow anymore. New players authenticate with invite code, save their long-lived student credential, choose a major, allocate stats, then enter the game. Returning players authenticate with nickname + invite code + student credential, then choose a save slot or start a new game.

## Hard Rules

- Do not start a bare local backend with `uvicorn` for integration work or OpenAPI generation. Use Docker Compose from the repository root.
- Do not hand-edit `zjus-frontend/src/types/api.generated.ts`; fix backend Pydantic/FastAPI models and regenerate from `/openapi.json`.
- Keep `zjus-frontend/src/api/client.ts` as a hand-written thin fetch wrapper that imports generated schema types.
- Do not remove `await` or weaken runtime validation just to silence Pylance; many Redis/OpenAI/SQLAlchemy diagnostics are stub or narrowing issues.
- The user's local npm is fine. If npm commands fail only inside an agent sandbox, prefer project-local binaries or explain the sandbox limitation instead of diagnosing the user's machine.
- Preserve unrelated dirty worktree changes.

## Compose-First Backend

Use Docker Compose for backend services, migrations, Redis, Postgres, embeddings seed, and API contract generation:

```powershell
docker compose up -d --build backend
docker compose logs --tail=200 backend
```

Production `docker-compose.yml` does not publish the backend port to the host; Nginx reaches `backend:8000` over the Docker network. Local development and OpenAPI generation rely on `docker-compose.override.yml` to publish `127.0.0.1:8000:8000`.
In production, backend startup defaults to SQL echo off and skips `Base.metadata.create_all`; database structure should come from the `migrate` Alembic service.

OpenAPI regeneration path:

```powershell
docker compose up -d --build backend
$openapi = $null
for ($i = 0; $i -lt 30; $i++) {
    try {
        $openapi = Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8000/openapi.json
        if ($openapi.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 2
    }
}
if (-not $openapi -or $openapi.StatusCode -ne 200) {
    throw "Backend did not serve /openapi.json in time."
}
cd zjus-frontend
.\node_modules\.bin\openapi-typescript.cmd http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

## Useful Commands

Backend checks from `zjus-backend/`:

```powershell
..\.venv\Scripts\python.exe -m py_compile app\game\engine.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_onboarding_flow.py
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m ruff format .
```

If pytest fails only while creating `tmp_path` directories on Windows/Codex,
rerun it with an explicit workspace temp root such as
`--basetemp ..\pytest-temp\current` from `zjus-backend/` before treating the
failure as a code regression.

Frontend checks from `zjus-frontend/`:

```powershell
.\node_modules\.bin\vue-tsc.cmd --noEmit
.\node_modules\.bin\vitest.cmd run
.\node_modules\.bin\vite.cmd build
```

Docs checks from `docs/`:

```powershell
npm run build
```

The VitePress homepage demo imports selected `zjus-frontend` Vue components. In a clean checkout or CI runner, install `zjus-frontend` dependencies before building docs so frontend `tsconfig` package extends such as `@vue/tsconfig` resolve correctly.
Keep `vue` and `pinia` deduped in `docs/.vitepress/config.ts`; otherwise the docs theme can install one Pinia instance while reused frontend components read another, causing the homepage demo to disappear during hydration.

## Architecture Pointers

Backend:

- `zjus-backend/app/api/auth.py`: invite-code auth, returning-user save list, majors, character initialization.
- `zjus-backend/app/api/game.py`: WebSocket entry, config API, engine lifecycle.
- `zjus-backend/app/admin.py`: SQLAdmin models plus `/admin/balance` operational balance editor.
- `zjus-backend/app/core/input_safety.py`: player username normalization, prompt-injection keyword checks, and prompt-safe fallback.
- `zjus-backend/app/game/engine.py`: tick loop, actions, final exams, random events, relax cooldowns, feedback messages, content mode switching.
- `zjus-backend/app/game/balance.py`: `world/game_balance.json` path resolution, runtime reads, and hot reload.
- `zjus-backend/app/services/game_service.py`: character/major initialization, semester transitions.
- `zjus-backend/app/services/save_service.py`: Redis/Postgres save load and persistence.
- `zjus-backend/app/services/balance_admin.py`: admin form schema, validation, atomic file publish, audit snapshot restore.
- `zjus-backend/app/repositories/redis_repo.py`: active game state, TTL, cooldowns, event history.
- `zjus-backend/app/core/llm.py` and `dingtalk_llm.py`: LLM-backed content generation and fallbacks.
  MiniMax M2-her RP calls use the OpenAI SDK compatible base URL `MINIMAX_BASE_URL=https://api.minimaxi.com/v1` and the case-sensitive model name `M2-her`; keep templates, docs, and tests exact when touching this path. Send only documented `role`/`content` fields in M2-her messages; do not pass DingTalk display names such as `【室友】` through the API `name` field.
  Long-running content actions must not block the WebSocket receive loop: DingTalk replies and relax actions run through `GameEngine._track_task`, with target-level de-duplication for relax actions.

Frontend:

- `zjus-frontend/src/App.vue`: pre-login prologue gate, phase routing, global modals, guide startup.
- `zjus-frontend/src/components/PrologueScene.vue` and `src/data/prologue.ts`: first-visit prologue text, image mapping, and seen-state key.
- `zjus-frontend/src/components/LoginView.vue`: Invite-code login, plus a session-scoped custom LLM config section where API key, model name, and provider are optional fields (may be left NULL; system defaults apply when NULL).
- `zjus-frontend/src/components/SaveSelect.vue`: returning-user save selection or new game.
- `zjus-frontend/src/components/CharacterCreate.vue`: major selection and stat budget UI.
- `zjus-frontend/src/composables/useGameWebSocket.ts`: auth handshake, heartbeat, message dispatch.
- `zjus-frontend/src/stores/gameStore.ts`: global game state, feedback modal, pause/guide flags, cooldowns.
- `zjus-frontend/src/components/RightPanel.vue`: relax actions, cooldown lockout, content generation mode switch.
- `zjus-frontend/src/components/modals/FeedbackModal.vue`: random-event and relax-result feedback.

Docs:

- User docs: `docs/user/*`
- Developer docs: `docs/dev/*`
- Homepage interactive demo: `docs/.vitepress/theme/components/InteractiveGameDemo.vue`
- World/balance docs: `docs/world/*`
- VitePress theme and interactive docs components: `docs/.vitepress/*`
- Public docs assets served from site root: `docs/public/assets/*`
- Do not manually maintain `docs/assets/sources` resource mirrors; world data source of truth is `zjus-backend/world/`.

## Current Behavior Contracts

Player usernames:

- `POST /api/auth` normalizes usernames with NFKC, trims/collapses ordinary spaces, limits length, and rejects control/hidden characters, emoji/symbols, unsupported punctuation, and prompt-injection/reserved keywords.
- Reuse `app.core.input_safety.validate_username` for login-time checks; do not add a second username allowlist in route code.
- Before putting any username into LLM prompts or persistent game stats, use `safe_username_for_prompt`; unsafe legacy values fall back to `同学`.

Character creation:

- `IQ`, `EQ`, and `Luck` each range from 50 to 150.
- The client and server both enforce a total base budget of 250.
- Major IQ bonus is added after the base-budget check and is intentionally retained.

Returning users:

- `POST /api/auth` returns `status: "returning"` with save summaries when a valid student credential is supplied.
- The frontend shows `SaveSelect`, where the player loads a listed save slot or starts a new game.

WebSocket:

- First message sends `token`, optional `load_save_slot`, and optional custom LLM fields.
- `auth_ok` means the connection is usable. The frontend must not automatically send `resume`; backend owns startup through `engine.start()`.
- `init` and `tick` include `relax_cooldowns`.
- `feedback` messages show user-facing result popups while `event` logs remain in "求是园动态".

Guide/pause:

- The first-play guide pauses backend ticking and freezes frontend local countdown through `isGuideActive`.
- Resume only after the guide finishes or the user explicitly resumes.

Relax actions:

- `gym`, `game`, `walk`, and `cc98` have server-side cooldowns.
- Cooldown buttons are disabled and display remaining seconds.
- Relax results show a feedback modal for 3 seconds and still append logs.

Random events:

- Event choices are validated against the current server-side event.
- Results show a feedback modal for 5 seconds and still append logs.

Content generation:

- Modes are `library`, `hybrid`, and `ai`.
- When AI/LLM becomes unavailable, AI mode falls back toward hybrid mode(if still have issues, then fall back to library mode) behavior and emits mode/toast updates.

Admin balance:

- `/admin/balance` edits only the existing numeric/short-text fields in `zjus-backend/world/game_balance.json`; v1 does not add/delete speed modes, course strategies, relax actions, or arbitrary JSON nodes.
- Saving validates the full config, atomically replaces the JSON file, calls `balance.reload()`, and records `balance_update` in `admin_audit_logs`.
- "Restore latest" reads the previous config from the latest `balance_update` audit row, writes it back, hot reloads, and records `balance_restore`.
- This admin page does not change player HTTP APIs, WebSocket contracts, OpenAPI, or database schema.

## Pylance Notes

Common backend noise should be fixed by narrowing types rather than suppressing:

- Use `Coroutine[Any, Any, Any]` for helpers that pass coroutine objects into `asyncio.create_task`.
- Use SQLAlchemy async types (`AsyncSession`, `async_sessionmaker`) for async DB code.
- Normalize optional strings before `.strip()`, `json.loads`, `compare_digest`, or service calls.
- Keep Redis calls async; fix imports/types instead of deleting `await`.
- Convert numeric Redis hash values to strings if stubs require string values.
- Guard OpenAI response `content` because SDK types allow `None` and mixed content shapes.

## Related Project Skills

Claude Code can use `.claude/skills/code-review-skill/SKILL.md` for path-aware checks. The Codex-side workflows in `.codex/skills/` are also useful references:

- `zjus-compose-openapi`: Docker Compose backend + OpenAPI regeneration.
- `zjus-docs-sync`: docs synchronization after product/API changes.
- `zjus-player-onboarding`: auth, saves, character creation, and stat-budget flow.
- `zjus-pylance-noise`: project-specific Pylance/Pyright cleanup.
- `zjus-change-review`: broad frontend/backend regression review.

## Rule for maintaining up-to-date documentation (.claude\CLAUDE.md & AGENTS.md):

- Trigger: After any modification or refactoring (e.g., backend API, database schema, logic migration).
- Action: Update or supplement the file to match the new state.
- Goal: To provide accurate, current information for current agent or other agents taking over development.
