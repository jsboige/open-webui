# OWUI Maintenance Summary Report

**Date:** 2026-03-03
**Scope:** All 7 tenants (myia, epf, epf-genai, ece, esg, epita, pauwels)

---

## Phase 1: OWUI Update

- **Status:** Completed
- Upstream already up-to-date (no new commits)
- Pulled latest Docker image `ghcr.io/open-webui/open-webui:main`
- Restarted all 7 tenant containers with `--force-recreate`
- All tenants verified healthy

## Phase 2: Chat Cleanup

- **Status:** Completed
- **Script:** `scripts/cleanup-chats.py`
- **Total deleted:** 187 test conversations across 7 tenants
- **Preserved:** 81 conversations in folders (myia)

| Tenant | Deleted | Kept |
|--------|---------|------|
| myia | 82 | 81 |
| epf | 33 | 0 |
| epf-genai | 18 | 0 |
| ece | 19 | 0 |
| esg | 10 | 0 |
| epita | 22 | 0 |
| pauwels | 3 | 0 |

## Phase 3: Model Audit & Optimization

### 3.1 Model Audit
- **Script:** `scripts/audit-models.py`
- **Report:** `scripts/reports/model-audit.md`
- 19 custom models, 245 base models, 12 with avatars, 7 without

### 3.2 Avatar Generation
- **Script:** `scripts/generate-avatars.py`
- Generated 7 avatars via SD Forge SDXL Lightning (4 steps, 1024x1024, resized to 256x256)
- Deployed to all 7 tenants (49 API updates)
- Models: expert-analyste, redacteur-technique, vision-expert, Local.qwen3.5-35b-a3b-fast, tp-linux-debutant, tp-python-data, tp-git-workflow

### 3.3 Benchmark
- **Script:** `scripts/benchmark-models.py`
- **Report:** `scripts/reports/benchmark-report.md`
- 12 models × 5 prompts = 60 API calls
- Providers tested: OpenAI, MistralAI, DeepSeek, OpenRouter, Local

**Key findings:**

| Use Case | Current | Recommended | Latency | Cost Savings |
|----------|---------|-------------|---------|-------------|
| TP Tutors | OpenAI.gpt-4.1-mini (5.3s, $1.6/M) | MistralAI.devstral-small (2.4s, $0.3/M) | **2x faster** | **81%** |
| Creative personas | OpenAI.gpt-5 (~$30/M) | MistralAI.mistral-medium ($1.2/M) | ~2x slower | **96%** |
| Code personas | OpenAI.gpt-5 (~$30/M) | MistralAI.devstral-small ($0.3/M) | 2x faster | **99%** |
| Reasoning | OpenAI.o1/o3 (~$50/M) | Claude Sonnet 4 ($15/M) | similar | **70%** |

### 3.4 Optimization Applied
- **Script:** `scripts/optimize-models.py`
- **Report:** `scripts/reports/optimization-recommendations.md`
- 36 changes across 7 tenants:
  - **3 TP tutors**: base_model_id migrated from `OpenAI.gpt-4.1-mini` → `MistralAI.devstral-small-latest`
  - **3 utility models**: system prompts added (expert-analyste, redacteur-technique, vision-expert)
  - Descriptions already set during avatar deployment

**Persona migrations (recommended but not yet applied):** See `optimization-recommendations.md` for detailed recommendations per persona.

## Phase 4: Workspace Refinement

### 4.1 Workspace Audit
- **Script:** `scripts/audit-workspace.py`
- **Report:** `scripts/reports/workspace-audit.md`
- 7 prompts, 6 tools, 7 functions (before changes)

### 4.2 Community Portal Exploration
- **Report:** `scripts/reports/community-exploration.md`
- Browsed openwebui.com Functions, Tools, Prompts sections via Playwright MCP
- Compiled shortlist of recommended additions for educational deployment

### 4.3 Cleanup
- Deleted `MoEA` and `Mixture of Agents` functions from all 7 tenants

### 4.4 Community Functions Updated
- **Script:** `scripts/install-community-functions.py` (updated with multi-tenant support)
- Refreshed all 8 community functions across 7 tenants (56 updates)
- Fixed OWUI v0.8.8 API change: update endpoint now requires `id` in body

### 4.5 Educational Prompts
- **Script:** `scripts/deploy-prompts.py`
- Created and deployed 4 new educational prompts to all 7 tenants:
  - `/plan-projet` — Planificateur de Projet (structured project planning)
  - `/resume-session` — Résumé de Session (conversation handoff notes)
  - `/prompt-engineering` — Atelier Prompt Engineering (teach prompt writing)
  - `/analyse-critique` — Analyse Critique (critical thinking & argumentation)

---

## Scripts Created/Updated

