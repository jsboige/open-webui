# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **fork/clone of Open WebUI** (v0.8.2, upgraded from v0.7.2 on 2026-02-16) — an extensible, self-hosted AI chat platform. This specific instance is used to run **multiple tenant deployments** (myia, epf, ece, esg, epita, pauwels, epf-genai) via per-tenant docker-compose and env files on the same machine.

**Stack**: SvelteKit 2 + Svelte 5 (frontend) / FastAPI 0.128 + SQLAlchemy 2 (backend) / Python 3.11+

## Multi-Tenant Container Setup

Each tenant has its own `docker-compose-<tenant>.yaml` and `<tenant>.env` file at the repo root. The pattern for managing any tenant:

```bash
# Start
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d

# Stop
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml down

# Update (pull upstream image, restart)
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml pull
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d

# Rebuild from source
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d --build
```

Active tenants: `myia`, `epf`, `epf-genai`, `ece`, `esg`, `epita`, `pauwels`

The primary tenant is **myia** (port 2090, image tag `cuda`, Redis on 6351, Tika on 9917).

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
| `OLLAMA_BASE_URL` | Ollama API endpoint | `http://localhost:11434` |
| `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` | OpenAI-compatible API | — |
| `WEBUI_SECRET_KEY` | JWT/session secret | auto-generated |
| `REDIS_URL` / `WEBSOCKET_REDIS_URL` | Redis for sessions/websockets | — |
| `VECTOR_DB` | Vector DB backend (`chroma`, `qdrant`, etc.) | `chroma` |
| `STORAGE_TYPE` | File storage (`local`, `s3`, `azure`, `gcs`) | `local` |
| `ENV` | `dev` / `prod` / `test` | `prod` |
| `ENABLE_OLLAMA_API` / `ENABLE_OPENAI_API` | Feature toggles | `true` |

## Git & Remotes

- `origin` → `jsboige/open-webui` (fork, pour pousser)
- `upstream` → `open-webui/open-webui` (officiel, pour tirer les mises à jour)
- Upstream is tracked on `main`; local work on `dev`
- Sync upstream: `git fetch upstream && git rebase upstream/dev && git push origin dev`

## Notes

- The `.env` files at root (myia.env, epf.env, etc.) contain secrets — never commit them. The `.gitignore` blocks `*.env` and allows `*.env.example`
- Use `tenant.env.example` as template for new tenants
- The Dockerfile is a multi-stage build: Node.js (frontend) → Python 3.11 slim (backend), exposed on port 8080 internally
- Build args `USE_CUDA`, `USE_OLLAMA`, `USE_SLIM` control Dockerfile variants
- Playwright auth credentials for testing are in `.env` at repo root (gitignored): `MYIA_URL`, `MYIA_EMAIL`, `MYIA_PASSWORD`

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
- [ ] Set up webhooks for external integrations

### Phase 2c: Knowledge Base Expansion (myia)
- [x] Created "Bibliographie IA" knowledge base for academic literature
- [x] Built bulk upload script (`scripts/bulk-kb-upload.py`) — host-side HTTP API client, skip-existing, size filtering
- [x] Calibrated upload pipeline: 3 test PDFs → 509 vectors, then full batch with 10s delay
- [x] Uploaded 140 PDFs (777 MB) from `G:/Mon Drive/MyIA/IA/Bibliographie IA/` (recursive)
- [x] **109,482 vectors** in Qdrant `open-webui_knowledge` collection
- [x] RAG retrieval verified: 5 domain queries, relevance scores 0.86–0.93
- [x] Domains covered: ML, Constraint Programming, Game Theory, Probabilistic Methods, Search, Symbolic AI, Trading/Finance
- [ ] Upload 4 skipped large PDFs (>50 MB) — split or increase reverse proxy limit
- [ ] Fix 3 HTTP 413 failures (28–43 MB) — increase nginx `client_max_body_size`
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
- [ ] Evaluate Priority 2 functions (Sub Agent, YouTube Transcript, Export to Word, Visuals Toolkit, LLM Council)

### Phase 3: Deploy to Student Tenants
- [ ] Export validated config from myia (model filters, connections, functions, tools)
- [ ] Apply to each tenant: epf, epf-genai, ece, esg, epita, pauwels
- [ ] Rebuild knowledge bases per tenant as needed
- [ ] Verify each tenant's API keys and quotas

### Phase 4: Local Infrastructure (future)
- [ ] Evaluate moving some cloud services to local infra (vLLM, embeddings, STT)
- [ ] Compare SOTA cloud models vs local hosting cost/performance
- [ ] Deploy embedding service container (vLLM or TEI) for `qwen3-4b-awq-embedding`
- [x] ~~WARNING~~: v0.8.2 upgrade completed successfully (2026-02-16) — 5 Alembic migrations, no manual DB intervention
