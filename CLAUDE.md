# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **fork/clone of Open WebUI** (v0.8.3, upgraded v0.7.2→v0.8.2 on 2026-02-16, then v0.8.2→v0.8.3 on 2026-02-19) — an extensible, self-hosted AI chat platform. This specific instance is used to run **multiple tenant deployments** (myia, epf, ece, esg, epita, pauwels, epf-genai) via per-tenant docker-compose and env files on the same machine.

**Stack**: SvelteKit 2 + Svelte 5 (frontend) / FastAPI 0.128 + SQLAlchemy 2 (backend) / Python 3.11+

## Multi-Tenant Architecture

### Infrastructure (shared services)

All tenants share a common infrastructure managed via `docker-compose-infra.yaml` (project `open-webui-infra`):

```bash
# Manage shared infra (PostgreSQL + Tika + Redis)
docker compose -p open-webui-infra -f docker-compose-infra.yaml up -d
docker compose -p open-webui-infra -f docker-compose-infra.yaml down
docker compose -p open-webui-infra -f docker-compose-infra.yaml logs
```

| Service | Container | Host Port | Internal Port | Notes |
|---------|-----------|-----------|---------------|-------|
| PostgreSQL 16 | `open-webui-postgres` | 5432 | 5432 | Shared DB server, one database per tenant |
| Tika | `open-webui-infra-tika-1` | 9917 | 9998 | Document extraction for RAG |
| Redis (Valkey) | `open-webui-infra-redis-1` | 6351 | 6379 | WebSocket pub/sub, DB isolation per tenant |

Redis DB allocation: myia=0, epf=1, epf-genai=2, ece=3, esg=4, epita=5, pauwels=6

**Important**: The PostgreSQL volume uses `external: true` with `name: myia-open-webui_postgres-data` to preserve data. Never change the compose project name without updating volume references.

### Myia sidecars (`docker-compose-myia.yaml`)

Myia hosts additional services shared by all tenants:

| Service | Container | Port | Notes |
|---------|-----------|------|-------|
| Pipelines | `myia-open-webui-pipelines-1` | 9099 | Rate limit, turn limit, detoxify, python code |
| Kokoro TTS | `myia-open-webui-kokoro-tts-1` | 8880 | 67 voices, French=`ff_siwis`, GPU-accelerated |
| Whisper STT | `myia-open-webui-whisper-stt-adapter-1` | 8787 | OpenAI-compatible proxy to Gradio |

### LAN services (HTTPS via IIS reverse proxy, accessible by all tenants)

All services run on physical LAN machines, exposed via IIS reverse proxies on `*.myia.io` subdomains.

| Service | URL | Machine | Notes |
|---------|-----|---------|-------|
| Qdrant | `https://qdrant.myia.io:443` | myia-ai-01 | MUST use `:443` (client adds `:6333` by default) |
| Embedding | `https://embeddings.myia.io/v1` | **myia-po-2026** (RTX 3080 16GB) | Model: `qwen3-4b-awq-embedding` (dim=2560) |
| SearXNG | `https://search.myia.io` | myia-ai-01 | Web search engine |
| SD Forge | `https://turbo.sd-forge.myia.io` | **myia-po-2023** (RTX 3090+3080) | Image generation |
| Whisper STT | `https://whisper-webui.myia.io` | **myia-po-2023** | Gradio WebUI, proxied by STT adapter |
| vLLM mini | `http://host.docker.internal:5001` | myia-ai-01 GPU 2 | `qwen3-vl-8b-thinking` |
| vLLM medium | `http://host.docker.internal:5002` | myia-ai-01 GPU 0+1 | `glm-4.7-flash` |
| sk-agent MCP | `http://host.docker.internal:8100/mcp` | myia-ai-01 | MCP Tool Server (Streamable HTTP), future: `skagents.myia.io` |

### Machine fleet

| Machine | GPU(s) | VRAM | Role |
|---------|--------|------|------|
| **myia-ai-01** | 3× RTX 4090 | 72 GB | OWUI tenants, vLLM, Qdrant, PostgreSQL, Redis, Tika, Pipelines, Kokoro TTS |
| **myia-po-2023** | RTX 3090 + RTX 3080 | 40 GB | Whisper STT, SD Forge |
| **myia-po-2026** | RTX 3080 | 16 GB | Embedding service |
| **myia-po-2025** | RTX 3080 | 16 GB | Coming soon — available for new workloads |

