# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **fork/clone of Open WebUI** (v0.6.43) — an extensible, self-hosted AI chat platform. This specific instance is used to run **multiple tenant deployments** (myia, epf, ece, esg, epita, pauwels, epf-genai) via per-tenant docker-compose and env files on the same machine.

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
- [ ] Install useful pipelines (filters, function calling, etc.)

### Phase 2: Services & Settings (myia)
- [x] Fix default locale → `fr-FR` (set in database, takes effect on restart)
- [x] Audit image generation: SD WebUI Forge (`turbo.sd-forge.myia.io`) — Flux model, working
- [x] Audit TTS/STT: OpenAI `tts-1`/`whisper-1` — functional
- [x] Audit embeddings: switched to local `qwen3-4b-awq-embedding` @ `embeddings.myia.io/v1` (dim=2560, batch=16)
- [x] Switch vector DB: ChromaDB → Qdrant @ `qdrant.myia.io` (12 existing collections)
- [x] Audit web search: SearXNG @ `search.myia.io` — functional
- [x] Activate functions: Artifacts V2, MoEA, Mixture of Agents — all active + global
- [x] Deploy Kokoro-FastAPI TTS (`ghcr.io/remsky/kokoro-fastapi-gpu:latest`) on port 8880, 67 voices, French=`ff_siwis`
- [x] Configure TTS to use Kokoro: Engine=OpenAI, Base URL=`http://kokoro-tts:8880/v1`, Model=kokoro, Voice=ff_siwis — tested end-to-end
- [x] Deploy Whisper WebUI STT adapter sidecar (`whisper-webui-adapter/`) — OpenAI-compatible proxy to Gradio API of `whisper-webui.myia.io`
- [x] Configure STT to use adapter: Engine=OpenAI, Base URL=`http://whisper-stt-adapter:8787/v1` — tested end-to-end ("Bonjour, ceci est un test.")
- [x] Verify embedding service is running (confirmed functional by Roo)
- [ ] Rebuild knowledge bases (currently 0 — need to create new ones with Qdrant + local embeddings)

### Phase 3: Deploy to Student Tenants
- [ ] Export validated config from myia (model filters, connections, functions, tools)
- [ ] Apply to each tenant: epf, epf-genai, ece, esg, epita, pauwels
- [ ] Rebuild knowledge bases per tenant as needed
- [ ] Verify each tenant's API keys and quotas

### Phase 4: Local Infrastructure (future)
- [ ] Evaluate moving some cloud services to local infra (vLLM, embeddings, STT)
- [ ] Compare SOTA cloud models vs local hosting cost/performance
- [ ] Deploy embedding service container (vLLM or TEI) for `qwen3-4b-awq-embedding`
- [ ] **WARNING**: Major upstream Open WebUI release with tricky DB migration — handle with care when syncing
