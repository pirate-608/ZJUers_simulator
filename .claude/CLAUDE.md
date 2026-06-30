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
- `zjus-backend/app/admin.py`: SQLAdmin models plus `/admin/balance` and `/admin/items` operational world-data editors.
- `zjus-backend/app/core/input_safety.py`: player username normalization, prompt-injection keyword checks, and prompt-safe fallback.
- `zjus-backend/app/game/engine.py`: tick loop, actions, final exams, random events, relax cooldowns, feedback messages, content mode switching.
- `zjus-backend/app/game/balance.py`: `world/game_balance.json` path resolution, runtime reads, and hot reload.
- `zjus-backend/app/game/stat_definitions.py`: `world/stat_definitions.json` loading, stat defaults, initial allocation rules, effect allowlists, and frontend metadata source.
- `zjus-backend/app/game/items.py`: `world/items.json` loading, item economy, passive bonuses, buy/sell state helpers.
- `zjus-backend/app/services/game_service.py`: character/major initialization, semester transitions.
- `zjus-backend/app/services/save_service.py`: Redis/Postgres save load and persistence, including DingTalk and item state.
- `zjus-backend/app/services/balance_admin.py`: admin form schema, validation, atomic file publish, audit snapshot restore.
- `zjus-backend/app/services/item_admin.py`: admin item economy/catalog form schema, validation, atomic file publish, audit snapshot restore.
- `zjus-backend/app/repositories/redis_repo.py`: active game state, TTL, cooldowns, event history, DingTalk state, item state.
- `zjus-backend/scripts/generate_content_library.py`: offline event/CC98 library generation through OpenAI-compatible `chat/completions`; can point at a cloud endpoint or local Ollama `/v1`, while embedding/query vectors stay on local Ollama `bge-m3`.
- `zjus-backend/scripts/sync_stat_definitions.py` and `validate_world_data.py`: keep frontend stat metadata and world effect fields in sync with `world/stat_definitions.json`.
- `zjus-backend/app/core/llm.py` and `dingtalk_llm.py`: LLM-backed content generation and fallbacks.
  Graduation summaries use LLM first, but library mode or LLM failures must fall back to GPA-branched text from `world/graduation_comments.json`.
  MiniMax M2-her RP calls use the OpenAI SDK compatible base URL `MINIMAX_BASE_URL=https://api.minimaxi.com/v1` and the case-sensitive model name `M2-her`; keep templates, docs, and tests exact when touching this path. Send only documented `role`/`content` fields in M2-her messages; do not pass DingTalk display names such as `【室友】` through the API `name` field.
  DingTalk uses platform M2-her only when the player has not provided a general custom LLM, unless the player provides `custom_rp_api_key`; with a general custom LLM and no RP key, DingTalk falls back to the general custom LLM to avoid platform RP spend.
  Cache only the platform-default MiniMax client. Player-provided `custom_rp_api_key` clients are session-sensitive and must be closed after each call instead of stored in a process-wide cache.
  Long-running content actions must not block the WebSocket receive loop: DingTalk replies and relax actions run through `GameEngine._track_task`, with target-level de-duplication for relax actions.

Frontend:

- `zjus-frontend/src/App.vue`: pre-login prologue gate, phase routing, global modals, guide startup.
- `zjus-frontend/src/components/PrologueScene.vue` and `src/data/prologue.ts`: first-visit prologue text, image mapping, and seen-state key.
- `zjus-frontend/src/components/LoginView.vue`: Invite-code login, plus session-scoped custom general LLM config and an optional custom RP MiniMax API key for DingTalk M2-her.
- `zjus-frontend/src/components/SaveSelect.vue`: returning-user save selection or new game.
- `zjus-frontend/src/data/statDefinitions.generated.ts`: generated stat metadata from backend world data; regenerate via `scripts/sync_stat_definitions.py --write`.
- `zjus-frontend/src/utils/statDisplay.ts`: shared frontend helper for stat labels, icons, defaults, min/max ranges, values, and progress percentages.
- `zjus-frontend/src/components/CharacterCreate.vue`: major selection and stat budget UI driven by generated stat metadata.
- `zjus-frontend/src/composables/useGameWebSocket.ts`: auth handshake, heartbeat, message dispatch.
- `zjus-frontend/src/stores/gameStore.ts`: global game state, feedback modal, pause/guide flags, cooldowns.
- `zjus-frontend/src/components/RightPanel.vue`: relax actions, cooldown lockout, content generation mode switch.
- `zjus-frontend/src/components/modals/FeedbackModal.vue`: random-event, relax-result, DingTalk, and item feedback.

Docs:

- User docs: `docs/user/*`
- Developer docs: `docs/dev/*`
- World-data maintenance guide: `docs/dev/world-data.md`
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

