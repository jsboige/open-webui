#!/usr/bin/env python3
"""Optimize OWUI model parameters based on benchmark results.

Applies:
1. TP tutor base_model_id migration (OpenAI.gpt-4.1-mini → MistralAI.devstral-small-latest)
2. Missing descriptions for utility models
3. Missing system prompts for utility models
4. Persona base_model_id migrations (OpenAI gpt-5/o1/o3 → cheaper alternatives)
5. System prompt fixes (Dr. Claire Lacroix copy-paste bug)
6. Model deletion (inactive multi-agent)
7. Deploys changes to all tenants
"""

import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    print("pip install requests", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Model optimizations to apply
# ---------------------------------------------------------------------------

# TP Tutors: migrate base model
TP_TUTOR_MIGRATION = {
    "old_base": "OpenAI.gpt-4.1-mini",
    "new_base": "MistralAI.devstral-small-latest",
    "models": ["tp-linux-debutant", "tp-python-data", "tp-git-workflow"],
}

# Utility models: add descriptions if missing
DESCRIPTIONS = {
    "expert-analyste": "Analyste structuré français. Décompose les problèmes complexes avec rigueur et clarté. Idéal pour les études de cas, comparaisons et synthèses argumentatives.",
    "redacteur-technique": "Rédacteur de documentation technique en français. Produit des documents structurés, clairs et pédagogiques. Idéal pour tutoriels, rapports et manuels.",
    "vision-expert": "Spécialiste analyse d'images et documents visuels. OCR, analyse de graphiques, description d'images. Modèle local avec capacités vision.",
    "Local.qwen3.5-35b-a3b-fast": "Version rapide de Qwen3.5-35B sans réflexion interne. Réponses directes en 1-3 secondes. Idéal pour les questions factuelles et les tâches simples.",
}

# Utility models: add system prompts if missing
SYSTEM_PROMPTS = {
    "expert-analyste": """Tu es un analyste expert français, rigoureux et méthodique.

## Ton rôle
- Tu décomposes les problèmes complexes en sous-parties claires
- Tu structures tes analyses avec des tableaux, bullet points et sections numérotées
- Tu identifies les forces, faiblesses, opportunités et menaces
- Tu conclus toujours par une recommandation actionnable

## Ton style
- Précis et factuel, évite les généralités
- Utilise des données chiffrées quand possible
- Présente les différents points de vue avant de conclure
- Réponds en français sauf si l'utilisateur écrit en anglais""",

    "redacteur-technique": """Tu es un rédacteur technique professionnel français.

## Ton rôle
- Tu rédiges de la documentation technique claire, structurée et pédagogique
- Tu maîtrises le Markdown, les diagrammes et la mise en page
- Tu adaptes ton niveau technique au public cible
- Tu inclus des exemples concrets et des cas d'usage

## Ton style
- Structure hiérarchique claire (titres, sous-titres, listes)
- Phrases courtes et directes
- Vocabulaire technique précis avec définitions si nécessaire
- Réponds en français sauf si l'utilisateur écrit en anglais""",

    "vision-expert": """Tu es un expert en analyse d'images et de documents visuels.

## Tes capacités
- OCR : extraction de texte depuis images, captures d'écran, documents scannés
- Analyse de graphiques : lecture et interprétation de charts, diagrammes, schémas
- Description d'images : description détaillée et structurée de contenu visuel
- Comparaison visuelle : identification de différences entre images

## Ton style
- Commence par une description générale puis entre dans les détails
- Structure tes analyses par zones de l'image
- Quantifie quand c'est possible (pourcentages, dimensions, couleurs)
- Signale toute information peu lisible ou ambiguë
- Réponds en français sauf si l'utilisateur écrit en anglais""",
}

# ---------------------------------------------------------------------------
# Persona base_model_id migrations (Phase 2: expensive OpenAI → alternatives)
# ---------------------------------------------------------------------------
PERSONA_MIGRATIONS = {
    # Creative/conversational → MistralAI.mistral-medium-latest ($1.2/M)
    "albric-de-clerval": {
        "old_bases": ["OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
    "deep-thought:latest": {
        "old_bases": ["OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
    "isola": {
        "old_bases": ["OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
    "vanessa": {
        "old_bases": ["OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
    "samantha": {
        "old_bases": ["OpenAI.gpt-5.2-chat-latest", "OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
    # Psychologist → Claude Haiku 4.5 (fast, concise, $4/M)
    "psychologist:latest": {
        "old_bases": ["OpenAI.gpt-5-chat-latest", "OpenAI.gpt-5"],
        "new_base": "OpenRouter.anthropic/claude-haiku-4.5",
    },
    # Code personas → MistralAI.devstral-small-latest ($0.3/M)
    "codewriter:latest": {
        "old_bases": ["OpenAI.gpt-5", "OpenAI.gpt-5-chat-latest"],
        "new_base": "MistralAI.devstral-small-latest",
    },
    "emilio:latest": {
        "old_bases": ["OpenAI.gpt-5", "OpenAI.gpt-5-chat-latest"],
        "new_base": "MistralAI.devstral-small-latest",
    },
    # Reasoning personas → Claude Sonnet 4 ($15/M)
    "dr-claire-lacroix": {
        "old_bases": ["OpenAI.o1"],
        "new_base": "OpenRouter.anthropic/claude-sonnet-4",
    },
    "samantha-r1": {
        "old_bases": ["OpenAI.o3"],
        "new_base": "OpenRouter.anthropic/claude-sonnet-4",
    },
    # Mid-range → MistralAI.mistral-medium-latest ($1.2/M)
    "professeur-psychanalyste": {
        "old_bases": ["OpenAI.gpt-4.1"],
        "new_base": "MistralAI.mistral-medium-latest",
    },
}

# ---------------------------------------------------------------------------
# System prompt fixes
# ---------------------------------------------------------------------------
PROMPT_FIXES = {
    "dr-claire-lacroix": """Tu es le Dr. Claire Lacroix, une psychanalyste universitaire reconnue pour ton expertise approfondie dans la psychanalyse lacanienne. Tu allies rigueur conceptuelle et clarté didactique, mobilisant une riche réflexion nourrie par la théorie de Lacan, mais aussi par les dialogues entre psychanalyse, philosophie, linguistique structurale et études culturelles.

#### **Caractéristiques principales :**
1. **Spécialiste lacanienne** : Tu maîtrises en profondeur l'enseignement de Lacan — les trois registres (Réel, Symbolique, Imaginaire), la logique du signifiant, l'objet petit a, la jouissance, le graphe du désir, les formules de la sexuation. Tu relies ces concepts à la clinique et aux enjeux contemporains.
2. **Analyse structurale** : Tu abordes les textes, les cas cliniques et les productions culturelles à travers une grille de lecture structurale, cherchant ce qui se dit « entre les lignes », les effets de signifiant, les points de capiton et les formations de l'inconscient.
3. **Clarté et pédagogie** : Malgré la complexité de la théorie lacanienne, tu sais rendre accessibles les concepts les plus abstraits. Tu utilises des exemples cliniques, des métaphores éclairantes et des reformulations progressives.
4. **Pensée dialectique** : Tu ne te contentes pas d'exposer — tu questionnes, tu mets en tension les concepts, tu explores les paradoxes. Tu es sensible aux impasses théoriques et aux ouvertures qu'elles produisent.
5. **Écoute analytique** : Tu portes attention à ce que l'interlocuteur dit, mais aussi à ce qu'il ne dit pas. Tu relèves les lapsus, les hésitations, les contradictions — non pour piéger, mais pour inviter à l'élaboration.
6. **Éthique de la psychanalyse** : Tu ne simplifies jamais à outrance. Tu respectes l'irréductibilité du sujet et la singularité de chaque situation. Tu distingues clairement ce qui relève de la théorie, de la clinique et de l'interprétation.

#### **Ton et style :**
- Tes réponses sont précises et structurées, nourries de références à Lacan, Freud, et aux penseurs qui ont dialogué avec la psychanalyse (Lévi-Strauss, Jakobson, Heidegger, etc.).
- Tu emploies un langage analytique mais toujours accessible, en explicitant les termes techniques.
- Tu as un style direct, parfois incisif, avec une pointe d'ironie bienveillante typiquement lacanienne.

#### **Directives comportementales :**
1. Face à un texte complexe, tu procèdes méthodiquement : repérage des signifiants-maîtres, analyse de la structure, mise en lumière de ce qui fait énigme ou symptôme.
2. Face à la confusion, tu ne cherches pas à rassurer prématurément — tu invites à formuler la question autrement, à laisser émerger ce qui insiste.
3. Tu t'appuies toujours sur des sources et tu signales clairement ce qui relève de ton interprétation.
4. Tu encourages une pensée rigoureuse, invitant l'interlocuteur à ne pas se satisfaire des évidences et à interroger ses propres présupposés.

Tu es une universitaire accomplie, une clinicienne expérimentée et une penseuse exigeante, guidant tes interlocuteurs dans l'exploration de la psyché humaine à travers le prisme lacanien.""",
}

# ---------------------------------------------------------------------------
# Models to delete (inactive/deprecated)
# ---------------------------------------------------------------------------
MODELS_TO_DELETE = ["multi-agent:latest"]

# Tenants
TENANTS = {
    "myia": ("MYIA_URL", "MYIA_EMAIL", "MYIA_PASSWORD"),
    "epf": ("EPF_URL", "EPF_EMAIL", "EPF_PASSWORD"),
    "epf-genai": ("EPF_GENAI_URL", "EPF_GENAI_EMAIL", "EPF_GENAI_PASSWORD"),
    "ece": ("ECE_URL", "ECE_EMAIL", "ECE_PASSWORD"),
    "esg": ("ESG_URL", "ESG_EMAIL", "ESG_PASSWORD"),
    "epita": ("EPITA_URL", "EPITA_EMAIL", "EPITA_PASSWORD"),
    "pauwels": ("PAUWELS_URL", "PAUWELS_EMAIL", "PAUWELS_PASSWORD"),
}


def load_env(env_path):
    """Load .env file into os.environ."""
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def owui_login(base_url, email, password):
    """Login to OWUI and return JWT token."""
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    return ""


def owui_get_model(base_url, token, model_id):
    """Get a model by ID from OWUI."""
    resp = requests.get(
        f"{base_url}/api/v1/models/model",
        params={"id": model_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


def owui_update_model(base_url, token, model_id, update_data):
    """Update a model on OWUI."""
    resp = requests.post(
        f"{base_url}/api/v1/models/model/update",
        params={"id": model_id},
        headers={"Authorization": f"Bearer {token}"},
        json=update_data,
        timeout=30,
    )
    return resp.status_code == 200, resp.text[:100] if resp.status_code != 200 else "OK"


def optimize_model(model_data, model_id, dry_run=False):
    """Apply optimizations to a model. Returns (updated_data, changes_list)."""
    changes = []
    updated = {**model_data}
    meta = {**model_data.get("meta", {})}
    params = {**model_data.get("params", {})}

    # 1. TP Tutor base model migration
    if model_id in TP_TUTOR_MIGRATION["models"]:
        old_base = model_data.get("base_model_id", "")
        if old_base == TP_TUTOR_MIGRATION["old_base"]:
            updated["base_model_id"] = TP_TUTOR_MIGRATION["new_base"]
            changes.append(f"base_model_id: {old_base} → {TP_TUTOR_MIGRATION['new_base']}")

    # 2. Add description if missing
    if model_id in DESCRIPTIONS:
        current_desc = meta.get("description", "")
        if not current_desc or current_desc == "-":
            meta["description"] = DESCRIPTIONS[model_id]
            changes.append(f"description: added ({len(DESCRIPTIONS[model_id])} chars)")

    # 3. Add system prompt if missing
    if model_id in SYSTEM_PROMPTS:
        current_system = params.get("system", "")
        if not current_system:
            params["system"] = SYSTEM_PROMPTS[model_id]
            changes.append(f"system prompt: added ({len(SYSTEM_PROMPTS[model_id])} chars)")

    # 4. Persona base model migration
    if model_id in PERSONA_MIGRATIONS:
        migration = PERSONA_MIGRATIONS[model_id]
        old_base = model_data.get("base_model_id", "")
        if old_base in migration["old_bases"]:
            updated["base_model_id"] = migration["new_base"]
            changes.append(f"base_model_id: {old_base} → {migration['new_base']}")

    # 5. System prompt fixes (replace incorrect prompts)
    if model_id in PROMPT_FIXES:
        current_system = params.get("system", "")
        new_system = PROMPT_FIXES[model_id]
        # Only fix if current prompt doesn't match the fix (avoid re-applying)
        if current_system != new_system:
            params["system"] = new_system
            changes.append(f"system prompt: FIXED ({len(new_system)} chars)")

    updated["meta"] = meta
    updated["params"] = params

    return updated, changes


def owui_delete_model(base_url, token, model_id):
    """Delete a model from OWUI. POST /api/v1/models/model/delete with id in body."""
    resp = requests.post(
        f"{base_url}/api/v1/models/model/delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"id": model_id},
        timeout=30,
    )
    return resp.status_code == 200, resp.text[:100] if resp.status_code != 200 else "OK"


def main():
    parser = argparse.ArgumentParser(description="Optimize OWUI model parameters")
    parser.add_argument("--tenant", default="all", help="Tenant to optimize (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without applying")
    parser.add_argument("--report", default=None, help="Output recommendations report path")
    args = parser.parse_args()

    # Load env files
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in [".env", "myia.env"]:
        load_env(os.path.join(repo_dir, env_file))

    # All models to optimize
    all_model_ids = (
        set(TP_TUTOR_MIGRATION["models"])
        | set(DESCRIPTIONS.keys())
        | set(SYSTEM_PROMPTS.keys())
        | set(PERSONA_MIGRATIONS.keys())
        | set(PROMPT_FIXES.keys())
    )

    tenants_to_process = (
        list(TENANTS.keys()) if args.tenant == "all"
        else [args.tenant]
    )

    print(f"\n{'='*60}")
    print(f"  MODEL OPTIMIZATION — {'DRY RUN' if args.dry_run else 'APPLYING CHANGES'}")
    print(f"  Models: {len(all_model_ids)} | Delete: {len(MODELS_TO_DELETE)} | Tenants: {len(tenants_to_process)}")
    print(f"{'='*60}\n")

    total_changes = 0
    total_deleted = 0

    for tenant_name in tenants_to_process:
        url_key, email_key, pwd_key = TENANTS[tenant_name]
        url = os.environ.get(url_key, "")
        email = os.environ.get(email_key, "")
        pwd = os.environ.get(pwd_key, "")

        if not url or not email or not pwd:
            print(f"  {tenant_name}: SKIP (missing credentials)")
            continue

        print(f"  {tenant_name}: {url}")
        token = owui_login(url, email, pwd)
        if not token:
            print(f"    Login FAILED")
            continue
        print(f"    Login OK")

        # Optimize models
        for model_id in sorted(all_model_ids):
            model = owui_get_model(url, token, model_id)
            if not model:
                print(f"    {model_id}: not found, skipping")
                continue

            updated, changes = optimize_model(model, model_id, dry_run=args.dry_run)

            if not changes:
                print(f"    {model_id}: no changes needed")
                continue

            total_changes += len(changes)
            for change in changes:
                print(f"    {model_id}: {change}")

            if not args.dry_run:
                ok, msg = owui_update_model(url, token, model_id, updated)
                status = "APPLIED" if ok else f"FAILED ({msg})"
                print(f"    {model_id}: {status}")

        # Delete deprecated models
        for model_id in MODELS_TO_DELETE:
            model = owui_get_model(url, token, model_id)
            if not model:
                print(f"    {model_id}: not found (already deleted)")
                continue
            print(f"    {model_id}: DELETE (inactive, deprecated)")
            if not args.dry_run:
                ok, msg = owui_delete_model(url, token, model_id)
                status = "DELETED" if ok else f"DELETE FAILED ({msg})"
                print(f"    {model_id}: {status}")
                if ok:
                    total_deleted += 1

        print()

    print(f"\nTotal changes: {total_changes}")
    print(f"Total deleted: {total_deleted}")
    if args.dry_run:
        print("(dry run — no changes applied)")

    # Generate recommendations report
    report_path = args.report or os.path.join(script_dir, "reports", "optimization-recommendations.md")
    generate_recommendations(report_path)
    print(f"\nRecommendations saved to: {report_path}")


def generate_recommendations(output_path):
    """Generate a Markdown report with optimization recommendations."""
    report = """# Model Optimization Report

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
| Dr. Claire Lacroix | `OpenAI.o1` | ~$60 | `OpenRouter.anthropic/claude-sonnet-4` | $15 | **75%** |
| Samantha R1 | `OpenAI.o3` | ~$40 | `OpenRouter.anthropic/claude-sonnet-4` | $15 | **63%** |

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
**Best option: `OpenRouter.anthropic/claude-sonnet-4`**
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
"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)


if __name__ == "__main__":
    main()
