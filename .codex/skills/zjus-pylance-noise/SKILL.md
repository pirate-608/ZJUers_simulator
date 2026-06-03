---
name: zjus-pylance-noise
description: Triage and reduce Pylance/Pyright diagnostics in ZJUers Simulator. Use when Codex sees or is asked about Python/Pylance/Pyright warnings in the FastAPI backend, SQLAlchemy async models/sessions, Redis asyncio calls, OpenAI response parsing, Pydantic schemas, import resolution, venv interpreter drift, generated/cache diagnostics, or editor-only type noise that should be cleaned without hiding real defects.
---

# ZJUS Pylance Noise

## Goal

Handle Pylance/Pyright warnings without hiding real defects or changing unrelated runtime behavior. Prefer real type narrowing, safer parsing, correct async APIs, and small helper types over broad suppressions.

## Workflow

1. Capture the exact diagnostic:
   - file path, line, diagnostic code, message, selected Python interpreter, and whether it appears only in VS Code/Pylance.
   - If the user provides a screenshot, transcribe the diagnostic before acting.

2. Classify the warning:
   - **Real bug**: runtime import failure, bad path, wrong API use, impossible type, or failing test.
   - **Environment drift**: wrong interpreter, stale venv, missing package, wrong workspace root, or Pylance indexing a generated/cache directory.
   - **Analyzer limitation**: dynamic imports, SQLAlchemy descriptor typing, Redis overload gaps, OpenAI SDK union responses, optional dependency, conditional platform code, or library without useful type stubs.
   - **Style preference**: strictness choice such as unknown member/type noise.

3. Verify before editing:
   - Inspect existing project config first: `.vscode/settings.json`, `zjus-backend/pyproject.toml`, `zjus-backend/requirements.txt`, `docs/requirements.txt`, `.venv/`, Docker Compose files, and related scripts.
   - Run the smallest relevant command when useful, such as `..\.venv\Scripts\python.exe -m py_compile app\path\file.py` from `zjus-backend`, a focused pytest file, or a docs build if docs Python changed.
   - Do not assume a Pylance warning is false. `zjus-backend` is production Python code, not just tooling.

4. Choose the narrowest fix:
   - Wrong interpreter or venv: configure interpreter path or document activation; do not edit application code.
   - Missing dependency: add it only to the appropriate requirements file if the project actually uses it.
   - Generated/cache noise: exclude the directory from analysis.
   - Missing stubs or dynamic library typing: prefer local type narrowing, `typing.cast`, protocol definitions, or small wrapper functions.
   - Last resort: use per-line `# type: ignore[...]` / `# pyright: ignore[...]` with a reason.

## Project Defaults

This repository is a Python/FastAPI backend plus Vue frontend monorepo:

- Backend source of truth: `zjus-backend/app/**`
- Backend tests: `zjus-backend/tests/**`
- Backend config: `zjus-backend/pyproject.toml`, `zjus-backend/requirements.txt`
- Frontend TypeScript/OpenAPI files are handled by `zjus-compose-openapi` when backend HTTP models/routes change.
- Docs Python tooling is secondary and uses `docs/requirements.txt`.

Treat these paths as likely editor noise sources unless the user is explicitly working on them:

- `.venv/`
- `site/`
- `dist/`
- `dist-sea/`
- `node_modules/`
- `.pytest_cache/`
- generated documentation artifacts

Prefer exclusions over code changes only when diagnostics come from generated/cache/dependency paths. For `zjus-backend/app/**`, first look for a narrow source fix.

Use the workspace virtual environment when validating Python tooling:

```powershell
.\.venv\Scripts\python.exe --version
cd zjus-backend
..\.venv\Scripts\python.exe -m py_compile app\game\engine.py
..\.venv\Scripts\python.exe -m pytest tests\unit\test_game_state.py
```

For docs-only diagnostics, validate with:

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

For frontend checks, prefer project-local binaries and remember the user's npm is not the problem when Codex sandbox npm commands fail:

```powershell
cd zjus-frontend
.\node_modules\.bin\vue-tsc.cmd --noEmit
```

Do not start local backend services directly. If backend HTTP schemas/routes change and OpenAPI must be regenerated, use the `zjus-compose-openapi` skill and Docker Compose from the repository root.

## Common ZJUS Fix Patterns

- `asyncio.create_task` with `Awaitable`: narrow helper parameters to `Coroutine[Any, Any, Any]` when all callers pass `async def` coroutine objects.
- SQLAlchemy async sessions: import/use `async_sessionmaker` and `AsyncSession`; avoid typing async factories as sync `sessionmaker`/`Session`.
- SQLAlchemy ORM instance attributes reported as `Column[...]`: narrow after database fetches with `isinstance(value, User)` or cast ORM objects at the boundary; avoid passing class descriptors to Pydantic/JWT helpers.
- Redis asyncio methods reported as non-awaitable: ensure imports come from `redis.asyncio`, annotate repository clients as the async Redis type or a small protocol, and cast Redis return values after runtime decoding. Do not remove `await` just to appease Pylance.
- Redis hash values: convert numeric values to `str` before `hset` when the current stub overload only accepts strings.
- OpenAI SDK responses: guard optional `content`, normalize list/string content before `json.loads`, and provide a non-optional model string before `client.chat.completions.create`.
- FastAPI dependency values: annotate request/dependency parameters precisely; normalize optional form/query fields before `.strip()`, `compare_digest`, or service calls.
- Logging extras: use `getattr(record, "field", default)` or a typed dict payload rather than direct unknown `LogRecord` attributes.
- Dynamic JSON/state data: validate with `isinstance`, `pydantic` models, or small conversion helpers before passing to typed functions.

## Suppression Rules

Avoid broad suppressions unless the user asks for a workspace-wide policy change:

- Avoid setting type checking to `off` for the whole workspace.
- Avoid disabling all diagnostics.
- Avoid adding blanket `reportMissingImports = false` unless the warning is from generated, optional, or platform-specific code and narrower fixes are not viable.
- Avoid adding imports or dependencies just to satisfy Pylance when runtime does not need them.
- Avoid removing `await`, changing async/sync APIs, or weakening validation just because a third-party stub is inaccurate.

When suppression is justified, make it traceable:

```python
# pyright: ignore[reportUnknownMemberType]  # dynamic API returns runtime-validated object
```

## Recommended VS Code Settings Shape

Use only if the project has VS Code settings or the user asks for editor-level cleanup:

```json
{
  "python.analysis.exclude": [
    "**/.venv/**",
    "**/site/**",
    "**/dist/**",
    "**/dist-sea/**",
    "**/node_modules/**",
    "**/.pytest_cache/**"
  ],
  "python.analysis.diagnosticMode": "workspace",
  "python.defaultInterpreterPath": "${workspaceFolder}\\.venv\\Scripts\\python.exe"
}
```

Do not create `.vscode/settings.json` just because Pylance is noisy; first confirm the warning is editor-scope and not a real project issue.

If a workspace setting is justified, keep it scoped to analysis hygiene. Do not rewrite formatting, linting, or TypeScript settings as part of Pylance cleanup.

## Response Pattern

Report the result in this order:

1. diagnostic classification,
2. evidence checked,
3. fix applied or recommended,
4. residual risk if any.