### Tenant container management

Each tenant has its own `docker-compose-<tenant>.yaml` and `<tenant>.env` file at the repo root. Each compose contains only a single `open-webui` service on the `open-webui-shared` external Docker network.

```bash
# Start
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d

# Stop
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml down

# Update (pull upstream image, restart)
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml pull
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d

# Force recreate (required after .env changes — `up -d` alone won't detect env changes)
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d --force-recreate
```

### Tenant status (all v0.8.3, all PostgreSQL, 2026-02-20)

| Tenant | Port | Users | Models | KBs | Database | Notes |
|--------|------|-------|--------|-----|----------|-------|
| myia | 2090 | 19 | 103 | 12 | myia_db | Reference instance + sidecars |
| epita | 3014 | 30 | 100 | 12 | epita_db | |
| esg | 3011 | 30 | 94 | 13 | esg_db | 37 spam purged pre-flight |
| ece | 3012 | 30 | 99 | 12 | ece_db | Upgraded v0.7.2→v0.8.3 |
| epf-genai | 3013 | 30 | 100 | 12 | epf_genai_db | 9 excess admins downgraded |
| epf | 3010 | 30 | 97 | 12 | epf_db | Upgraded v0.6.34→v0.8.3 |
| pauwels | 3016 | 17 | 94 | 13 | pauwels_db | "Formation Pro" instance |

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

| Variable | Purpose | Default | Our setting |
|---|---|---|---|
| `DATABASE_URL` | SQLAlchemy connection string | `sqlite:///...webui.db` | `postgresql://...@postgres:5432/{tenant}_db` |
| `VECTOR_DB` | Vector DB backend | `chroma` | `qdrant` |
| `QDRANT_URI` | Qdrant server URL | — | `https://qdrant.myia.io:443` |
| `WEBSOCKET_REDIS_URL` | Redis for WebSocket pub/sub | — | `redis://redis:6379/{db_number}` |
| `WEBSOCKET_REDIS_LOCK_TIMEOUT` | Redis lock TTL (seconds) | `60` | `300` (must be > SESSION_POOL_TIMEOUT=120s) |
| `WEBUI_SECRET_KEY` | JWT/session secret | auto-generated | (auto) |
| `ENABLE_OLLAMA_API` | Ollama feature toggle | `true` | `false` |
| `AIOHTTP_CLIENT_TIMEOUT` | HTTP client timeout | `300` | `6000` |
| `STORAGE_TYPE` | File storage (`local`, `s3`, etc.) | `local` | `local` |

## Git & Remotes

- `origin` → `jsboige/open-webui` (fork, pour pousser)
- `upstream` → `open-webui/open-webui` (officiel, pour tirer les mises à jour)
- Upstream is tracked on `main`; local work on `dev`
- Sync upstream: `git fetch upstream && git rebase upstream/dev && git push origin dev`

## Deployment Scripts

| Script | Purpose |
|--------|---------|
| `scripts/preflight-cleanup.py` | Delete broken functions, clean model filterIds, purge spam, delete old KBs |
| `scripts/configure-tenant.py` | Clone all config sections from myia to tenants via API |
| `scripts/shallow-copy-kbs.py` | Copy KB metadata between PostgreSQL databases (same UUIDs = shared Qdrant vectors) |
| `scripts/install-community-functions.py` | Install/update community functions and tools (8 total) |
| `scripts/migrate-sqlite-to-postgres.py` | SQLite→PG migration (runs inside container, SAVEPOINT-based error handling) |
| `scripts/bulk-kb-upload.py` | Host-side PDF uploader with skip-existing, delay, size filtering |
| `scripts/create-thematic-kbs.py` | Create thematic KBs from Bibliographie IA subdirectories |

## Knowledge Bases (12 shared across all tenants)

All tenants share the same 12 KBs via shallow copies (same Qdrant collection UUIDs). Files stored in myia's volume, accessed via WSL symlinks in each tenant's uploads directory.

- **Bibliographie IA** (148 files, 362K vectors) — main academic literature collection
- **Argumentation et Esprit Critique** (69 files) — argumentation and critical thinking
- **9 thematic KBs**: IA - ML, IA - Game Theory, IA - Search, IA - Symbolic AI, IA - Programmation par contraintes, IA - Trading et finance, IA - Méthodes probabilistes, IA - Big Data, IA - Automates
- **Guide MyIA** (test KB)

