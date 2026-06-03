# Claude Code Handoff Changelog

## 2026-06-03

### Entry Flow And Saves

- Removed the old entrance-exam/admission-test mental model from handoff docs.
- Current player phases are `login`, `save_select`, `character_create`, `loading`, `playing`, and `ended`.
- Returning users log in with nickname, invite code, and long-lived student credential, then choose a listed save slot or start a new game.
- New games use `CharacterCreate` with major selection and stat allocation.

### Character Initialization

- `IQ`, `EQ`, and `Luck` each stay within `50-150`.
- Base stat total must equal `250` on both client and server.
- Major IQ bonus is retained and applied after the base-budget validation.

### API And OpenAPI

- HTTP models/routes are the source for generated frontend types.
- `zjus-frontend/src/types/api.generated.ts` is generated from the running backend `/openapi.json`.
- `zjus-frontend/src/api/client.ts` remains the hand-written fetch wrapper.
- For OpenAPI regeneration, use root Docker Compose backend; do not start a local bare `uvicorn` process.

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

- MkDocs user/developer docs were updated for the current onboarding, saves, content generation modes, feedback modals, cooldowns, and WebSocket fields.
- `mkdocs build --strict` was passing after the docs sync; existing unnaved planning notes may still be reported by MkDocs Material.

### Validation Notes

- Prefer focused validation while the working tree is large:
  - Backend syntax: `..\.venv\Scripts\python.exe -m py_compile <file>`
  - Focused backend tests: `..\.venv\Scripts\python.exe -m pytest tests\unit\test_onboarding_flow.py`
  - Frontend type check: `.\node_modules\.bin\vue-tsc.cmd --noEmit`
  - Docs: `.\.venv\Scripts\python.exe -m mkdocs build --strict`
