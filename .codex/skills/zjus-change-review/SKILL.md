---
name: zjus-change-review
description: "Review large ZJUers Simulator commits or working-tree changes that touch frontend and backend behavior, especially auth, character initialization, saves, WebSocket contracts, OpenAPI types, database migrations, docs, or Docker Compose. Use when the user asks for a review, regression check, or risk scan of recent changes."
---

# ZJUS Change Review

## Overview

Review from a failure-first stance: startup blockers, broken contracts, data loss, auth regressions, stale generated types, and missing migrations outrank style concerns.

## Review Order

1. Get the change shape.

```powershell
git show --stat --oneline --decorate HEAD
git show --name-only --format=short HEAD
git diff --stat
```

2. Check backend startup and schema drift.
   - Import `app.main` from `zjus-backend`.
   - Look for ORM fields removed from `models/*` but still referenced by admin/API/services.
   - Check Alembic migrations when models change.
   - Verify Pydantic response models match actual service data types.

3. Check frontend/backend contracts.
   - `api.generated.ts` must reflect compose backend OpenAPI.
   - `client.ts` should import generated schema types and remain a thin wrapper.
   - Watch for stale endpoint names such as old entrance exam routes.

4. Check auth and player flow.
   - JWT and persistent player credential must not be mixed.
   - Returning users must not be forced into character creation unless intentionally starting a new game.
   - Loading a save should use the selected slot and force DB load.
   - New game should reset Redis state before initialization.

5. Run focused validation where practical.

```powershell
..\.venv\Scripts\python.exe -m pytest
.\node_modules\.bin\vue-tsc.cmd --noEmit
cd docs
npm run build
```

Use project-local frontend binaries when npm wrapper behavior is affected by the Codex sandbox. Do not claim the user's local npm is broken based only on sandbox npm failures.

## High-Risk Patterns

- Backend imports fail because admin, routes, or services reference removed ORM fields.
- A generated type file remains stale after backend route/schema changes.
- A response model uses `Dict[str, str]` for mixed course data that includes numeric fields.
- Frontend phase routing lets refresh bypass save selection or enter character creation incorrectly.
- LocalStorage names obscure whether a value is JWT or persistent token.
- Client-side-only validation can be bypassed by direct API calls.
- DB migrations disagree with current SQLAlchemy models.

## Output Format

For review responses, lead with findings ordered by severity. Include file links and line numbers. Then list open questions, then brief validation notes. If there are no findings, say that clearly and name residual test gaps.
