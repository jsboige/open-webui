# Model Benchmark Report

**Generated:** 2026-03-03 17:55 UTC
**Tool:** `scripts/benchmark-models.py`


## Alternatives to OpenAI.gpt-4.1-mini for TP tutors (code + pedagogy)

**Current model:** `OpenAI.gpt-4.1-mini`

### Summary

| Model | Avg Latency | Avg Output | Est. Cost/1M tok | Errors |
|-------|------------|-----------|-----------------|--------|
| `OpenAI.gpt-4.1-mini` **(current)** | 5.3s | 1097 chars | $1.6/M out | 0/5 |
| `MistralAI.mistral-small-latest` | 3.3s | 1247 chars | $0.3/M out | 0/5 |
| `MistralAI.devstral-small-latest` | 2.4s | 1534 chars | $0.3/M out | 0/5 |
| `DeepSeek.deepseek-chat` | 14.9s | 1341 chars | $0.28/M out | 0/5 |
| `Local.qwen3.5-35b-a3b-fast` | 51.6s | 2038 chars | $0.0/M out **FREE** | 1/5 |
| `Local.qwen3.5-35b-a3b` | 39.4s | 1916 chars | $0.0/M out **FREE** | 1/5 |

### Detailed Results

| Model | Prompt | Latency | Output | Response (excerpt) |
|-------|--------|---------|--------|-------------------|
| `DeepSeek.deepseek-chat` | Q&A Francais | 6.7s | 553c | L'intelligence artificielle (IA) est une discipline informatique qui vise à crée |
| `DeepSeek.deepseek-chat` | Code Python | 8.0s | 863c | ```python def is_palindrome(s: str) -> bool:     """     Check if a string is a  |
| `DeepSeek.deepseek-chat` | Raisonnement | 24.3s | 1782c | Allons-y étape par étape.  ---  **1. Situation initiale**  - Distance Paris–Lyon |
| `DeepSeek.deepseek-chat` | Analyse Structuree | 33.3s | 3444c | ### **Cloud Computing**  **Avantages :** - **Réduction des coûts initiaux** : Pa |
| `DeepSeek.deepseek-chat` | Creativite FR | 2.2s | 65c | Clavier qui danse L'écran s'illumine, code Un monde nouveau naît. |
| `Local.qwen3.5-35b-a3b` | Q&A Francais | 43.7s | 455c | L'intelligence artificielle est un domaine technologique qui vise à créer des sy |
| `Local.qwen3.5-35b-a3b` | Code Python | 28.2s | 285c | ```python def is_palindrome(s: str) -> bool:     """     Check if a given string |
| `Local.qwen3.5-35b-a3b` | Raisonnement | 47.0s | 2345c | Voici le raisonnement étape par étape pour résoudre ce problème.  ### 1. Définir |
| `Local.qwen3.5-35b-a3b` | Analyse Structuree | 38.8s | 4581c | Voici une comparaison structurée entre le **Cloud Computing** et l'**Hébergement |
| `Local.qwen3.5-35b-a3b` | Creativite FR | 122.3s | 0c | **HTTP 502: <!DOCTYPE html PUBLI** |
| `Local.qwen3.5-35b-a3b-fast` | Q&A Francais | 63.7s | 398c | L'intelligence artificielle désigne des systèmes informatiques capables d'effect |
| `Local.qwen3.5-35b-a3b-fast` | Code Python | 54.5s | 400c | ```python def is_palindrome(s: str) -> bool:     """     Check if a given string |
| `Local.qwen3.5-35b-a3b-fast` | Raisonnement | 52.0s | 2248c | Voici le raisonnement étape par étape pour résoudre ce problème.  ### 1. Mise en |
| `Local.qwen3.5-35b-a3b-fast` | Analyse Structuree | 36.4s | 5105c | Voici une comparaison structurée entre le **Cloud Computing** et l'**hébergement |
| `Local.qwen3.5-35b-a3b-fast` | Creativite FR | 121.3s | 0c | **HTTP 502: <!DOCTYPE html PUBLI** |
| `MistralAI.devstral-small-latest` | Q&A Francais | 1.2s | 753c | L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à cré |
| `MistralAI.devstral-small-latest` | Code Python | 0.9s | 465c | ```python def is_palindrome(s: str) -> bool:     """     Check if a given string |
| `MistralAI.devstral-small-latest` | Raisonnement | 3.3s | 1730c | Pour résoudre ce problème, nous allons suivre ces étapes :  1. **Calculer la dis |
| `MistralAI.devstral-small-latest` | Analyse Structuree | 5.9s | 4574c | Voici une comparaison structurée des avantages et inconvénients du **cloud compu |
| `MistralAI.devstral-small-latest` | Creativite FR | 0.5s | 146c | **Code qui s'écrit,** **l'écran s'illumine,** **l'erreur s'efface.**  *(Un haiku |
| `MistralAI.mistral-small-latest` | Q&A Francais | 1.1s | 619c | 1. **L'intelligence artificielle (IA)** est une technologie qui permet aux machi |
| `MistralAI.mistral-small-latest` | Code Python | 1.0s | 472c | ```python def is_palindrome(s: str) -> bool:     """     Check if a given string |
| `MistralAI.mistral-small-latest` | Raisonnement | 5.0s | 2361c | Pour résoudre ce problème, nous allons déterminer l'heure et la distance à laque |
| `MistralAI.mistral-small-latest` | Analyse Structuree | 6.6s | 2642c | Voici une comparaison des avantages et inconvénients du **cloud computing** et d |
| `MistralAI.mistral-small-latest` | Creativite FR | 2.6s | 143c | **Code qui s'écoule,** **L'écran s'illumine d'espoir—** **Bug, puis solution.**  |
| `OpenAI.gpt-4.1-mini` | Q&A Francais | 2.2s | 551c | L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à cré |
| `OpenAI.gpt-4.1-mini` | Code Python | 2.2s | 256c | ```python def is_palindrome(s: str) -> bool:     """     Check if the given stri |
| `OpenAI.gpt-4.1-mini` | Raisonnement | 10.4s | 1587c | Données du problème : - Distance Paris-Lyon = 480 km - Train 1 part de Paris à 9 |
| `OpenAI.gpt-4.1-mini` | Analyse Structuree | 10.3s | 3014c | Voici une comparaison des avantages et inconvénients du **cloud computing** vers |
| `OpenAI.gpt-4.1-mini` | Creativite FR | 1.2s | 78c | Code danse en rythme,   Bits tissent des poèmes neufs,   Nuit claire s’allume. |

