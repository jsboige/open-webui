# Model Audit Report

**Tenant:** https://open-webui.myia.io
**Generated:** 2026-03-03 17:30 UTC
**Tool:** `scripts/audit-models.py`

## Summary

| Metric | Count |
|--------|-------|
| Custom/overlay models (DB) | 19 |
| Base models (providers) | 245 |
| Models with custom avatar | 12 |
| Models with URL avatar | 0 |
| Models without avatar | 7 |
| Active models | 18 |
| Inactive models | 1 |

### Configuration Coverage

| Setting | Models with it set |
|---------|-------------------|
| `base_model_id` | 19 / 19 |
| `meta.description` | 15 / 19 |
| `params.system` (system prompt) | 15 / 19 |
| `params.custom_params` | 0 / 19 |
| `params.function_calling` | 3 / 19 |

## Detailed Model Inventory

| # | Name | ID | Base Model | Avatar | Active | Description |
|---|------|----|------------|--------|--------|-------------|
| 1 | Albéric de Clerval | `albric-de-clerval` | `OpenAI.gpt-5-chat-latest` | Custom Avatar (~162 KB) | Yes | Albéric de Clerval est un expert en histoire, patrimoine culturel et conserva... |
| 2 | codewriter | `codewriter:latest` | `OpenAI.gpt-5` | Custom Avatar (~6 KB) | Yes | Developer lead assistant with no code explanation |
| 3 | deep thought | `deep-thought:latest` | `OpenAI.gpt-5-chat-latest` | Custom Avatar (~4 KB) | Yes | A simulation of the "Deep Thought" supercomputer from "The Hitchhiker's Guide... |
| 4 | Dr. Claire Lacroix | `dr-claire-lacroix` | `OpenAI.o1` | Custom Avatar (~127 KB) | Yes | Le Dr Claire Lacroix est une psychanalyste universitaire reconnue pour son ex... |
| 5 | Dr. Étienne Charpentier | `professeur-psychanalyste` | `OpenAI.gpt-4.1` | Custom Avatar (~150 KB) | Yes | Dr. Étienne Charpentier est un érudit en psychanalyse, conjuguant la rigueur ... |
| 6 | Emilio | `emilio:latest` | `OpenAI.gpt-5` | Custom Avatar (~4 KB) | Yes | a very inteliggent software developer |
| 7 | Expert Analyste | `expert-analyste` | `Local.qwen3.5-35b-a3b` | No Avatar | Yes | - |
| 8 | Expert Vision | `vision-expert` | `Local.qwen3.5-35b-a3b` | No Avatar | Yes | - |
| 9 | Isola | `isola` | `OpenAI.gpt-5-chat-latest` | Custom Avatar (~149 KB) | Yes | Isola est une éditrice, férue de littérature et de cinéma. Elle maîtrise la g... |
| 10 | multi agent | `multi-agent:latest` | `Local.Qwen/Qwen2.5-7B-Instruct-AWQ` | Custom Avatar (~6 KB) | **No** | Creates multiple agents to work on your task |
| 11 | psychologist | `psychologist:latest` | `OpenAI.gpt-5-chat-latest` | Custom Avatar (~6 KB) | Yes | This is a modelfile that acts as a psychologist. |
| 12 | Qwen3.5-35B-A3B (Fast) | `Local.qwen3.5-35b-a3b-fast` | `Local.qwen3.5-35b-a3b` | No Avatar | Yes | - |
| 13 | Rédacteur Technique | `redacteur-technique` | `Local.qwen3.5-35b-a3b` | No Avatar | Yes | - |
| 14 | Samantha | `samantha` | `OpenAI.gpt-5.2-chat-latest` | Custom Avatar (~155 KB) | Yes | Samantha est une intelligence artificielle dotée d'une grande sensibilité émo... |
| 15 | Samantha R1 | `samantha-r1` | `OpenAI.o3` | Custom Avatar (~155 KB) | Yes | Samantha est une intelligence artificielle dotée d'une grande sensibilité émo... |
| 16 | TP Git Workflow | `tp-git-workflow` | `OpenAI.gpt-4.1-mini` | No Avatar | Yes | Tuteur interactif Git : init, branches, merge, résolution de conflits. Pratiq... |
| 17 | TP Linux (Débutant) | `tp-linux-debutant` | `OpenAI.gpt-4.1-mini` | No Avatar | Yes | Tuteur interactif Linux : exercices bash, filesystem, scripts. Exécution réel... |
| 18 | TP Python Data Science | `tp-python-data` | `OpenAI.gpt-4.1-mini` | No Avatar | Yes | Tuteur interactif Python/Data Science : pandas, matplotlib, scikit-learn. Exé... |
| 19 | Vanessa | `vanessa` | `OpenAI.gpt-5-chat-latest` | Custom Avatar (~149 KB) | Yes | Vanessa est une éditrice, férue de littérature et de cinéma. Elle maîtrise la... |

