# Checklist de vérification tenant Open WebUI

> **Usage** : Exécuter avant chaque cours/déploiement pour vérifier qu'une instance est opérationnelle.
> **Dernière exécution complète** : 2026-04-08 (EPITA — cours PPC)

## 1. Infrastructure Docker

| Check | Commande | Attendu |
|-------|---------|---------|
| Container OWUI UP (healthy) | `docker ps --filter name={tenant}-open-webui` | `Up ... (healthy)` |
| Container Terminal UP | `docker ps --filter name=open-terminal-{tenant}` | `Up` |
| Container Channel Bot UP | `docker ps --filter name={tenant}-channel-bot` | `Up`, logs: `Socket.IO connected` |

## 2. Authentification

| Check | Endpoint | Attendu |
|-------|----------|---------|
| Admin login | `POST /api/v1/auths/signin` | token JWT valide |
| Bot login | idem avec `bot@{tenant}.myia.io` | token JWT valide |
| Users listing | `GET /api/v1/users/` | >= 2 users (admin + bot) |

## 3. Connecteurs LLM (OpenAI Connections)

| Check | Détail |
|-------|--------|
| Nombre de connecteurs | 12 (OpenAI, Local micro/mini/medium/large, Pipelines, OpenRouter, Anthropic, DeepSeek, MistralAI, GoogleDirect, Z.ai) |
| Groq ABSENT | Vérifié supprimé |
| MistralAI fonctionnel | `POST /api/chat/completions` avec `MistralAI.devstral-small-latest` |
| OpenAI fonctionnel | idem avec `OpenAI.gpt-4.1-mini` |
| DeepSeek fonctionnel | idem avec `DeepSeek.deepseek-chat` |
| OpenRouter fonctionnel | idem avec `OpenRouter.anthropic/claude-haiku-4.5` |
| vLLM medium (Qwen 3.5) | idem avec `Local.qwen3.5-35b-a3b` |
| vLLM mini (OmniCoder) | idem avec `Local.omnicoder-9b` |

### Clés à vérifier

| Connecteur | Index | Format clé |
|-----------|-------|------------|
| vLLM mini | [2] | `FEECE4DF2224BF0A...` (32 hex) |
| vLLM medium | [3] | `7711C3D0426C998B...` (32 hex) |
| MistralAI | [9] | `X8IfiK7R56tVCha...` |

## 4. Modèles Personas (Custom Models)

### Tuteurs TP (5 — prioritaires pour les cours)

| Modèle | Base | function_calling |
|--------|------|-----------------|
| `tp-linux-debutant` | `MistralAI.devstral-small-latest` | `native` |
| `tp-git-workflow` | `MistralAI.devstral-small-latest` | `native` |
| `tp-python-data` | `MistralAI.devstral-small-latest` | `native` |
| `tp-prompt-engineering` | `MistralAI.mistral-medium-latest` | aucun (conversationnel) |
| `tp-data-analyst-agent` | `MistralAI.devstral-small-latest` | `native` |

### Personas générales

| Persona | Base attendu (avril 2026) |
|---------|--------------------------|
| Samantha, Emilio, Isola, deep thought | `OpenAI.gpt-5` |
| Dr. Étienne Charpentier | `OpenAI.o4-mini` |
| codewriter | `OpenAI.gpt-5.2` |
| psychologist | `OpenAI.gpt-4o-mini` ou supérieur |
| Albéric de Clerval | `OpenAI.gpt-4o` ou supérieur |
| Expert Analyste, Redacteur Technique, Expert Vision | `Local.qwen3.5-35b-a3b` |
| Qwen 3.5 (Instruct/Think/Code/Reason/Fast) | `Local.qwen3.5-35b-a3b` |

### Vérifications personas

- [ ] QwQ supprimé (pas de `Local-QwQ-32B-Concise`)
- [ ] Aucune base `OpenAI.o3-mini` (retiré)
- [ ] Aucune base `OpenAI.chatgpt-4o-latest` (retiré)
- [ ] Aucune base `Groq.*` (supprimé)

## 5. Embedding (RAG)

| Check | Attendu |
|-------|---------|
| Engine | `openai` |
| Model | `qwen3-4b-awq-embedding` |
| URL | `https://embeddings.myia.io/v1` |
| Clé | `365f36ffbff3f43de53299625590381a...` (70 chars) |

## 6. Audio

| Check | Attendu |
|-------|---------|
| TTS engine | `openai` (Kokoro) |
| TTS URL | `http://kokoro-tts:8880/v1` |
| TTS model | `kokoro` |
| STT engine | `openai` (Whisper) |
| STT URL | `http://whisper-stt-adapter:8787/v1` |
| STT model | `whisper-1` |