## Community Functions (8 installed on all tenants)

- **Filters** (global): Markdown Normalizer, Async Context Compression
- **Actions** (global): Flash Card, Smart Mind Map, Export to Word Enhanced
- **Tools**: Sub Agent, YouTube Transcript Provider, Visuals Toolkit

## Notes

- The `.env` files at root (myia.env, epf.env, etc.) contain secrets — never commit them. The `.gitignore` blocks `*.env` and allows `*.env.example`
- Use `tenant.env.example` as template for new tenants
- The Dockerfile is a multi-stage build: Node.js (frontend) → Python 3.11 slim (backend), exposed on port 8080 internally
- Build args `USE_CUDA`, `USE_OLLAMA`, `USE_SLIM` control Dockerfile variants
- Docker Compose `--env-file` only interpolates into the compose file — variables must also be in the `environment:` section to reach the container
- Tika image has wget, NOT curl — healthcheck must use `wget --spider -q`
- Volume naming: volumes are prefixed with project name. Use `external: true` + `name:` to reference existing volumes when changing project names

## Maintenance Roadmap (instance myia)

Work in progress — each phase validates on myia first, then deploys to student tenants.

### Phase 1: API Connections & Model Cleanup (myia)
- [x] Audit all 12 OpenAI-compatible connections (OpenAI, OpenRouter, Groq, DeepSeek, MistralAI, GoogleDirect, Local/vLLM, Pipelines)
- [x] Curated OpenRouter filter: 42 models across 10 providers (Anthropic, OpenAI, Google, Mistral, DeepSeek, Z.ai, xAI, Meta, Qwen, NVIDIA) with BYOK keys
- [x] GoogleDirect disabled — Google models served via OpenRouter BYOK (avoids 429 quota issue)
- [x] OpenAI filter: 17 chat/reasoning models (removed audio, realtime, image, moderation, sora, transcribe)
- [x] MistralAI filter: 16 chat/code/reasoning models (removed embed, moderation, voxtral/audio, OCR)
- [x] Groq filter: 10 chat models (removed whisper, guard, safeguard, orpheus/TTS)
- [x] Deploy Pipelines container (`ghcr.io/open-webui/pipelines:main`) on internal Docker network
- [x] Verify vLLM servers: mini=Qwen3-VL-8B-Thinking (5001), medium=GLM-4.7-Flash (5002) — both healthy
- [x] Install pipelines: rate_limit_filter, conversation_turn_limit_filter, detoxify_filter, python_code_pipeline

### Phase 2: Services & Settings (myia)
- [x] Fix default locale → `fr-FR` (set in database, takes effect on restart)
- [x] Audit image generation: SD WebUI Forge (`turbo.sd-forge.myia.io`) — Flux model, working
- [x] Audit TTS/STT: OpenAI `tts-1`/`whisper-1` — functional
- [x] Audit embeddings: switched to local `qwen3-4b-awq-embedding` @ `embeddings.myia.io/v1` (dim=2560, batch=16)
- [x] Switch vector DB: ChromaDB → Qdrant @ `qdrant.myia.io:443` (fix: must include `:443` for HTTPS reverse proxy — qdrant-client adds `:6333` otherwise)
- [x] Audit web search: SearXNG @ `search.myia.io` — functional
- [x] Activate functions: MoEA + Mixture of Agents active+global
- [x] Deploy Kokoro-FastAPI TTS (`ghcr.io/remsky/kokoro-fastapi-gpu:latest`) on port 8880, 67 voices, French=`ff_siwis`
- [x] Configure TTS to use Kokoro: Engine=OpenAI, Base URL=`http://kokoro-tts:8880/v1`, Model=kokoro, Voice=ff_siwis — tested end-to-end
- [x] Deploy Whisper WebUI STT adapter sidecar (`whisper-webui-adapter/`) — OpenAI-compatible proxy to Gradio API of `whisper-webui.myia.io`
- [x] Configure STT to use adapter: Engine=OpenAI, Base URL=`http://whisper-stt-adapter:8787/v1` — tested end-to-end ("Bonjour, ceci est un test.")
- [x] Verify embedding service is running (confirmed functional)
- [x] Fix Qdrant URI: must be `https://qdrant.myia.io:443` (qdrant-client defaults to port 6333 when not specified)
- [x] Create test knowledge base "Guide MyIA" — RAG pipeline validated (upload → Tika extraction → embedding → Qdrant → retrieval)
- [x] Cleaned up unused tool: removed `home_assistant_tool`
- [x] Install pipelines: rate_limit_filter (10 req/min), conversation_turn_limit_filter (10 turns/user), detoxify_filter, python_code_pipeline
- [x] Deleted broken `autotoolv2` and `artifacts_v2` functions (crashed `/api/models` in v0.8.2 due to deprecated `open_webui.apps` import)