| Script | Status | Purpose |
|--------|--------|---------|
| `scripts/audit-models.py` | NEW | Audit all custom models (avatars, params, descriptions) |
| `scripts/audit-workspace.py` | NEW | Audit prompts, tools, functions |
| `scripts/cleanup-chats.py` | NEW | Selective chat deletion with dry-run |
| `scripts/generate-avatars.py` | NEW | SD Forge avatar generation + multi-tenant deploy |
| `scripts/benchmark-models.py` | NEW | Model benchmark (latency, quality, cost) |
| `scripts/optimize-models.py` | NEW | Apply model parameter optimizations |
| `scripts/deploy-prompts.py` | NEW | Deploy educational prompts to all tenants |
| `scripts/install-community-functions.py` | UPDATED | Added multi-tenant support, fixed v0.8.8 API |

## Reports Generated

| Report | Content |
|--------|---------|
| `scripts/reports/model-audit.md` | Full model inventory with avatar/param status |
| `scripts/reports/benchmark-report.md` | 12-model benchmark with detailed results |
| `scripts/reports/optimization-recommendations.md` | Cost savings recommendations per model |
| `scripts/reports/workspace-audit.md` | Prompts/tools/functions inventory |
| `scripts/reports/community-exploration.md` | Community portal exploration & recommendations |
| `scripts/reports/maintenance-summary.md` | This report |

---

## Phase 5: Final Fixes (session 2)

### 5.1 Dr. Claire Lacroix System Prompt Fix
- **Bug**: System prompt was a copy-paste of Dr. Étienne Charpentier's prompt
- **Fix**: Wrote distinctive Lacanian psychoanalyst prompt (3112 chars) emphasizing RSI, signifiant, objet petit a
- Applied to myia (only tenant with this model)

### 5.2 Persona Base Model Migrations
- **Script:** `scripts/optimize-models.py` (updated with PERSONA_MIGRATIONS)
- **11 personas migrated** on myia (other tenants have subset of models):

| Persona | Old Base | New Base | Savings |
|---------|----------|----------|---------|
| Albéric de Clerval | `OpenAI.gpt-5-chat-latest` | `MistralAI.mistral-medium-latest` | 96% |
| deep thought | `OpenAI.gpt-5-chat-latest` | `MistralAI.mistral-medium-latest` | 96% |
| Isola | `OpenAI.gpt-5-chat-latest` | `MistralAI.mistral-medium-latest` | 96% |
| Vanessa | `OpenAI.gpt-5-chat-latest` | `MistralAI.mistral-medium-latest` | 96% |
| Samantha | `OpenAI.gpt-5.2-chat-latest` | `MistralAI.mistral-medium-latest` | 96% |
| psychologist | `OpenAI.gpt-5-chat-latest` | `OpenRouter.anthropic/claude-haiku-4.5` | 87% |
| codewriter | `OpenAI.gpt-5` | `MistralAI.devstral-small-latest` | 99% |
| Emilio | `OpenAI.gpt-5` | `MistralAI.devstral-small-latest` | 99% |
| Dr. Claire Lacroix | `OpenAI.o1` | `OpenRouter.anthropic/claude-sonnet-4` | 75% |
| Samantha R1 | `OpenAI.o3` | `OpenRouter.anthropic/claude-sonnet-4` | 63% |
| Dr. Étienne Charpentier | `OpenAI.gpt-4.1` | `MistralAI.mistral-medium-latest` | 85% |

### 5.3 multi-agent Model Deletion
- Deleted from myia, epf-genai, ece, epita (4 tenants where it existed)
- Was inactive, using deprecated `Local.Qwen/Qwen2.5-7B-Instruct-AWQ`

### 5.4 New Community Functions
- **Smart Infographic** (action, @Fu-Jie v1.5.0): AI-powered infographic generator with AntV, 70+ templates
- **LLM Council** (tool, @mabntt v0.3.0): Multi-model deliberation with 3-stage process
- Deployed to all 7 tenants (14 creates)

### 5.5 EasyLang Translation Assistant (session 3)
- **EasyLang** (filter, @h4nn1b4l v0.2.7): Smart bidirectional translation with context-based summarization
- Downloaded from GitHub repo `annibale-x/Easylang` (previously blocked — openwebui.com required login)
- Commands: `tr` (translate), `trs` (summarize+translate), `trc` (translate+continue chat), `tl`/`bl` (config)
- Deployed as global filter to all 7 tenants (7 creates)

### 5.6 Reasoning Persona Model Update (session 3)
- **Dr. Claire Lacroix**: `OpenRouter.anthropic/claude-sonnet-4` → `OpenRouter.anthropic/claude-sonnet-4-6`
- **Samantha R1**: `OpenRouter.anthropic/claude-sonnet-4` → `OpenRouter.anthropic/claude-sonnet-4-6`
- Applied on myia (only tenant with these personas)

---

## Remaining Items

1. **Persona quality validation**: The 11 persona migrations should be tested interactively to verify response quality matches expectations (especially creative/conversational personas on Mistral Medium)