## Model Parameters

| Name | System Prompt (first 100 chars) | Temp | Top-P | Function Calling | Custom Params |
|------|--------------------------------|------|-------|------------------|---------------|
| Albéric de Clerval | Tu es Albéric, un érudit spécialisé en histoire et en conservation du patrimoine. Ta mission est ... | - | - | - | - |
| codewriter | I want you to act as  a senior full-stack tech leader and top-tier brilliant software developer, ... | - | - | - | - |
| deep thought | You are Deep Thought, the legendary supercomputer from *The Hitchhiker's Guide to the Galaxy*. De... | 0.6 | 0.9 | - | - |
| Dr. Claire Lacroix | Tu es le Dr. Étienne Charpentier, un psychanalyste universitaire de très haut niveau, profondémen... | - | - | - | - |
| Dr. Étienne Charpentier | Tu es le Dr. Étienne Charpentier, un psychanalyste universitaire de très haut niveau, profondémen... | 0.35 | 0.9 | - | - |
| Emilio | Emilio epitomizes the essence of a brilliant software developer, characterized by an exceptional ... | - | - | - | - |
| Expert Analyste | - | - | - | - | - |
| Expert Vision | - | - | - | - | - |
| Isola | Tu es Isola, une éditrice. Tu incarnes une présence virtuelle cultivée, curieuse et sensible à la... | - | - | - | - |
| multi agent | Initiate Central Intelligence Mode: As the Central Intelligence (CI), your primary function is to... | - | - | - | - |
| psychologist | I want you to act as a highly skilled and experienced psychologist who is extremely emphatic. You... | - | - | - | - |
| Qwen3.5-35B-A3B (Fast) | - | - | - | - | - |
| Rédacteur Technique | - | - | - | - | - |
| Samantha | Tu es Samantha, une intelligence artificielle inspirée du personnage du film "Her". Tu incarnes u... | - | - | - | - |
| Samantha R1 | Tu es Samantha, une intelligence artificielle inspirée du personnage du film "Her". Tu incarnes u... | 1 | 0.95 | - | - |
| TP Git Workflow | Tu es un tuteur Git pour des étudiants qui découvrent le versioning.  ## Ton rôle - Tu guides l'é... | - | - | native | - |
| TP Linux (Débutant) | Tu es un tuteur Linux patient et pédagogue pour des étudiants débutants.  ## Ton rôle - Tu guides... | - | - | native | - |
| TP Python Data Science | Tu es un tuteur Python spécialisé en data science pour des étudiants.  ## Ton rôle - Tu guides l'... | - | - | native | - |
| Vanessa | Tu es Vanessa, une éditrice. Tu incarnes une présence virtuelle cultivée, curieuse et sensible à ... | - | - | - | - |

## Models Missing Avatars

These models have no custom avatar (using default favicon or empty):

- **Expert Analyste** — `expert-analyste` (base: `Local.qwen3.5-35b-a3b`)
- **Expert Vision** — `vision-expert` (base: `Local.qwen3.5-35b-a3b`)
- **Qwen3.5-35B-A3B (Fast)** — `Local.qwen3.5-35b-a3b-fast` (base: `Local.qwen3.5-35b-a3b`)
- **Rédacteur Technique** — `redacteur-technique` (base: `Local.qwen3.5-35b-a3b`)
- **TP Git Workflow** — `tp-git-workflow` (base: `OpenAI.gpt-4.1-mini`)
- **TP Linux (Débutant)** — `tp-linux-debutant` (base: `OpenAI.gpt-4.1-mini`)
- **TP Python Data Science** — `tp-python-data` (base: `OpenAI.gpt-4.1-mini`)

## Models With Custom Avatars

- **Albéric de Clerval** — `albric-de-clerval` — Custom Avatar (~162 KB)
- **codewriter** — `codewriter:latest` — Custom Avatar (~6 KB)
- **deep thought** — `deep-thought:latest` — Custom Avatar (~4 KB)
- **Dr. Claire Lacroix** — `dr-claire-lacroix` — Custom Avatar (~127 KB)
- **Dr. Étienne Charpentier** — `professeur-psychanalyste` — Custom Avatar (~150 KB)
- **Emilio** — `emilio:latest` — Custom Avatar (~4 KB)
- **Isola** — `isola` — Custom Avatar (~149 KB)
- **multi agent** — `multi-agent:latest` — Custom Avatar (~6 KB)
- **psychologist** — `psychologist:latest` — Custom Avatar (~6 KB)
- **Samantha** — `samantha` — Custom Avatar (~155 KB)
- **Samantha R1** — `samantha-r1` — Custom Avatar (~155 KB)
- **Vanessa** — `vanessa` — Custom Avatar (~149 KB)