- Initial allocatable stats come from `world/stat_definitions.json`; currently `IQ`, `EQ`, `Luck`, and `Charm` each range from 50 to 150.
- The client and server both enforce `initial_budget` from the stat registry, currently 300.
- `POST /api/init_character` accepts the preferred `stats` map plus legacy `iq`/`eq`/`luck`/`charm` fields for compatibility.
- Major IQ bonus is added after the base-budget check and is intentionally retained.
- Frontend stat display must read labels/defaults/caps from `statDefinitions.generated.ts` or `statDisplay.ts`; do not hardcode stat labels such as `金币`/`魅力` or numeric caps such as `100`/`200` inside components.
- Backend stat defaults and clamps should use `stat_definitions`: `PlayerStats`, `RedisRepository.update_stat_safe()`, item effective stats, event library filtering, and LLM/DingTalk context all consume the registry.

Returning users:

- `POST /api/auth` returns `status: "returning"` with save summaries when a valid student credential is supplied.
- The frontend shows `SaveSelect`, where the player loads a listed save slot or starts a new game.

WebSocket:

- First message sends `token`, optional `load_save_slot`, optional custom LLM fields, and optional `custom_rp_api_key`.
- `auth_ok` means the connection is usable. The frontend must not automatically send `resume`; backend owns startup through `engine.start()`.
- `init` and `tick` include `relax_cooldowns`; `init` also includes `items_state`, and item buy/sell changes emit `items_state`.
- `feedback` messages show user-facing result popups while `event` logs remain in "求是园动态".
- Backend outbound sends are serialized per user in `ConnectionManager`; do not bypass `send_personal_message()` for normal game messages. `save_and_exit` sends `save_result(success=true)`, then `exit_confirmed`, then clears Redis and closes the socket with code `1000`.

Guide/pause:

- The first-play guide pauses backend ticking and freezes frontend local countdown through `isGuideActive`.
- Resume only after the guide finishes or the user explicitly resumes.
- Backend pause enforcement uses the existing `GameEngine.is_running` flag as the single source of truth. When it is false, gameplay mutation actions such as `relax`, `exam`, `event_choice`, `dingtalk_reply`, `item_buy`, `item_sell`, and `change_course_state` are rejected server-side; navigation/state actions and `next_semester` after `exam_completed=1` remain allowed.

Semester transitions:

- New semesters reset courses and course states, reset elapsed time, and recover energy halfway toward 100 with `ceil((100 + current_energy) / 2)` without reducing energy already above 100.
- Final exams compute both a term GPA and a cumulative GPA by credit-weighted grade points. `PlayerStats.gpa` stores cumulative GPA; `highest_gpa` stores the best single-term GPA for achievements/user summary; `gpa_points_total` and `gpa_credits_total` persist the cumulative weighted totals.

Relax actions:

- `gym`, `game`, `walk`, and `cc98` have server-side cooldowns.
- Cooldown buttons are disabled and display remaining seconds.
- Relax results show a feedback modal for 3 seconds and still append logs; the feedback `changes` list should include the actual stat deltas players need to see.
- Positive relax effects that hit the good endpoint are partially redirected to `energy`, then `sanity`, then `charm`; this overflow rule is relax-only and does not affect random events, DingTalk settlements, or item passives. Gym can grant charm through `relax_actions.gym.charm_gain_probability` and `charm_gain`.

Random events:

- Event choices are validated against the current server-side event.
- Results show a feedback modal for 5 seconds and still append logs.
- Event and DingTalk effects are limited by `allow_event_effect` in `world/stat_definitions.json`; item passive bonuses are computed separately and should not be written back into base stats.

Achievements:

- `_check_achievements()` returns newly unlocked achievement details, emits `achievement_unlocked`, and final-exam summaries include the achievements unlocked during that semester.
- Social achievements should require both stat thresholds and behavior evidence; `social_butterfly` uses EQ/Charm thresholds plus completed DingTalk round counts from `action_counts.dingtalk_round`, not initial stats alone.
- Graduation payloads should include `achievement_details` derived from `world/achievements.json`; frontend fallbacks may display legacy code-only achievements.
- End screens expose both restart and return-home actions. Returning home disconnects the game WebSocket, disables reconnect, clears per-session game JWT/slot markers, and keeps the long-lived student credential.

Items:

