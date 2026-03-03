# Model Optimization Report

**Generated:** 2026-03-03
**Tool:** `scripts/optimize-models.py`
**Based on:** `scripts/reports/benchmark-report.md`

## Changes Applied

### 1. TP Tutor Base Model Migration

| Model | Old Base | New Base | Rationale |
|-------|----------|----------|-----------|
| `tp-linux-debutant` | `OpenAI.gpt-4.1-mini` | `MistralAI.devstral-small-latest` | 2x faster (2.4s vs 5.3s), 5x cheaper ($0.3 vs $1.6/M), code-specialized |
| `tp-python-data` | `OpenAI.gpt-4.1-mini` | `MistralAI.devstral-small-latest` | Same — devstral excels at code pedagogy |
| `tp-git-workflow` | `OpenAI.gpt-4.1-mini` | `MistralAI.devstral-small-latest` | Same — excellent French support |

**Benchmark evidence:**
- devstral-small: 2.4s avg latency, 1534 chars avg output, 0/5 errors, $0.3/M output
- gpt-4.1-mini: 5.3s avg latency, 1097 chars avg output, 0/5 errors, $1.6/M output
- devstral produces longer, more detailed responses with better code formatting

**Monthly savings estimate** (assuming ~500K output tokens/month for TP tutors):
- Before: 500K × $1.6/M = $0.80/month
- After: 500K × $0.3/M = $0.15/month
- **Savings: ~80%**

### 2. Utility Model Descriptions Added

| Model | Description |
|-------|-------------|
| `expert-analyste` | Analyste structuré français. Décompose les problèmes complexes... |
| `redacteur-technique` | Rédacteur de documentation technique en français... |
| `vision-expert` | Spécialiste analyse d'images et documents visuels... |
| `Local.qwen3.5-35b-a3b-fast` | Version rapide de Qwen3.5-35B sans réflexion interne... |

### 3. System Prompts Added

| Model | System Prompt Summary |
|-------|----------------------|
| `expert-analyste` | Analyste rigoureux, structuration, recommandations actionnables |
| `redacteur-technique` | Documentation technique, Markdown, pédagogie |
| `vision-expert` | OCR, graphiques, description d'images, comparaison visuelle |

---

## Persona Migration Recommendations (NOT YET APPLIED)

### Priority 1: Most Expensive Models (gpt-5, o1, o3)

| Persona | Current Base | Cost/M output | Recommended | Cost/M output | Savings |
|---------|-------------|---------------|-------------|---------------|---------|
| Albéric de Clerval | `OpenAI.gpt-5-chat-latest` | ~$30 | `MistralAI.mistral-medium-latest` | $1.2 | **96%** |
| deep thought | `OpenAI.gpt-5-chat-latest` | ~$30 | `MistralAI.mistral-medium-latest` | $1.2 | **96%** |
| Isola | `OpenAI.gpt-5-chat-latest` | ~$30 | `MistralAI.mistral-medium-latest` | $1.2 | **96%** |
| Vanessa | `OpenAI.gpt-5-chat-latest` | ~$30 | `MistralAI.mistral-medium-latest` | $1.2 | **96%** |
| psychologist | `OpenAI.gpt-5-chat-latest` | ~$30 | `OpenRouter.anthropic/claude-haiku-4.5` | $4.0 | **87%** |
| codewriter | `OpenAI.gpt-5` | ~$30 | `MistralAI.devstral-small-latest` | $0.3 | **99%** |
| Emilio | `OpenAI.gpt-5` | ~$30 | `MistralAI.devstral-small-latest` | $0.3 | **99%** |
| Samantha | `OpenAI.gpt-5.2-chat-latest` | ~$30+ | `MistralAI.mistral-medium-latest` | $1.2 | **96%** |
| Dr. Claire Lacroix | `OpenAI.o1` | ~$60 | `OpenRouter.anthropic/claude-sonnet-4-6` | $15 | **75%** |
| Samantha R1 | `OpenAI.o3` | ~$40 | `OpenRouter.anthropic/claude-sonnet-4-6` | $15 | **63%** |

### Priority 2: Mid-Range Models

| Persona | Current Base | Cost/M output | Recommended | Cost/M output | Savings |
|---------|-------------|---------------|-------------|---------------|---------|
| Dr. Étienne Charpentier | `OpenAI.gpt-4.1` | ~$8 | `MistralAI.mistral-medium-latest` | $1.2 | **85%** |

### Benchmark-Based Recommendations by Use Case

#### For conversational/creative personas (Albéric, Isola, Vanessa, Samantha, psychologist):
**Best option: `MistralAI.mistral-medium-latest`**
- Pro: Excellent French, long detailed responses (2487 chars avg), great quality, $1.2/M
- Con: Slower (11.6s avg), can be verbose
- Alternative: `OpenRouter.anthropic/claude-haiku-4.5` for faster responses (3.1s) at $4/M

#### For coding personas (codewriter, Emilio):
**Best option: `MistralAI.devstral-small-latest`**
- Pro: Fastest (2.4s), excellent code quality, $0.3/M
- Alternative: `MistralAI.mistral-small-latest` for more balanced code+conversation

#### For reasoning personas (Dr. Claire Lacroix, Samantha R1, deep thought):
**Best option: `OpenRouter.anthropic/claude-sonnet-4-6`**
- Pro: Best reasoning quality, structured responses, $15/M
- Con: Still expensive but 50-75% cheaper than o1/o3
- Alternative: `MistralAI.mistral-medium-latest` for 92% savings with good reasoning

#### For the `multi-agent` model (currently INACTIVE):
- Currently on `Local.Qwen/Qwen2.5-7B-Instruct-AWQ` (deprecated small model)
- **Recommendation**: Either delete this model or migrate to a better base

### Known Issues Found

1. **Dr. Claire Lacroix** (`dr-claire-lacroix`): System prompt starts with "Tu es le Dr. Étienne Charpentier" — appears to be a **copy-paste error** from the Dr. Étienne Charpentier model. Should be corrected.

2. **multi-agent** (`multi-agent:latest`): Model is **inactive** and uses an old local model. Consider deleting.

---

## Cost Summary (if all recommendations applied)

| Category | Models | Current Cost/M | Recommended Cost/M | Savings |
|----------|--------|---------------|-------------------|---------|
| TP Tutors (3) | 3 | $1.6 | $0.3 | 81% |
| Creative personas (5) | 5 | ~$30 | $1.2 | 96% |
| Code personas (2) | 2 | ~$30 | $0.3 | 99% |
| Reasoning personas (2) | 2 | ~$50 | $15 | 70% |
| Mid-range (1) | 1 | ~$8 | $1.2 | 85% |
| **Total (13 models)** | | **~$150/M avg** | **~$5/M avg** | **~97%** |

*Note: Actual savings depend on usage volume. These are per-million-output-token costs.*
