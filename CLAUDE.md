# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **fork/clone of Open WebUI** (v0.11.0) — an extensible, self-hosted AI chat platform. This instance runs **multiple tenant deployments** via per-tenant docker-compose and env files.

**Stack**: SvelteKit 2 + Svelte 5 (frontend) / FastAPI 0.136 + SQLAlchemy 2 (backend) / Python 3.11+

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
- **Auth**: JWT tokens via `PyJWT` (`utils/auth.py` imports `jwt`; `python-jose` was dropped upstream — `joserfc` remains for JWKS/OIDC), RBAC with user groups. Multiple backends (local, LDAP, OAuth, SAML, SCIM 2.0)
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
- Boot-testing an image with `docker run` and no config looks hung: a default install has `RAG_EMBEDDING_ENGINE` empty, so it downloads `sentence-transformers/all-MiniLM-L6-v2` (30 files) from HuggingFace before serving `/health`. The tenants never do this (external `openai` engine). Pass `-e RAG_EMBEDDING_ENGINE=openai` for a representative test — `/health` then answers in ~20s
- **`docker logs --since` can silently return nothing for a container that is logging fine.** A torn write (two json-file records spliced into one physical line, seen on a rollout restart) halts Docker's *forward* parser at that line: a full read and every `--since` window after the tear return nothing, while `--tail N` — which seeks backward from EOF — reads the recent lines correctly. Symptom: asking for *more* lines returns *fewer* (`--tail 1000` → 1000 recent lines, `--tail 100000` → 401 stale ones). A `--since` sweep then reports the tenant as quiet, and quiet reads as healthy. Detect fleet-wide with `python scripts/docker-log-health.py` (read-only, exit 1 if any container is affected; `--json` feeds a scanner directly); scan an affected container with `--tail N`, never `--since`, and keep N at or below the budget the script prints — it rises as the container logs, so re-measure every run. Overshooting is silent and does *not* simply return the stale head: `--tail budget+k` returns exactly `k-1` lines, all predating the tear, saturating at the pre-tear total (measured on epita at budget 2726: `+2` → 1 line, `+74` → 73 lines, `+402` → 401). A near miss is the trap — a handful of days-old lines reads as "quiet container", not as a failed read. The tear is permanent for the life of the log file — `docker restart` keeps appending to the same file, only `up -d --force-recreate` (or rotation at `max-size`) starts a new one
- **Fork `dev` is synced to `upstream/dev` but NOT deployed (source-only).** Last synced 2026-08-23 (+137 commits over the 2026-08-14 sync of 212, merge `7453bcafb`, clean both times; fork-only files never touched). The 7 tenants run the **official** image `v0.11.0` (`WEBUI_DOCKER_TAG`), not the fork's source — a source sync touches zero production. **Upstream tagged `v0.11.1` on 2026-08-25** (462 commits over v0.11.0: 97 fix, 308 refac, 29 perf, 7 feat; 2 new optional env vars, both default false — no compose change required). **The Alembic chain is LINEAR, single head `d4c1a8e37b62` — the earlier "divergent 2-head" reading (2026-08-14/23) was a misreading**: `b10670c03dd5` sits *inside* the main line (its child `90ef40d4714e` continues to `f0bd01a18a3d`); the graph walk on v0.11.0/v0.11.1/upstream/dev all yield exactly one head and a pure 58-node line (verified 2026-08-26). A fleet upgrade to the official v0.11.1 image would apply exactly 3 linear migrations on top of our `f0bd01a18a3d` (`1ce6ade7d93b` group index, `6d09d1bf1f23` oauth repair, `d4c1a8e37b62` chat timer/indexes) — the standard path. Deploy timing remains the operator's call (backup first, calm window). `npm run lint:types` is **non-gated** on this fork (~8k pre-existing errors from stale generated `src/lib/apis/` types); validate merges against that baseline, not zero.
- **`v0.11.2` (tagged 2026-08-31) supersedes v0.11.1 as the upgrade target** — it is a **security patch** (release notes: "includes security and access-control fixes… some withheld"; recommends updating production promptly) and also fixes the reasoning-model streaming stall (#29053) + thinking rendered into replies after tool calls (#29052), both relevant to the Qwen tutor workaround (`enable_thinking:false` may be re-evaluated post-upgrade). **Schema-verified 2026-09-01**: the v0.11.2 Alembic graph is identical to v0.11.1 for us — 58 revisions, zero merge points, single head `d4c1a8e37b62`, exactly the same 3 linear migrations on top of `f0bd01a18a3d` (no new migration in 0.11.2). Image `v0.11.2` pre-pulled locally (`77ff490214a4`, 7.16 GB). An upgrade therefore goes straight to `WEBUI_DOCKER_TAG=v0.11.2` — nothing extra to verify beyond the standing plan (backup 7/7 → staged `up -d --force-recreate` pilot+6 → health/version/alembic/preflight ×7 → rollback = PG restore; the recreate also repairs epita's torn log file).
