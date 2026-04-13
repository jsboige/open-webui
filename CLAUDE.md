# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **fork/clone of Open WebUI** (v0.8.5) — an extensible, self-hosted AI chat platform. This instance runs **multiple tenant deployments** via per-tenant docker-compose and env files.

**Stack**: SvelteKit 2 + Svelte 5 (frontend) / FastAPI 0.128 + SQLAlchemy 2 (backend) / Python 3.11+

> **Deployment details** (infrastructure, tenants, services, machine fleet, maintenance roadmap) are in `.claude/DEPLOYMENT.md` (not committed — local only).

## Development Commands

### Frontend (SvelteKit + Vite)
```bash
npm run dev              # Dev server with HMR (runs pyodide:fetch first)
npm run build            # Production build
npm run lint:frontend    # ESLint with --fix
npm run lint:types       # svelte-check type validation
npm run format           # Prettier formatting
npm run test:frontend    # Vitest tests
npm run i18n:parse       # Extract i18n translation keys
```

### Backend (FastAPI + Uvicorn)
```bash
open-webui serve         # Production server on port 8080
open-webui dev           # Dev server with auto-reload
bash backend/start.sh    # Docker entrypoint (configurable workers)
```

### Combined Lint
```bash
npm run lint             # Runs lint:frontend + lint:types + lint:backend (pylint)
```

### Docker (default compose, includes Ollama)
```bash
make install             # docker compose up -d
make startAndBuild       # docker compose up -d --build
make stop                # docker compose stop
make update              # git pull + rebuild + restart
```

### Testing
- **Frontend**: `npm run test:frontend` (Vitest)
- **E2E**: Cypress (`cypress/` directory)
- **Backend**: `pytest` (optional deps in pyproject.toml `[project.optional-dependencies]`)

## Architecture

### Backend (`backend/open_webui/`)
- **`main.py`** — FastAPI app init, all middleware (CORS, sessions, compression, audit), mounts all routers and socket.io
- **`env.py`** — All environment variable loading (extensive, 400+ lines). Loads `.env` from repo root
- **`routers/`** — One file per domain: `ollama.py` and `openai.py` proxy LLM APIs; `retrieval.py` handles RAG (largest router); `auths.py` for JWT/LDAP/OAuth
- **`models/`** — SQLAlchemy 2 models. Each file typically defines a `Model`, `Form` classes, and a `ModelTable` class with CRUD methods
- **`internal/db.py`** — Database engine setup (SQLite default, PostgreSQL supported). Uses both SQLAlchemy and Peewee (legacy migrations via peewee-migrate, new migrations via Alembic)
- **`socket/main.py`** — Socket.IO for real-time chat streaming, user presence, model status broadcasting
- **`storage/provider.py`** — Pluggable storage abstraction (local, S3, Azure Blob, GCS)
- **`retrieval/`** — RAG components: embedding, reranking, vector DB clients (ChromaDB, Qdrant, Elasticsearch, Pinecone, PGVector, etc.)

### Frontend (`src/`)
- **`routes/(app)/`** — Main app (auth-protected): chat (`c/[id]`), admin panel, workspace (models/prompts/tools/knowledge/functions), channels, notes
- **`routes/auth/`** — Login/signup page
- **`lib/apis/`** — Typed API client wrappers matching backend routers
- **`lib/components/`** — Reusable Svelte components (chat, admin, workspace, common)
- **`lib/stores/`** — Svelte stores for global state management
- **`lib/i18n/`** — i18next translations (many locales)
- **`lib/utils/`** — Shared utility functions

### Key Patterns
- **Auth**: JWT tokens via `python-jose`, RBAC with user groups. Multiple backends (local, LDAP, OAuth, SAML, SCIM 2.0)
- **Real-time**: python-socketio for streaming chat responses and presence
- **Sessions**: StarSessions with optional Redis backend for horizontal scaling
- **Config**: Most settings stored in database and configurable at runtime via admin UI. Environment variables in `env.py` serve as defaults/overrides
- **Migrations**: Dual system — Peewee-migrate (legacy `backend/open_webui/migrations/`) and Alembic. Run automatically on startup if `ENABLE_DB_MIGRATIONS=true`

## Key Environment Variables

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///...webui.db` |
| `VECTOR_DB` | Vector DB backend | `chroma` |
| `QDRANT_URI` | Qdrant server URL | — |
| `WEBSOCKET_REDIS_URL` | Redis for WebSocket pub/sub | — |
| `WEBSOCKET_REDIS_LOCK_TIMEOUT` | Redis lock TTL (seconds) | `60` |
| `WEBUI_SECRET_KEY` | JWT/session secret | auto-generated |
| `ENABLE_OLLAMA_API` | Ollama feature toggle | `true` |
| `AIOHTTP_CLIENT_TIMEOUT` | HTTP client timeout | `300` |
| `STORAGE_TYPE` | File storage (`local`, `s3`, etc.) | `local` |

## Git & Remotes

- `origin` → `jsboige/open-webui` (fork, pour pousser)
- `upstream` → `open-webui/open-webui` (officiel, pour tirer les mises à jour)
- Upstream is tracked on `main`; local work on `dev`
- Sync upstream: `git fetch upstream && git rebase upstream/dev && git push origin dev`

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/preflight-cleanup.py` | Delete broken functions, clean model filterIds, purge spam, delete old KBs |
| `scripts/configure-tenant.py` | Clone all config sections from myia to tenants via API (6 sections: OpenAI, Embedding, Audio, Image, RAG, Tool Servers) |
| `scripts/shallow-copy-kbs.py` | Copy KB metadata between PostgreSQL databases (same UUIDs = shared Qdrant vectors) |
| `scripts/install-community-functions.py` | Install/update community functions and tools (8 total) |
| `scripts/migrate-sqlite-to-postgres.py` | SQLite→PG migration (runs inside container, SAVEPOINT-based error handling) |
| `scripts/bulk-kb-upload.py` | Host-side PDF uploader with skip-existing, delay, size filtering |
| `scripts/create-thematic-kbs.py` | Create thematic KBs from Bibliographie IA subdirectories |
| `scripts/checklist-tenant-verification.md` | Pre-course/deployment checklist for tenant instances |

## Notes

- The `.env` files at root (myia.env, epf.env, etc.) contain secrets — never commit them. The `.gitignore` blocks `*.env` and allows `*.env.example`
- Use `tenant.env.example` as template for new tenants
- The Dockerfile is a multi-stage build: Node.js (frontend) → Python 3.11 slim (backend), exposed on port 8080 internally
- Build args `USE_CUDA`, `USE_OLLAMA`, `USE_SLIM` control Dockerfile variants
- Docker Compose `--env-file` only interpolates into the compose file — variables must also be in the `environment:` section to reach the container
- Tika image has wget, NOT curl — healthcheck must use `wget --spider -q`
- Volume naming: volumes are prefixed with project name. Use `external: true` + `name:` to reference existing volumes when changing project names
