# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ZJUers Simulator (折姜大学模拟器) - A Zhejiang University simulation game with LLM-powered content generation.

- **Frontend**: Vue 3 + TypeScript + Vite + Pinia @[docs/dev/framework/frontend_framework.md]
- **Backend**: Python/FastAPI + SQLAlchemy + PostgreSQL + Redis @[docs/dev/framework/backend_framework.md]
- **World Data**: JSON files (courses, characters, achievements, majors) in `zjus-backend/world/`

## Quick Commands

### Setup
```bash
./setup.sh              # Linux/macOS quick start
./setup.ps1             # Windows quick start
docker compose up -d    # Docker deployment
```
See @[docs/dev/setup.md] for full setup details.

### Backend (zjus-backend/)
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload   # Dev server on :8000
python -m pytest tests/ -v      # Run tests
alembic upgrade head            # Apply migrations
ruff check . --fix && ruff format .  # Lint & format
```
See @[docs/dev/test.md] for testing details.

### Frontend (zjus-frontend/)
```bash
npm install
npm run dev              # Dev server on :3000 (proxies API to :8000)
npm run build            # Production build
npm run test             # Run Vitest
npm run type-check       # TypeScript check
npm run gen:api          # Generate API types from OpenAPI spec
```

### Docs
```bash
mkdocs serve             # Local server on :8080
mkdocs build
```

## Architecture Overview

### Backend Structure
```
app/
├── api/           # Route handlers (auth, game, deps)
├── core/          # Config, database, LLM, security
├── models/        # SQLAlchemy ORM models
├── services/      # Business logic (game_service, world_service)
├── game/          # Engine (engine.py), state, balance, access
├── websockets/    # Connection manager with heartbeat
└── admin.py       # SQLAdmin panel
```

**Key Patterns**:
- FastAPI dependency injection @[app/api/deps.py]
- Async SQLAlchemy with `asyncpg`
- Redis for active game state (TTL: 24h)
- PostgreSQL with pgvector for embeddings

See @[docs/dev/framework/backend_framework.md] for detailed backend architecture.

### Frontend Structure
```
src/
├── api/client.ts              # API client
├── stores/gameStore.ts        # Pinia state management
├── composables/               # useGameWebSocket.ts
├── components/                # Vue components by game phase
└── types/                     # TypeScript definitions
```

**Key Patterns**:
- Pinia single store for game state
- Options API (not Composition API)
- WebSocket real-time sync
- Phase-based view switching: login → admission → playing → ended

See @[docs/dev/framework/frontend_framework.md] for detailed frontend architecture.

### World Data System
Game content lives in `zjus-backend/world/`:
- `courses/` - 40 course JSON files by major/tier
- `characters.json`, `majors.json`, `achievements.json`
- `game_balance.json` - Numerical parameters
- `event_library.json`, `cc98_library.json` - Pre-generated content
- `query_embeddings.json`, `character_embeddings.csv` - Vector assets

Loaded at startup by `WorldService` and mounted at `/world` endpoint.

### Pre-built Content Pipeline
The game uses offline pre-built assets + runtime retrieval (not LLM-every-request):
1. **Generate**: `scripts/generate_content_library.py` → JSON libraries
2. **Embed**: `scripts/embed_world_data.py --csv-only` → vectors
3. **Import**: `scripts/import_character_embeddings.py` → pgvector
4. **Runtime**: Engine retrieves from local JSON/vectors first, LLM fallback only when needed

See @[docs/dev/setup.md] "本地预构建资产流程" section.

## Environment Variables

Critical vars in `.env` (see `.env.template`):
- `DATABASE_URL`, `REDIS_URL` - Data stores
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM` - LLM provider
- `SECRET_KEY` - JWT signing
- `ADMIN_USERNAME`, `ADMIN_PASSWORD` - Admin panel

## Deployment

- Production: `docker compose up -d` (pulls pre-built images)
- Local dev: `docker compose up -d --build` (builds locally with hot-reload)
- Bare metal: See @[docs/user/local_deploy_bare.md]

See @[docs/user/local_deploy.md] for deployment details.

## Key Files

| Purpose | Path |
|---------|------|
| Backend entry | `zjus-backend/app/main.py` |
| Game engine | `zjus-backend/app/game/engine.py` |
| WebSocket handler | `zjus-backend/app/api/game.py` |
| Frontend entry | `zjus-frontend/src/main.js` |
| Game store | `zjus-frontend/src/stores/gameStore.ts` |
| API client | `zjus-frontend/src/api/client.ts` |
| Docker compose | `docker-compose.yml` |