- Item definitions live in `zjus-backend/world/items.json`; `app/game/items.py` validates the catalog and falls back to an empty catalog on config errors.
- Item `effects` are limited by `allow_item_effect` in `world/stat_definitions.json`; adding an ordinary item should only require editing `items.json` and running world-data validation.
- `/admin/items` can publish the same `items.json` file with validation, atomic replacement, `items.reload()`, and `items_update` audit logging; use it for operational price/effect/catalog edits when a UI is preferable to hand-editing JSON.
- `PlayerStats.gold` is real persisted currency. New games use `economy.initial_gold`; final exams use `economy.exam_income`; random events and DingTalk settlements may also change gold.
- Items are v1 limited to one owned copy per `item_id`. They are hold-to-activate passive bonuses; selling removes the bonus and refunds `sell_price`.
- Backpacks persist through Redis `player:{id}:items_state` and PostgreSQL `game_saves.items_data`.
- Passive bonuses produce effective stats for tick/exam/Game Over/LLM context/UI and must not be repeatedly written into base Redis stats.

World data:

- `world/stat_definitions.json` is the stat single source of truth. After changing it, run `python scripts/sync_stat_definitions.py --write` from `zjus-backend/`, then `python scripts/validate_world_data.py`.
- Use `scripts/scaffold_game_stat.py add <stat_id>` to draft a new stat definition and review checklist; it does not modify gameplay code unless called with `--write`.
- `validate_world_data.py` checks stat definitions, item effects, event-library effects, and generated frontend stat metadata freshness.
- `game_balance.json.tick.interval_seconds` is the actual engine tick interval used by `GameEngine.run_loop`; keep balance docs/admin validation aligned with this runtime behavior.

Content generation:

- Modes are `library`, `hybrid`, and `ai`.
- DingTalk model selection order is: player custom RP MiniMax key, platform M2-her when no general custom LLM is configured, then the active general LLM fallback.
- General OpenAI-compatible LLM clients use an explicit timeout. Platform-default clients may be cached and are closed on FastAPI shutdown; player custom LLM clients are closed after each call and their generated CC98/event/DingTalk fallback content must not enter the shared Redis content pools.
- DingTalk contact lists are capped by `events.dingtalk.max_contacts` (default 12). New message generation applies `reuse_closed_contact_probability` exactly once before generation; reusable closed contacts are selected with a bias toward contacts that have been quiet longer, and compact must not remove open-round contacts.
- When AI/LLM becomes unavailable, AI mode falls back toward hybrid mode(if still have issues, then fall back to library mode) behavior and emits mode/toast updates.

Admin world-data editors:

- `/admin/balance` edits only the existing numeric/short-text fields in `zjus-backend/world/game_balance.json`; v1 does not add/delete speed modes, course strategies, relax actions, or arbitrary JSON nodes.
- Saving validates the full config, atomically replaces the JSON file, calls `balance.reload()`, and records `balance_update` in `admin_audit_logs`.
- `/admin/items` edits `zjus-backend/world/items.json` economy fields and item catalog entries. Existing item IDs are read-only in the UI; create/delete/price/tag/effect edits validate `allow_item_effect`, atomically replace the file, call `items.reload()`, and record `items_update`.
- "Restore latest" reads the previous config from the latest matching update audit row, writes it back, hot reloads, and records `balance_restore` or `items_restore`.
- These admin pages do not change player HTTP APIs, WebSocket contracts, OpenAPI, or database schema.

## Pylance Notes

Common backend noise should be fixed by narrowing types rather than suppressing:

- Use `Coroutine[Any, Any, Any]` for helpers that pass coroutine objects into `asyncio.create_task`.
- Use SQLAlchemy async types (`AsyncSession`, `async_sessionmaker`) for async DB code.
- Normalize optional strings before `.strip()`, `json.loads`, `compare_digest`, or service calls.
- Keep Redis calls async; fix imports/types instead of deleting `await`.
- Convert numeric Redis hash values to strings if stubs require string values.
- Guard OpenAI response `content` because SDK types allow `None` and mixed content shapes.

## Related Project Skills

Claude Code can use project skills in `.claude/skills/`. The Codex-side workflows in `.codex/skills/` are also useful references:

- `zjus-compose-openapi`: Docker Compose backend + OpenAPI regeneration.
- `zjus-docs-sync`: docs synchronization after product/API changes.
- `zjus-game-stat`: gameplay stat registry additions/updates, frontend metadata sync, and validation.
- `zjus-game-item`: item catalog additions/updates, item effect allowlists, and validation.
- `zjus-player-onboarding`: auth, saves, character creation, and stat-budget flow.
- `zjus-pylance-noise`: project-specific Pylance/Pyright cleanup.
- `zjus-change-review`: broad frontend/backend regression review.

## Rule for maintaining up-to-date documentation (.claude\CLAUDE.md & AGENTS.md):

- Trigger: After any modification or refactoring (e.g., backend API, database schema, logic migration).
- Action: Update or supplement the file to match the new state.
- Goal: To provide accurate, current information for current agent or other agents taking over development.
