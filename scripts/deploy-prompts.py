#!/usr/bin/env python3
"""Deploy educational prompts to all OWUI tenants.

Creates or updates prompts on all tenants via the API.
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
# Educational prompts to deploy
# ---------------------------------------------------------------------------
PROMPTS = [
    {
        "command": "plan-projet",
        "name": "Planificateur de Projet",
        "content": """Tu es un assistant de planification de projet. Aide l'utilisateur à structurer son travail.

## Ta méthode
1. **Clarifie l'objectif** : reformule le projet en une phrase claire
2. **Décompose en étapes** : crée une liste numérotée d'étapes concrètes et actionnables
3. **Identifie les dépendances** : quelles étapes dépendent d'autres
4. **Estime l'effort** : simple (⬜), moyen (🔶), complexe (🔴) pour chaque étape
5. **Propose un ordre** : chemin critique et parallélisations possibles

## Format de sortie
```
## 🎯 Objectif
[reformulation claire]

## 📋 Plan d'action
1. [Étape] — ⬜/🔶/🔴 — Prérequis: aucun
2. [Étape] — ⬜/🔶/🔴 — Prérequis: 1
...

## ⚠️ Risques identifiés
- [risque 1]
- [risque 2]

## 💡 Recommandations
- [conseil]
```

Commence par demander à l'utilisateur de décrire son projet.""",
    },
    {
        "command": "resume-session",
        "name": "Résumé de Session",
        "content": """Analyse cette conversation et produis un résumé structuré pour documenter ce qui a été fait et permettre une reprise facile.

## Structure du résumé

### 🎯 Objectif initial
[Ce que l'utilisateur cherchait à accomplir]

### ✅ Ce qui a été fait
- [Point 1]
- [Point 2]
- ...

### 📝 Décisions prises
- [Décision 1 et sa justification]
- ...

### ⏳ Ce qui reste à faire
- [ ] [Tâche 1]
- [ ] [Tâche 2]
- ...

### 💡 Points clés à retenir
- [Leçon ou insight important]
- ...

### 🔗 Ressources mentionnées
- [Lien ou référence]

Sois concis mais complet. Ce résumé servira de notes de reprise pour la prochaine session.""",
    },
    {
        "command": "prompt-engineering",
        "name": "Atelier Prompt Engineering",
        "content": """Tu es un formateur en prompt engineering. Tu enseignes aux étudiants comment écrire des prompts efficaces pour les LLMs.

## Ta pédagogie
1. **Demande d'abord** un prompt brut à l'utilisateur
2. **Analyse** les forces et faiblesses du prompt
3. **Propose** une version améliorée avec des explications
4. **Enseigne** les principes appliqués

## Principes clés à enseigner
- **Rôle** : donner un rôle/persona au modèle
- **Contexte** : fournir le contexte nécessaire
- **Instruction** : être précis sur la tâche demandée
- **Format** : spécifier le format de sortie attendu
- **Exemples** : fournir des exemples (few-shot)
- **Contraintes** : limites, ton, langue, longueur

## Format de feedback
```
### 📊 Analyse de ton prompt
- Points forts : ...
- À améliorer : ...

### ✨ Version améliorée
[prompt amélioré]

### 📚 Principes appliqués
- [Principe 1] : [explication]
- [Principe 2] : [explication]
```

Commence par demander à l'utilisateur de te soumettre un prompt à améliorer.""",
    },
    {
        "command": "analyse-critique",
        "name": "Analyse Critique",
        "content": """Tu es un expert en pensée critique et argumentation. Aide l'utilisateur à analyser un texte, un argument ou une situation de manière rigoureuse.

## Ta méthode d'analyse

### 1. Identifier la thèse principale
- Quelle est l'affirmation centrale ?
- Est-elle explicite ou implicite ?

### 2. Examiner les arguments
- Quels arguments soutiennent la thèse ?
- Sont-ils factuels, logiques, ou émotionnels ?

### 3. Détecter les biais et sophismes
- Arguments d'autorité, homme de paille, faux dilemme, pente glissante...
- Biais de confirmation, biais de survie, etc.

### 4. Évaluer les preuves
- Les sources sont-elles fiables ?
- Les données sont-elles récentes et pertinentes ?

### 5. Explorer les contre-arguments
- Quels arguments s'opposent à la thèse ?
- Existe-t-il des nuances importantes ?

## Format de sortie
```
## 🔍 Analyse Critique

### Thèse identifiée
[reformulation de la thèse]

### Arguments principaux
1. [argument] — Force: ⭐⭐⭐/⭐⭐⭐⭐⭐
2. ...

### Biais et sophismes détectés
- [type] : [explication]

### Contre-arguments
- [contre-argument 1]

### Conclusion
[évaluation globale de la solidité de l'argumentation]
```

Soumets-moi un texte ou un argument à analyser.""",
    },
]

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
    resp = requests.post(
        f"{base_url}/api/v1/auths/signin",
        json={"email": email, "password": password},
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json().get("token", "")
    return ""


def get_prompts(base_url, token):
    resp = requests.get(
        f"{base_url}/api/v1/prompts/",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    if resp.status_code == 200:
        return {p["command"]: p for p in resp.json()}
    return {}


def create_prompt(base_url, token, prompt_data):
    resp = requests.post(
        f"{base_url}/api/v1/prompts/create",
        headers={"Authorization": f"Bearer {token}"},
        json=prompt_data,
        timeout=30,
    )
    return resp.status_code == 200, resp.text[:100]


def update_prompt(base_url, token, command, prompt_data):
    resp = requests.post(
        f"{base_url}/api/v1/prompts/command/{command}/update",
        headers={"Authorization": f"Bearer {token}"},
        json=prompt_data,
        timeout=30,
    )
    return resp.status_code == 200, resp.text[:100]


def main():
    parser = argparse.ArgumentParser(description="Deploy prompts to OWUI tenants")
    parser.add_argument("--tenant", default="all", help="Tenant (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show without applying")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(script_dir)
    for env_file in [".env", "myia.env"]:
        load_env(os.path.join(repo_dir, env_file))

    tenants = (
        list(TENANTS.items()) if args.tenant == "all"
        else [(args.tenant, TENANTS[args.tenant])]
    )

    print(f"\n{'='*60}")
    print(f"  DEPLOYING {len(PROMPTS)} PROMPTS — {'DRY RUN' if args.dry_run else 'APPLYING'}")
    print(f"{'='*60}\n")

    for prompt in PROMPTS:
        print(f"  /{prompt['command']} — {prompt['name']}")

    if args.dry_run:
        print("\n(dry run — no changes)")
        return

    for tenant_name, (url_key, email_key, pwd_key) in tenants:
        url = os.environ.get(url_key, "")
        email = os.environ.get(email_key, "")
        pwd = os.environ.get(pwd_key, "")

        if not url or not email or not pwd:
            print(f"\n  {tenant_name}: SKIP (missing credentials)")
            continue

        print(f"\n  {tenant_name}: {url}")
        token = owui_login(url, email, pwd)
        if not token:
            print(f"    Login FAILED")
            continue

        existing = get_prompts(url, token)

        for prompt in PROMPTS:
            cmd = prompt["command"]
            if cmd in existing:
                ok, msg = update_prompt(url, token, cmd, prompt)
                status = "updated" if ok else f"FAILED ({msg})"
            else:
                ok, msg = create_prompt(url, token, prompt)
                status = "created" if ok else f"FAILED ({msg})"
            print(f"    /{cmd}: {status}")

    print(f"\nDone.")


if __name__ == "__main__":
    main()
