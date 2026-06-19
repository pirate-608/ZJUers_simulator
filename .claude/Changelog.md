# Claude Code Handoff Changelog

## 2026-06-19

### Charm Attribute

- Added `Charm` / `魅力` as a fourth allocatable character-creation stat.
- Current stat rules are `IQ`, `EQ`, `Luck`, and `Charm` each within `50-150`, with a total base budget of `300`.
- Major IQ bonus is still applied after base-budget validation.
- Charm is part of normal runtime state: UI stats, restart inference, event/DingTalk effects, item bonuses, and LLM context can now carry it.

## 2026-06-09

### VitePress Docs Migration

- Replaced the MkDocs Material documentation site with VitePress while keeping the existing page hierarchy and public routes.
- Moved documentation theme code, Vue components, and public image assets under `docs/`; root-level `overrides/` and MkDocs config/dependencies were removed.
- Rebuilt the docs homepage as a starfield/typewriter landing page and embedded a mock interactive Vue demo on the homepage.
- Updated docs deployment to run Node/VitePress from `docs/` and upload `docs/.vitepress/dist`.
- Current docs validation command is `cd docs; npm run build`.

## 2026-06-07

### Pre-login Prologue

- Added a first-visit, skippable prologue before the normal `GamePhase` flow.
- The prologue is a frontend startup gate, not a new game phase; while active, `App.vue` must not route to login/save/character pages or open the WebSocket.
- Seen state is stored as `localStorage.zjus_prologue_seen_v1`.
- Prologue text is embedded in `zjus-frontend/src/data/prologue.ts`; it does not fetch `/world/prologue.md` at runtime.
- `PrologueScene.vue` uses existing public image assets for mood transitions, including `sunset.webp` for the line about recorded smiles and "tomorrow will be better".
- Focused frontend tests cover first-visit display, skip behavior, and bypass after the seen flag is set.

### Docs And Handoff

- User docs now mention the first-visit prologue before login.
- Frontend framework docs and agent handoff docs describe the prologue gate and its localStorage key.
- No backend API, WebSocket, database migration, or OpenAPI regeneration was required.

## 2026-06-06

### DingTalk Private Chat Upgrade

- Reworked DingTalk from a simple message surface into persistent private threads grouped by character/contact.
- Only characters with messages appear in the contact list; unread contacts show red-dot/unread state.
- DingTalk state now carries contacts, messages, pending reply options, round metadata, and unread counts through the game lifecycle.
- Contact and conversation history persists across semester transitions and save/load boundaries.
- Replyable roles currently include `roommate`, `classmate`, `friend`, `teaching_assistant`, `teacher`, and `crush`, with role aliases normalized for Chinese labels such as "同学" and "室友".

### Reply Rounds And Stat Settlement

- Replyable contacts receive AI-generated player reply options.
- Three player replies to one contact count as one conversation round; after the NPC's third response in that round, AI settlement applies numeric effects.
- The MiniMax M2-her roleplay base, pgvector character retrieval, and embedding data shape were preserved.
- Fallback behavior remains in place when MiniMax, pgvector retrieval, or broader LLM services are unavailable.

### Frontend And WebSocket Contracts

- WebSocket handling now supports DingTalk state snapshots and per-thread updates alongside legacy message compatibility.
- The frontend store restores DingTalk contacts, recalculates unread counts, marks individual contacts read locally, and updates threads as messages arrive.
- The central panel now renders a contact list plus per-character private conversation view and reply options.
- Follow-up UI fixes kept long DingTalk threads scrollable so speed controls do not overlap extended conversation content.

### Save, Semester, And Regression Notes

- DingTalk state is included in active runtime state and persisted save data.
- Semester transition updates were tightened so the frontend immediately receives new semester stats, course metadata, and course states without requiring browser refresh.
- Focused DingTalk state tests, frontend type checks, Vitest, documentation build, and targeted backend checks were used during the upgrade.

## 2026-06-03

### Entry Flow And Saves

- Removed the old entrance-exam/admission-test mental model from handoff docs.
- Current player phases are `login`, `save_select`, `character_create`, `loading`, `playing`, and `ended`.
- Returning users log in with nickname, invite code, and long-lived student credential, then choose a listed save slot or start a new game.
- New games use `CharacterCreate` with major selection and stat allocation.

### Character Initialization

- This entry originally documented the three-stat onboarding model; the current four-stat `Charm` rules are tracked in the 2026-06-19 entry above.
- Major IQ bonus is retained and applied after the base-budget validation.

### API And OpenAPI

- HTTP models/routes are the source for generated frontend types.
- `zjus-frontend/src/types/api.generated.ts` is generated from the Docker Compose backend `/openapi.json`.
- `zjus-frontend/src/api/client.ts` remains the hand-written fetch wrapper.
- For OpenAPI regeneration, use root Docker Compose backend, wait until `/openapi.json` is reachable, and do not start a local bare `uvicorn` process.

### WebSocket And Gameplay UX

- WebSocket `auth_ok` no longer means the frontend should automatically send `resume`.
- Backend owns game startup through `engine.start()`.
- `init` and `tick` include `relax_cooldowns`.
- New-player guide pauses backend tick and freezes frontend countdown through `isGuideActive`.
- Relax buttons are disabled during cooldown and show remaining seconds.
- Random-event results show a feedback modal for 5 seconds while preserving event logs.
- Relax results (`gym`, `game`, `walk`, `cc98`) show a feedback modal for 3 seconds while preserving event logs.

### Content Generation Modes

- User-facing modes are `library`, `hybrid`, and `ai`.
- If AI/LLM availability drops, AI behavior falls back toward hybrid/library and emits mode/toast updates.
- Docs now include the mode switch and fallback behavior.

### Pylance And Backend Typing

- Several backend files were cleaned for Pylance/Pyright noise without changing runtime behavior.
- Common fixes include SQLAlchemy async typing, Redis asyncio typing, OpenAI response guards, optional string normalization, logging extras, and `Coroutine` typing for `asyncio.create_task` helpers.
- `.codex/skills/zjus-pylance-noise` contains a project-specific reference workflow that Claude can consult if needed.

### Documentation

- User/developer docs were updated for the current onboarding, saves, content generation modes, feedback modals, cooldowns, and WebSocket fields.
- The documentation site now builds with VitePress from `docs/`.

### Validation Notes

- Prefer focused validation while the working tree is large:
  - Backend syntax: `..\.venv\Scripts\python.exe -m py_compile <file>`
  - Focused backend tests: `..\.venv\Scripts\python.exe -m pytest tests\unit\test_onboarding_flow.py`
  - Frontend type check: `.\node_modules\.bin\vue-tsc.cmd --noEmit`
  - Docs: `cd docs; npm run build`
