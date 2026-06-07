---
name: zjus-docs-sync
description: "Update ZJUers Simulator documentation after product, API, onboarding, deployment, architecture, or agent-workflow changes. Use when modifying MkDocs pages, README files, AGENTS.md, .claude/CLAUDE.md, user guides, developer guides, navigation, screenshots/previews, API docs, setup docs, or when removing stale references such as the old entrance exam flow."
---

# ZJUS Docs Sync

## Overview

Keep user-facing and developer-facing docs aligned with the actual app behavior. Prefer concise docs that explain current flows, not history, unless a migration/removal note is useful.

## Map

- MkDocs config: `mkdocs.yml`
- User guide: `docs/user/*`
- Developer guide: `docs/dev/*`
- Preview pages: `docs/preview/*`
- General FAQ/index: `docs/faq.md`, `docs/index.md`
- Repository landing docs: `README.md`, `README_en.md`
- Agent handoff docs: `AGENTS.md`, `.claude/CLAUDE.md`
- Agent skills/workflows: `.codex/skills/*`, `.agents/skills/*`

## Workflow

1. Search for stale terms before editing:

```powershell
rg -n "\u{5165}\u{5b66}\u{8003}\u{8bd5}|\u{5f55}\u{53d6}\u{901a}\u{77e5}|exam|admission|assign_major|quick_login|AdmissionScreen|Exam" docs README.md README_en.md mkdocs.yml
```

2. Update user docs for player-visible behavior first.
   - Current entry flow is invite-code login, character creation, and returning-user save selection.
   - Preserve course/final-exam content when it refers to in-game semesters, not removed entrance exams.
   - Mention Library/AI/Hybrid content generation modes where relevant.

3. Update developer docs for contracts and maintenance.
   - HTTP docs should reflect `/api/auth`, `/api/majors`, `/api/init_character`, `/api/admission_info`, and generated OpenAPI types.
   - Frontend docs should describe `LoginView`, `CharacterCreate`, `SaveSelect`, WebSocket connection, and `client.ts`/`api.generated.ts` responsibilities.
   - Backend docs should describe JWT/session auth, Redis state, Postgres saves, migrations, and compose-first API generation.

4. Sync agent-facing handoff docs when workflows or maintenance rules change.
   - Check `AGENTS.md` and `.claude/CLAUDE.md` for any new project rules, verification commands, Docker/OpenAPI guidance, ownership boundaries, or handoff assumptions introduced by the change.
   - If a workflow skill changes how agents should work, update the relevant `.codex/skills/*` or `.agents/skills/*` file as part of the same documentation pass.
   - Treat agent docs as living operational docs, not static background notes: keep them concise, current, and aligned with actual repo behavior.

5. Wire new pages into `mkdocs.yml` cleanly.
   - Keep user-guide pages under the existing user section.
   - Remove nav entries for deleted preview pages.
   - Avoid adding generated or planning notes to nav unless the user asks.

6. Validate with strict MkDocs build:

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

If MkDocs reports an existing unnaved planning file, note it only if unchanged and unrelated.

## Style

- Match the language and tone of neighboring docs.
- Keep user docs task-oriented and concise.
- Keep developer docs contract-oriented with exact file/API names.
- Do not document local uvicorn as the OpenAPI generation path; use Docker Compose backend for that.
- Avoid preserving old removed-flow details except in explicit migration notes.