## Alternatives to OpenAI.gpt-4o / gpt-5 for personas

**Current model:** `OpenAI.gpt-4o`

### Summary

| Model | Avg Latency | Avg Output | Est. Cost/1M tok | Errors |
|-------|------------|-----------|-----------------|--------|
| `OpenAI.gpt-4o` **(current)** | 7.0s | 1127 chars | $10.0/M out | 0/5 |
| `OpenRouter.anthropic/claude-haiku-4.5` | 3.1s | 931 chars | $4.0/M out | 0/5 |
| `OpenRouter.anthropic/claude-sonnet-4` | 6.3s | 986 chars | $15.0/M out | 0/5 |
| `MistralAI.mistral-medium-latest` | 11.6s | 2487 chars | $1.2/M out | 0/5 |
| `OpenRouter.deepseek/deepseek-v3.2` | 21.7s | 1331 chars | $0.28/M out | 0/5 |
| `OpenRouter.x-ai/grok-3-mini` | 14.2s | 2065 chars | $0.5/M out | 0/5 |

### Detailed Results

| Model | Prompt | Latency | Output | Response (excerpt) |
|-------|--------|---------|--------|-------------------|
| `MistralAI.mistral-medium-latest` | Q&A Francais | 3.1s | 849c | L’**intelligence artificielle (IA)** désigne des systèmes informatiques capables |
| `MistralAI.mistral-medium-latest` | Code Python | 1.0s | 338c | ```python def is_palindrome(s: str) -> bool:     """     Check if a given string |
| `MistralAI.mistral-medium-latest` | Raisonnement | 13.2s | 2304c | Pour résoudre ce problème, nous allons suivre les étapes suivantes :  ### **1. D |
| `MistralAI.mistral-medium-latest` | Analyse Structuree | 39.4s | 8848c | Voici une comparaison structurée des **avantages et inconvénients** du **cloud c |
| `MistralAI.mistral-medium-latest` | Creativite FR | 1.2s | 95c | **Code dans la nuit** L'écran s'illumine — une boucle sans fin s'ouvre comme un  |
| `OpenAI.gpt-4o` | Q&A Francais | 3.2s | 625c | L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à cré |
| `OpenAI.gpt-4o` | Code Python | 1.5s | 257c | ```python def is_palindrome(s: str) -> bool:     """     Check if the given stri |
| `OpenAI.gpt-4o` | Raisonnement | 10.7s | 1530c | Pour résoudre ce problème, nous devons calculer à quel moment les deux trains se |
| `OpenAI.gpt-4o` | Analyse Structuree | 18.2s | 3152c | Bien sûr, voici une comparaison structurée des avantages et inconvénients du clo |
| `OpenAI.gpt-4o` | Creativite FR | 1.3s | 73c | Clavier crépite,   Code danse sous mes doigts vifs,   L'écran s'illumine. |
| `OpenRouter.anthropic/claude-haiku-4.5` | Q&A Francais | 2.5s | 628c | # L'Intelligence Artificielle  L'intelligence artificielle (IA) est un ensemble  |
| `OpenRouter.anthropic/claude-haiku-4.5` | Code Python | 1.6s | 650c | ```python def is_palindrome(s: str) -> bool:     """     Check if a string is a  |
| `OpenRouter.anthropic/claude-haiku-4.5` | Raisonnement | 3.8s | 1012c | # Résolution du problème de rencontre de deux trains  ## Données - Train A (Pari |
| `OpenRouter.anthropic/claude-haiku-4.5` | Analyse Structuree | 6.7s | 2265c | # Cloud Computing vs Hébergement On-Premise pour une PME  ## ☁️ CLOUD COMPUTING  |
| `OpenRouter.anthropic/claude-haiku-4.5` | Creativite FR | 1.0s | 99c | # Haiku sur la programmation  Codes s'entrelacent Bugs dansent dans la nuit noir |
| `OpenRouter.anthropic/claude-sonnet-4` | Q&A Francais | 4.6s | 740c | L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à cré |
| `OpenRouter.anthropic/claude-sonnet-4` | Code Python | 2.8s | 703c | ```python def is_palindrome(s: str) -> bool:     """     Check if a string is a  |
| `OpenRouter.anthropic/claude-sonnet-4` | Raisonnement | 8.4s | 1079c | Je vais résoudre ce problème étape par étape.  ## Données du problème - **Train  |
| `OpenRouter.anthropic/claude-sonnet-4` | Analyse Structuree | 13.6s | 2304c | # Comparaison Cloud Computing vs On-Premise pour une PME (50 employés)  ## 🌥️ CL |
| `OpenRouter.anthropic/claude-sonnet-4` | Creativite FR | 1.9s | 104c | Voici un haiku sur la programmation :  Code qui s'écrit la nuit Bug silencieux q |
| `OpenRouter.deepseek/deepseek-v3.2` | Q&A Francais | 4.6s | 627c | 1. L'intelligence artificielle (IA) est une technologie qui permet à des machine |
| `OpenRouter.deepseek/deepseek-v3.2` | Code Python | 9.4s | 836c | ```python def is_palindrome(s: str) -> bool:     """     Check if a string is a  |
| `OpenRouter.deepseek/deepseek-v3.2` | Raisonnement | 52.2s | 1884c | **Données du problème :**  - Distance entre Paris et Lyon : \( 480 \) km   - Tra |
| `OpenRouter.deepseek/deepseek-v3.2` | Analyse Structuree | 40.3s | 3248c | # Comparaison Cloud Computing vs Hébergement On-Premise pour une PME de 50 emplo |
| `OpenRouter.deepseek/deepseek-v3.2` | Creativite FR | 2.2s | 61c | Clavier qui danse, Le bug s'envole enfin - Nuit, écran, café. |
| `OpenRouter.x-ai/grok-3-mini` | Q&A Francais | 8.7s | 814c | L'intelligence artificielle (IA) est un domaine de l'informatique qui vise à cré |
| `OpenRouter.x-ai/grok-3-mini` | Code Python | 7.9s | 293c | ```python def is_palindrome(s: str) -> bool:     """     Check if the given stri |
| `OpenRouter.x-ai/grok-3-mini` | Raisonnement | 19.4s | 2885c | Pour résoudre ce problème, analysons pas à pas la situation. Un train part de Pa |
| `OpenRouter.x-ai/grok-3-mini` | Analyse Structuree | 21.0s | 5977c | Voici une comparaison structurée des avantages et inconvénients du cloud computi |
| `OpenRouter.x-ai/grok-3-mini` | Creativite FR | 13.8s | 355c | Voici un haïku en français sur le thème de la programmation, en respectant la st |