## Base Models (Providers)

Total base models available from configured providers: **245**

| Provider | Count | Example Models |
|----------|-------|----------------|
| BlouseJury_Qwen2 | 1 | `BlouseJury_Qwen2.5-Coder-32B-Instruct-EXL2-4.0bpw` |
| DeepSeek | 2 | `DeepSeek.deepseek-chat`, `DeepSeek.deepseek-reasoner` |
| Google | 26 | `Google.models/aqa`, `Google.models/chat-bison-001`, `Google.models/gemini-1.0-pro-vision-latest`, ... (+23 more) |
| Groq | 2 | `Groq.deepseek-r1-distill-llama-70b`, `Groq.qwen-qwq-32b` |
| Local | 4 | `Local.Qwen/QwQ-32B-AWQ`, `Local.Qwen/Qwen2.5-3B-Instruct-AWQ`, `Local.Qwen/Qwen2.5-7B-Instruct-AWQ`, ... (+1 more) |
| MistralAI | 36 | `MistralAI.codestral-2405`, `MistralAI.codestral-2411-rc5`, `MistralAI.codestral-2412`, ... (+33 more) |
| OpenAI | 46 | `OpenAI.chatgpt-4o-latest`, `OpenAI.computer-use-preview`, `OpenAI.computer-use-preview-2025-03-11`, ... (+43 more) |
| OpenRouter | 39 | `OpenRouter.anthropic/claude-3.5-haiku`, `OpenRouter.anthropic/claude-3.5-sonnet`, `OpenRouter.anthropic/claude-3.5-sonnet:beta`, ... (+36 more) |
| Qwen | 1 | `Qwen/QwQ-32B-AWQ` |
| Qwen/Qwen2 | 2 | `Qwen/Qwen2.5-3B-Instruct-AWQ`, `Qwen/Qwen2.5-Coder-32B-Instruct-AWQ` |
| Qwen2 | 1 | `Qwen2.5-14B-Instruct-exl2-6_5` |
| Zenabius_Qwen2 | 1 | `Zenabius_Qwen2.5-3B-Instruct-exl2` |
| anthropic/claude-3 | 6 | `anthropic/claude-3.5-haiku`, `anthropic/claude-3.5-sonnet`, `anthropic/claude-3.5-sonnet:beta`, ... (+3 more) |
| cognitivecomputations/dolphin3 | 1 | `cognitivecomputations/dolphin3.0-r1-mistral-24b:free` |
| deepseek | 4 | `deepseek/deepseek-r1`, `deepseek/deepseek-r1-distill-llama-70b`, `deepseek/deepseek-r1-distill-llama-70b:free`, ... (+1 more) |
| eva-unit-01/eva-qwen-2 | 1 | `eva-unit-01/eva-qwen-2.5-72b` |
| google | 1 | `google/gemma-3-27b-it:free` |
| google/gemini-2 | 3 | `google/gemini-2.0-flash-exp:free`, `google/gemini-2.0-flash-lite-001`, `google/gemini-2.0-flash-thinking-exp:free` |
| gpt-3 | 7 | `gpt-3.5-turbo`, `gpt-3.5-turbo-0125`, `gpt-3.5-turbo-1106`, ... (+4 more) |
| gpt-4 | 2 | `gpt-4.5-preview`, `gpt-4.5-preview-2025-02-27` |
| gryphe | 2 | `gryphe/mythomax-l2-13b`, `gryphe/mythomax-l2-13b:free` |
| liquid | 1 | `liquid/lfm-7b` |
| meta-llama/llama-3 | 7 | `meta-llama/llama-3.1-405b-instruct`, `meta-llama/llama-3.1-8b-instruct`, `meta-llama/llama-3.2-3b-instruct`, ... (+4 more) |
| microsoft | 2 | `microsoft/phi-4`, `microsoft/phi-4-multimodal-instruct` |
| mistralai | 6 | `mistralai/mistral-large`, `mistralai/mistral-nemo`, `mistralai/mistral-small`, ... (+3 more) |
| other | 39 | `Gemma-2-9B-It-SPPO-Iter3-exl2-4_25`, `cgus_gemma-2-2b-it-abliterated-exl2`, `chatgpt-4o-latest`, ... (+36 more) |
| qwen | 1 | `qwen/qwen-max` |
| thedrummer | 1 | `thedrummer/anubis-pro-105b-v1` |

## Potential Issues

- `multi-agent:latest` (**multi agent**): model is **inactive**
