---
name: zjus-player-onboarding
description: "Work safely on the ZJUers Simulator player entry flow: invite-code auth, JWT versus persistent user token handling, character creation, initial stat budget validation, returning-user save selection, WebSocket save loading, and new-game reset behavior. Use when modifying LoginView, CharacterCreate, SaveSelect, App phase routing, auth.py, game.py, GameService, SaveService, or related tests."
---

# ZJUS Player Onboarding

## Overview

This project's onboarding flow crosses HTTP, localStorage, Redis, Postgres saves, and WebSocket auth. Keep the contracts explicit and test both new-user and returning-user paths.

## Current Flow

1. `POST /api/auth` validates username, invite code, blacklist/restrictions, and optional persistent user token.
2. New users receive a JWT plus a persistent `user_token`, then go to character creation.
3. Returning users receive a JWT plus save summaries, then choose an existing save or start a new game.
4. `POST /api/init_character` validates JWT, major, and IQ/EQ/Luck/Charm budget, then writes a fresh Redis state.
5. The game WebSocket expects JWT auth in the first message. Loading an old save uses `load_save_slot`.

## Token Rules

- Treat `zju_jwt` and `zju_token` as JWT-compatible auth for current sessions.
- Store the long-lived player credential separately as `zju_user_token`.
- Never send `zju_user_token` to the WebSocket as the auth token.
- On logout, expired JWT, or invalid WebSocket auth, clear game-start/save-selection localStorage enough to avoid refresh loops.

## Stat Rules

- IQ/EQ/Luck/Charm must each be in `50..150`.
- Their sum must equal `300`.
- Preserve the major IQ bonus after validation; do not count the major bonus against the 300-point user budget unless the user explicitly asks to change the design.
- Enforce the budget server-side in `zjus-backend/app/api/auth.py`, not only in `CharacterCreate.vue`.

## Save Rules

- Returning users should not be forced into `CharacterCreate`.
- Loading an existing save should explicitly pass the selected slot and force DB-to-Redis loading.
- Starting a new game should clear/reset current Redis game data before initializing a fresh character.
- Preserve `save_slot` semantics even if the UI currently exposes only one slot; the table and service are slot-aware.

## Key Files

- Backend auth and schemas: `zjus-backend/app/api/auth.py`
- Backend WebSocket entry: `zjus-backend/app/api/game.py`
- Game state orchestration: `zjus-backend/app/services/game_service.py`
- DB save load/list logic: `zjus-backend/app/services/save_service.py`
- Redis write/reset logic: `zjus-backend/app/repositories/redis_repo.py`
- Frontend phase routing: `zjus-frontend/src/App.vue`
- Login and token storage: `zjus-frontend/src/components/LoginView.vue`
- Character creation: `zjus-frontend/src/components/CharacterCreate.vue`
- Save selection: `zjus-frontend/src/components/SaveSelect.vue`
- WebSocket client: `zjus-frontend/src/composables/useGameWebSocket.ts`

## Validation Checklist

Run focused tests for backend validation, then type-check frontend:

```powershell
..\.venv\Scripts\python.exe -m pytest
.\node_modules\.bin\vue-tsc.cmd --noEmit
```

For end-to-end API verification, use the compose backend, not a local uvicorn process.
