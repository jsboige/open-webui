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
- **Fork `dev` is synced to `upstream/dev` but NOT deployed (source-only).** Last synced **2026-10-29 (+1108 commits over the 2026-10-05 sync; merge `6367eb60e` on branch `sync/upstream-dev-20261029`, ZERO conflict, 158 local commits preserved, and the 12 production compose files came through byte-identical — only `docker-compose-launcher.sh` changed, 3 lines upstream)**. Previous: 2026-10-05 (+402, merge `4b3407d74` on branch `sync/upstream-dev-20261005`, zero conflict — the first fully clean sync since 08-23). `lint:types` after the merge: 6928 errors (baseline 7082 → −154, upstream fixed type debt; non-gated). Alembic: 66 revisions at `v0.12.5`, single head **`0bd252b206fb`** (8 migrations beyond v0.11.4, **now deployed** on the 7 tenants). Upstream feature highlights in this window: MFA challenge/recovery UI, group hierarchy/inherited members, skills utils, channel queue. Previous sync 2026-09-14 (+401, one conflict `.dockerignore` resolved as union; 7082 lint errors; 58 revisions at `d4c1a8e37b62`). Earlier syncs 2026-08-14 (+212) and 2026-08-23 (+137) clean. The 7 tenants run the **official** image `v0.12.5` (`WEBUI_DOCKER_TAG`, deployed 2026-10-29), not the fork's source — a source sync touches zero production. The Alembic chain history note: an earlier "divergent 2-head" reading (2026-08-14/23) was a misreading — graph walks on v0.11.0–v0.11.3 all yield a single head and a pure line; count heads by graph walk (who has no child), never from one node's down_revision. ⚠️ A naive head-walk on the *source* of the migration files can return dozens of false heads (the `down_revision` parser is fragile) — trust the linear chain, not the walk. `npm run lint:types` is **non-gated** on this fork (~7k pre-existing errors from stale generated `src/lib/apis/` types); validate merges against that baseline, not zero.
- **`v0.12.5` DEPLOYED 7/7 on 2026-10-29** (jsboige GO in-session : « Tu pourras faire une sync upstream et une MAJ des tenants ? »). Cible = **`v0.12.5`** (tag 2026-10-29 09:08Z, +99 commits sur v0.12.4, **0 migration nouvelle**, advisory sécurité explicite « update as soon as possible » ⇒ v0.12.4 est superseded). **8 migrations** depuis v0.11.4, chaîne linéaire, tête = **`0bd252b206fb`** (`d4c1a8e37b62 → a7d3e9f2b641 → b8e4f0a3c752 → d6a8c3f912ab → e7b9d4a023bc → f8c0e5b134cd → b8f2c6d91a04 → c92da83b017f → 0bd252b206fb`) ⇒ **rollback = restore PG** (l'image seule ne revient pas en arrière). Backup frais 7/7 d'abord (`backups/owui-daily/2026-10-29/`, 571 Mo, poison-guards OK, rétention 365 j ⇒ 0 suppression). Rollout staged esg (pilote) → ece → pauwels → epf → epf-genai → epita → myia, avec **`up -d --force-recreate --no-deps open-webui`** : la compose déclare 3 services (`open-webui`, `open-terminal`, `channel-bot`) et le bot est en `build:` ⇒ recréer tout le projet **rebuilderait l'image du bot** ; en ne recréant que `open-webui`, le bot **se reconnecte seul** (Socket.IO, « Joined as » ~37 s après, ×7 vérifié). Validations : `/health` 200 + version `0.12.5` ×7, **Alembic `0bd252b206fb` ×7**, restarts=0, 0 erreur de log, tuteurs 200 en 0,8-1,2 s, bots ×7. ⚠️ **RAG et STT étaient rouges pendant le rollout = panne po-2023** (embeddings 502 + whisper-webui 502), **pas l'upgrade** : à ne jamais confondre les deux dans un rapport. Pré-vol utile : diff des sources v0.11.4 vs v0.12.5 ⇒ **aucune variable de prod renommée/supprimée** (les `.env` restent valides). Deltas à surveiller : Skills (instructions chargées à chaque message si le builtin est ON — nous ne l'utilisons pas), tool servers auto-récupérés après outage (volet sk-agent), `Forward cookies` OFF par défaut (sans effet, bearer), chats E2E chiffrés OFF par défaut, onglets Sessions dans Admin Analytics, pages multiples dans les Notes, embeddings par lots de 1000 chunks, `RAG_EMBEDDING_{QUERY,CONTENT}_PREFIX` désormais réglables en admin. Détail : `docs/…` fiche mémoire `upgrade-v0125-2026-10-29.md`.
- **Une suite E2E E2E-déterministe existe hors de ce dépôt** : sujet F1 « QA E2E Open WebUI » du cours EPF, dossier `groupe-owui-qa/` dans `jsboigeEPF/2026-MSMIN5IN52-GenAI` (PR #28 + #31). 2 instances OWUI en Docker + **mock LLM** OpenAI-compatible maison (`mock-llm/server.mjs`) ⇒ **zéro GPU, zéro API payante, réponses déterministes**, donc exécutable pendant une panne d'embedder et utilisable comme **sonde de dérive UI indépendante** d'un upgrade. 17/17 en v0.11.4 ; sur **v0.12.5 : 15/17** (RAG depuis le composer + exécution d'un outil) ⇒ écart de comportement réel à instruire (A/B dans le même environnement : v0.11.4 = 17/17, donc pas un artefact de montage). Portage vers l'espace pédagogique `D:/CoursIA/.../Playwright-OWUI` (aujourd'hui vide) **proposé** sur le dashboard `CoursIA` — l'espace exige un claim (`check_lane_claim.py`) et plusieurs lanes y travaillent : ne pas l'éditer sans.
- **`v0.11.4` DEPLOYED 7/7 on 2026-10-06** (jsboige GO in-session, after the lane's full-notes assessment; supersedes v0.11.3 of 2026-09-01). v0.11.4 (tagged 2026-09-21) carries an explicit **Security Advisory** ("we recommend updating production deployments at your earliest convenience", some fixes withheld) with fleet-relevant access fixes: knowledge file access + KB directory traversal, terminal sessions re-checked every 10 s after access changes, connector model listing no longer open to any signed-in user (#29619), IdP tokens no longer written to logs (#29709), Mermaid/SVG cross-origin refusal. **Zero Alembic migrations v0.11.3→v0.11.4** — the cleanest upgrade in fleet history: flip `WEBUI_DOCKER_TAG` + `up -d --force-recreate`, DB stays at `d4c1a8e37b62` ×7 (verified in PG per tenant). Rollout: manual fresh backup 7/7 first (`backups/owui-daily/2026-10-05/` = rollback point), then staged esg (pilot, fully validated incl. RAG/tutor/bot) → ece → pauwels → epf → epf-genai → epita → myia. All validations green: `/health` 200 + version 0.11.4 ×7, RAG canaries, tutors 200, bots boot-race recovered ×7, audio baseline exact (STT 200 ×7 / TTS 401 ×7 standing), **sk-agent MCP tool server config survived** (`server:mcp:sk-agent` visible). Image 6.5 GB vs 7.16 GB (−660 MB, the release-notes size cut). Behavior deltas to watch at the tirs: v0.11 chat-stall (~1/6) possibly fixed by the streaming fixes; tool-server `Forward cookies` now OFF by default (we use bearer — unaffected); #29757 fallback for chats whose model was removed; new terminal features (skills from terminal, AGENTS.md auto-read, per-command tabs, folder uploads) relevant to TP program. `WEBUI_SECRET_KEY` rotation still jsboige's call.
- **`v0.11.3` DEPLOYED 7/7 on 2026-09-01** (jsboige GO; supersedes v0.11.0 of 2026-08-07). v0.11.3 (tagged 2026-08-31 ~14:55 UTC) is a strict superset of v0.11.2 (`git merge-base --is-ancestor` exit 0) — v0.11.2 was the **security patch** ("some fixes withheld"; recommended promptly) and also fixes the reasoning-model streaming stall (#29053) + thinking leaking into replies after tool calls (#29052, relevant to the Qwen tutor workaround); v0.11.3 additionally fixes upgrade-failure bug #29280 (a failed DB migration aborts cleanly instead of half-booting on a missing `chat.timer_at`). **Rollout executed**: fresh backup 7/7 first (`backups/owui-daily/2026-09-01/`, 466 MB, poison-guards OK — this is the rollback point, PG restore), then staged `up -d --force-recreate` esg (pilot, fully validated) → ece → pauwels → epf → epf-genai → epita → myia. All 7: `/health` 200, version 0.11.3, Alembic head `d4c1a8e37b62` (3 migrations `1ce6ade7d93b → 6d09d1bf1f23 → d4c1a8e37b62` applied cleanly per tenant, zero errors), 6/6 channel-bots auto-recovered from the boot-race 502 within ~15 s (no bcrypt issue), audio preflight unchanged (STT 200 ×7 / TTS 401 ×7 standing), Mistral-disabled + tutors-on-Qwen runtime state survived intact. **The recreate also repaired epita's torn log file** (`docker-log-health` verdict OK, inversion gone). Known-behavior deltas to watch: v0.11 chat-stall (~1/6 browser chats) may change post-#29053 — re-observe; `WEBUI_SECRET_KEY` rotation still jsboige's call.