## 7. Image Generation

| Check | Attendu |
|-------|---------|
| Enabled | `true` |
| Engine | `automatic1111` (SD Forge) |
| URL | `https://turbo.stable-diffusion-webui-forge.myia.io/` |
| Model | `sdxl_lightning_4step.safetensors` |

## 8. RAG & Web Search

| Check | Attendu |
|-------|---------|
| Tika URL | `http://tika:9998` |
| Web Search | `searxng` via `https://search.myia.io/search?q=<query>` |
| TOP_K | 3 |
| Chunk size | 1000 |

## 9. Knowledge Bases

| Check | Détail |
|-------|--------|
| KBs présentes | 12+ (dont thématiques IA) |
| KB PPC (EPITA) | `IA - Programmation par contraintes` |
| Bibliographie IA | présente (148+ fichiers) |

## 10. Channels & Bots

| Check | Attendu |
|-------|---------|
| Channel principal | `#2025-ppc-general` (EPITA) |
| Bot connecté | `Assistant {Tenant}` en mode `faq` |
| Bot Socket.IO | logs: `Socket.IO connected`, `Listening on ALL channels` |

## 11. Tools & MCP

| Check | Attendu |
|-------|---------|
| SK-Agent MCP | `http://myia-mcp-proxy:9090/sk-agent/mcp` (bearer auth) |
| Functions (5 actives) | Markdown Normalizer, Async Context Compression, Smart Mind Map, Flash Card, Export to Word |
| Functions (2 inactives) | EasyLang Translation, Smart Infographic |

## 12. Open Terminal

| Check | Attendu |
|-------|---------|
| Python | 3.12+ |
| pandas | installé |
| numpy, matplotlib | installés |
| Datasets | `~/datasets/` : `ventes_ecommerce.csv`, `donnees_rh.csv`, `logs_web.csv` |

## 13. Tests Playwright (automatisés)

```bash
cd tests/playwright
npx playwright test scenarios/18-full-stack-services.spec.ts --project=myia      # 28 tests (ALL services)
npx playwright test scenarios/16-tp-datasets-validation.spec.ts --project=myia   # 17 tests
npx playwright test scenarios/17-tp-multi-tenant.spec.ts --project=myia          # 9 tests
npx playwright test scenarios/10-multi-tenant.spec.ts --project=myia             # 4 tests
```

---

## Script de vérification rapide

```bash
# Usage: TENANT=epita ./scripts/quick-verify.sh
# Authentifie, teste les modèles critiques, vérifie les configs
source .env
TENANT=${TENANT:-epita}
URL_VAR="${TENANT^^}_URL"
EMAIL_VAR="${TENANT^^}_EMAIL"
PASS_VAR="${TENANT^^}_PASSWORD"
# ... (à développer)
```

## 14. Tests fonctionnels (manuels via API)

Ces tests ne sont pas couverts par Playwright et doivent être vérifiés manuellement :

```bash
# Embedding (via chat avec KB)
curl -X POST {URL}/api/chat/completions -d '{"model":"...", "messages":[...], "files":[{"type":"collection","id":"KB_ID"}]}'

# TTS
curl -X POST {URL}/api/v1/audio/speech -d '{"input":"Bonjour"}' → HTTP 200 + audio bytes

# Image Gen (SD Forge status)
curl https://turbo.stable-diffusion-webui-forge.myia.io/sdapi/v1/sd-models → liste modèles

# Chaque persona
curl -X POST {URL}/api/chat/completions -d '{"model":"PERSONA_ID","messages":[...]}'
```

### Notes de compatibilité modèles reasoning (o4-mini, o3, o1)
- Ne supportent PAS : `temperature`, `top_p`, `top_k`, `min_p`, `frequency_penalty`, `presence_penalty`
- Personas sur ces modèles : supprimer ces params, ne garder que `system` et `max_tokens`

## Historique des vérifications

| Date | Tenant | Résultat | Notes |
|------|--------|----------|-------|
| 2026-04-08 | EPITA | OK | Groq supprimé, MistralAI débloqué, vLLM réparé, embedding key MAJ, personas MAJ, o4-mini params nettoyés |
| 2026-04-08 | ALL | OK | Config propagée (OpenAI, Embedding, Audio, Image, RAG, Tools) — EPF personas corrigées |
| 2026-04-08 | myia | OK | Scenario 18: 28/28 pass — codewriter fixé (gpt-5.1-codex→gpt-5.2), API trailing slashes corrigés |