### Phase 2.5: Docker Image Upgrade v0.7.2 → v0.8.2 (myia)
- [x] Backup PostgreSQL database (`backups/myia_db_backup_20260216.sql`, 120 MB)
- [x] Pull and deploy `ghcr.io/open-webui/open-webui:cuda` v0.8.2 (Feb 16 2026)
- [x] 5 Alembic migrations ran: prompt_history, chat_message, access_grant, skill tables + scim column
- [x] Fix broken functions crashing `/api/models` — deleted `autotoolv2` + `artifacts_v2`
- [x] Clean model metadata: removed dead `filterIds` references from 4 custom models
- [x] Add all sidecar services to `open-webui-shared` Docker network (tika, pipelines, kokoro-tts, whisper-stt-adapter, redis)
- [x] Verified: all config preserved (audio, embedding, connections, channels, KBs, users)
- [x] New features available: Groups, Analytics, Skills, Database admin, Code Execution

### Phase 2b: Channels & Collaboration (myia)
- [x] Channels feature enabled (`features.channels: true` in user permissions)
- [x] Created channels: `general` (public), `ai-playground` (public)
- [x] Tested @mention model responses: `<@M:Local.glm-4.7-flash|GLM-4.7-Flash>` — model responds in thread
- [x] Create user groups: "Equipe MyIA" (full access, 1 admin) + "Utilisateurs" (standard access, 18 users)
- [x] Evaluated bot framework ([open-webui/bot](https://github.com/open-webui/bot)) — **NOT deploying**: broken v0.7.2 compatibility (event name mismatch), native @mention already works
- [x] Set up webhooks for external integrations — created on `general` and `ai-playground` channels, tested end-to-end

### Phase 2c: Knowledge Base Expansion (myia)
- [x] Created "Bibliographie IA" knowledge base for academic literature
- [x] Built bulk upload script (`scripts/bulk-kb-upload.py`) — host-side HTTP API client, skip-existing, size filtering
- [x] Calibrated upload pipeline: 3 test PDFs → 509 vectors, then full batch with 10s delay
- [x] Uploaded 140 PDFs (777 MB) from `G:/Mon Drive/MyIA/IA/Bibliographie IA/` (recursive)
- [x] **109,482 vectors** in Qdrant `open-webui_knowledge` collection
- [x] RAG retrieval verified: 5 domain queries, relevance scores 0.86–0.93
- [x] Domains covered: ML, Constraint Programming, Game Theory, Probabilistic Methods, Search, Symbolic AI, Trading/Finance
- [x] Uploaded 4 large PDFs (54-86 MB): AIMA 4th Ed, Probabilistic ML, Algorithmic Trading, Principles of Finance
- [x] Fixed HTTP 413 failures — the 28-44 MB files were already uploaded; added to thematic KBs
- [x] **362K vectors** in Qdrant `open-webui_knowledge` collection (up from 109K)
- [x] Created 9 thematic KBs from Bibliographie IA subdirectories (script: `scripts/create-thematic-kbs.py`)
- [x] Created "Argumentation et Esprit Critique" KB — 73 PDFs from `Argumentum/Fallacies/Documentation/` (script: `scripts/bulk-kb-upload.py --recursive`)

### Phase 2d: Community Functions (myia)
- [x] Installed **Markdown Normalizer** (filter, global) — fixes LaTeX, code blocks, Mermaid, headings, tables
- [x] Installed **Async Context Compression** (filter, global) — -65% tokens on long conversations
- [x] Installed **Flash Card** (action, global) — auto-generates study flashcards
- [x] Installed **Smart Mind Map** (action, global) — interactive mind maps (Markmap.js)
- [x] Installation script: `scripts/install-community-functions.py` (create/update/toggle)
- [x] Source files saved: `scripts/community-functions/` (4 .py files from Fu-Jie/openwebui-extensions)
- [x] Tested all 4 functions end-to-end on myia (2026-02-18) — all working
- [x] Fixed MoEA filter bug: was globally active with empty valves, replacing all messages with error — toggled off
- [x] Evaluated Priority 2 functions — installed 4, skipped LLM Council (doesn't exist on openwebui.com)
- [x] Installed **Export to Word Enhanced** (action, global) — .docx export with native LaTeX equations, Mermaid diagrams (Fu-Jie)
- [x] Installed **Sub Agent** (tool) — delegates tool-heavy tasks to isolated sub-agents, parallel execution (Skyzi000)
- [x] Installed **YouTube Transcript Provider** (tool) — fetches YouTube transcripts, default lang changed to `fr,en` (Newnol)
- [x] Installed **Visuals Toolkit** (tool) — Plotly charts, tables, heatmaps, timelines, flowcharts with ASCII fallback (Cole)
- [x] Cleaned up duplicate "IA - IA symbolique" KB (empty, deleted via API)
- [x] Updated install script to support tools (`/api/v1/tools/` endpoint)
- [x] Evaluated v0.8.3 — patch release, PostgreSQL fixes, no breaking changes
- [x] Upgraded v0.8.2 → v0.8.3 (2026-02-19): backup DB, pull image, restart, verify health — all OK

### Phase 3: Deploy to Student Tenants (COMPLETED - 2026-02-19)
- [x] Created `scripts/preflight-cleanup.py` — delete broken functions, clean model filterIds, purge spam, delete old KBs
- [x] Created `scripts/configure-tenant.py` — clone all config sections (OpenAI connections, embedding, audio, image, RAG) from myia to tenants via API
- [x] Created `scripts/shallow-copy-kbs.py` — copy KB metadata between PostgreSQL databases (same UUIDs = shared Qdrant vectors)
- [x] Updated all 6 tenant docker-compose files: dual-network topology (open-webui-shared + internal), PostgreSQL, Qdrant, standardized ports
- [x] Updated all 6 tenant .env files: removed legacy config, added DATABASE_URL, QDRANT_URI, QDRANT_API_KEY, websocket config
- [x] Fixed migration script: SAVEPOINT-based error handling (was rolling back entire transaction on single row errors), added prompt boolean column mapping
- [x] Pre-flight cleanup on all 5 running tenants: broken functions deleted, spam purged, old KBs removed
- [x] Deployed **epita** (v0.8.3→v0.8.3): SQLite→PG migration (1636 rows), config clone, 12 KBs, 8 functions/tools
- [x] Deployed **esg** (v0.8.3→v0.8.3): SQLite→PG migration (759 rows), config clone, 12 KBs, 8 functions/tools
- [x] Deployed **ece** (v0.7.2→v0.8.3): SQLite→PG migration (783 rows, 7 prompts skipped), config clone, 12 KBs, 8 functions/tools
- [x] Deployed **epf-genai** (v0.7.2→v0.8.3): SQLite→PG migration (641 rows), config clone, 12 KBs, 8 functions/tools, 9 excess admins downgraded
- [x] Deployed **epf** (v0.6.34→v0.8.3): SQLite→PG migration (1033 rows, some v0.6 tables absent), config clone, 12 KBs, 8 functions/tools
- [x] Deployed **pauwels** (Formation Pro): SQLite→PG migration (63 rows), config clone, 12 KBs, 8 functions/tools, renamed to "Formation Pro"
- [x] Final verification: all 7 tenants on v0.8.3, 94-103 models, 12-13 KBs, 5 functions + 5 tools each
- [x] WSL symlinks for KB file access — 261 individual file symlinks per tenant (not directory symlinks)
- [x] Remove orphan standalone `tika` container

### Phase 3.5: Infrastructure Mutualization (COMPLETED - 2026-02-20)
- [x] Created `docker-compose-infra.yaml` — combined PostgreSQL + Tika + Redis as project `open-webui-infra`
- [x] Removed Tika containers from all 6 tenant compose files (was duplicated per tenant)
- [x] Removed Redis containers from all 6 tenant compose files → single shared Redis with DB number isolation
- [x] Simplified all tenant compose files to single `open-webui` service on `open-webui-shared` network
- [x] Fixed myia compose: added missing WebSocket env vars (`ENABLE_WEBSOCKET_SUPPORT`, `WEBSOCKET_MANAGER`, `WEBSOCKET_REDIS_URL`)
- [x] Fixed v0.8.3 Redis lock timeout bug: `WEBSOCKET_REDIS_LOCK_TIMEOUT=300` (was 60s, shorter than SESSION_POOL_TIMEOUT=120s)
- [x] Removed obsolete per-tenant standalone compose files (`docker-compose-postgres.yaml`, `docker-compose-tika.yaml`, `docker-compose-redis.yaml`)

### Phase 4: Remaining Tasks
- [x] Upload 4 large PDFs (>50 MB) — AIMA 4th Ed (79MB), Probabilistic ML (86MB), Algorithmic Trading (54MB), Principles of Finance (61MB)
- [x] Add medium files (28-44MB) to thematic KBs — Model Based ML, Latent Diffusion, Geometric DL, CP-SAT Primer
- [x] Create WSL symlinks for new uploads on all 6 tenants (4 files × 6 tenants = 24 symlinks)
- [x] Fix IIS reverse proxy: `tika.myia.io` → port 9917 (web.config updated + Tika container restarted, verified HTTP 200)
- [x] Set up webhooks for channel external integrations — `general` + `ai-playground` on myia
- [x] sk-agent integration study — see Phase 5 below
- [x] Document distributed infrastructure (machine fleet, GPU allocation) — see Phase 5 below

### Phase 5: Integration & Future Work

#### sk-agent Integration (studied 2026-02-20)

**sk-agent v2.0** (`roo-extensions/mcps/internal/servers/sk-agent/`) is a Semantic Kernel-based MCP server providing:
- **Agent orchestration**: 11 composable agents (analyst, vision-analyst, researcher, etc.) with shared model pool
- **Multi-agent conversations**: Deep Search, Deep Think, Code Review, Research Debate presets
- **Persistent vector memory**: per-agent Qdrant collections + embeddings
- **Autonomous tool use**: SearXNG search, Playwright browser, recursive self-invocation

**Current model pool**: GLM-5 + GLM-4.6V (z.ai cloud), ZwZ-8B + GLM-4.7-Flash (local vLLM)

**Integration (implemented 2026-02-20)**:

sk-agent is registered as an **MCP Tool Server** in OWUI (myia) via Streamable HTTP transport:
- **URL**: `http://host.docker.internal:8100/mcp` (sk-agent runs on host, OWUI in Docker)
- **Transport**: sk-agent supports dual mode — `stdio` (for Claude/Roo) and `streamable-http` (for OWUI/LAN)
- **13 tools exposed**: `call_agent`, `run_conversation`, `list_agents`, `list_conversations`, `list_tools`, `end_conversation`, plus deprecated aliases
- **10 agents available**: analyst, vision-analyst, fast, researcher, synthesizer, critic, optimist, devils-advocate, pragmatist, mediator
- **4 conversation presets**: deep-search, deep-think, code-review, research-debate
- **Models**: GLM-4.7-Flash (local vLLM), Qwen3-VL-8B (local vLLM with vision). Z.ai cloud models (GLM-5, GLM-4.6V) disabled pending API key.
- **Tested end-to-end**: `list_agents` and `call_agent` work from OWUI chat → MCP → sk-agent → vLLM → response

**Running sk-agent in HTTP mode**:
```bash
cd d:\roo-extensions\mcps\internal\servers\sk-agent
python sk_agent.py streamable-http  # Listens on 0.0.0.0:8100
# Override port: SK_AGENT_PORT=9100 python sk_agent.py streamable-http
```

**Future work**:
- `skagents.myia.io` IIS reverse proxy for LAN-wide access
- Dockerize sk-agent as sidecar in `docker-compose-myia.yaml`
- Direction 2: sk-agent consumes OWUI Pipelines/models as providers

#### Infrastructure Notes (documented 2026-02-20)

All services are **already running locally** on LAN machines — the `*.myia.io` HTTPS URLs are IIS reverse proxies, NOT cloud services. See "Machine fleet" and "LAN services" tables above for the full mapping.

**myia-ai-01 GPU allocation** (3× RTX 4090, 24 GB each):
| GPU | VRAM Used | Assignment |
|-----|-----------|------------|
| GPU 0+1 | ~97% each | vLLM medium (GLM-4.7-Flash, tensor-parallel) |
| GPU 2 | ~84% | vLLM mini (ZwZ-8B) + Kokoro TTS (~3.9 GB free) |

**Available capacity**: myia-po-2025 (RTX 3080 16GB) arriving next week — can host additional models or services.
