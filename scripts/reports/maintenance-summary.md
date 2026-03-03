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

## Remaining Items (for next session)

1. **Persona base model migrations**: Benchmark supports switching expensive OpenAI models (gpt-5 at $30/M, o1 at $60/M, o3 at $40/M) to cheaper alternatives. Recommendations ready in `optimization-recommendations.md`. Needs user validation before applying.

2. **Dr. Claire Lacroix system prompt bug**: Uses Dr. Étienne Charpentier's prompt (copy-paste error). Needs manual correction.

3. **New community functions**: AI Infographic Generator, Translation Assistant, LLM Council tool recommended for installation. Requires downloading source from openwebui.com (user login needed).

4. **multi-agent model**: Inactive, uses deprecated local model. Consider deleting or migrating.
