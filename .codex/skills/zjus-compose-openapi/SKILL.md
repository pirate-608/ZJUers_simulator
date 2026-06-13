---
name: zjus-compose-openapi
description: "Keep the ZJUers Simulator Docker backend, FastAPI OpenAPI contract, generated frontend TypeScript schemas, and thin API client in sync. Use when backend HTTP models/routes change, when src/types/api.generated.ts or src/api/client.ts may be stale, when debugging API response validation errors, or when asked to regenerate OpenAPI/types for this project."
---

# ZJUS Compose OpenAPI

## Overview

Use the repository root Docker Compose stack as the source of truth for the running backend. Do not start a local uvicorn/FastAPI process to generate OpenAPI for this project.

## Workflow

1. Inspect the relevant backend schema/route changes first.
   - API models usually live in `zjus-backend/app/api/*.py`.
   - Shared behavior may live in `zjus-backend/app/services/*`, `repositories/*`, or `schemas/*`.

2. Rebuild and start the backend only through Docker Compose from the repository root:

```powershell
docker compose up -d --build backend
```

If Docker Engine access is denied by the sandbox, request escalation for the same `docker compose` command. The repo expects compose to orchestrate db, redis, migrations, seed jobs, and backend.
The production base compose file keeps the backend internal to the Docker network; `http://127.0.0.1:8000` is available only when the local `docker-compose.override.yml` publishes `127.0.0.1:8000:8000`.

3. Wait until the compose backend serves OpenAPI:

```powershell
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
```

4. Regenerate frontend API types from the running compose backend:

```powershell
.\node_modules\.bin\openapi-typescript.cmd http://127.0.0.1:8000/openapi.json -o src/types/api.generated.ts
```

Run that command from `zjus-frontend`. Prefer project-local binaries like `.\node_modules\.bin\vue-tsc.cmd`; do not treat Codex sandbox npm CLI failures as evidence that the user's local npm is broken.

5. Keep responsibilities clean.
   - `zjus-frontend/src/types/api.generated.ts` is generated from OpenAPI. Do not hand-edit it.
   - `zjus-frontend/src/api/client.ts` is the hand-written thin fetch wrapper. It should import schema types from `api.generated.ts`.
   - If the generated type is wrong, fix the backend Pydantic model and regenerate.

## Useful Checks

Use these after API or type generation work:

```powershell
..\.venv\Scripts\python.exe -m pytest
.\node_modules\.bin\vue-tsc.cmd --noEmit
docker compose logs --tail=200 backend
```

Run backend tests from `zjus-backend` and frontend type-checks from `zjus-frontend`.

## Failure Patterns

- If `/api/init_character` 500s after successful state writes, check response model validation in backend logs.
- If frontend code compiles against old endpoints, regenerate `api.generated.ts` from compose backend.
- If WebSocket auth fails after login, verify JWT and persistent user token have not been mixed.
- If Docker logs show old code, rebuild `backend` rather than generating from a local process.
