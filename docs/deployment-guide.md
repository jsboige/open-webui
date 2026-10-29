# Guide de Deploiement Multi-Tenant Open WebUI

Ce guide documente les procedures operationnelles pour gerer le deploiement multi-tenant Open WebUI sur l'infrastructure MyIA.

## Architecture

```
                           open-webui-shared (Docker network)
                    ┌─────────────────────────────────────────────┐
                    │                                             │
  ┌─────────────────┤  Shared Infrastructure                      │
  │ docker-compose-  │  ┌──────────┐ ┌──────┐ ┌───────┐          │
  │ infra.yaml       │  │PostgreSQL│ │ Tika │ │ Redis │          │
  │ (open-webui-     │  │  :5432   │ │:9917 │ │ :6351 │          │
  │  infra)          │  └──────────┘ └──────┘ └───────┘          │
  └─────────────────┤                                             │
                    │  Myia Sidecars                               │
  ┌─────────────────┤  ┌──────────┐ ┌────────┐ ┌─────┐ ┌───────┐│
  │ docker-compose-  │  │Pipelines │ │Kokoro  │ │Whis-│ │sk-    ││
  │ myia.yaml        │  │  :9099   │ │TTS:8880│ │per  │ │agent  ││
  │ (myia-open-webui)│  └──────────┘ └────────┘ │:8787│ │:8100  ││
  └─────────────────┤                           └─────┘ └───────┘│
                    │                                             │
                    │  Tenant Containers (1 each)                  │
  ┌─────────────────┤  ┌──────┐ ┌──────┐ ┌─────┐ ... ┌────────┐ │
  │ docker-compose-  │  │ myia │ │epita │ │ esg │     │pauwels │ │
  │ <tenant>.yaml    │  │:2090 │ │:3014 │ │:3011│     │ :3016  │ │
  └─────────────────┤  └──────┘ └──────┘ └─────┘     └────────┘ │
                    └─────────────────────────────────────────────┘
                                        │
                   ┌────────────────────┬┘
                   ▼                    ▼
           LAN Services          IIS Reverse Proxies
  ┌──────────────────────┐   ┌─────────────────────────┐
  │ Qdrant     (ai-01)   │   │ open-webui.myia.io      │
  │ Embedding  (po-2026) │   │ qdrant.myia.io:443      │
  │ SearXNG    (ai-01)   │   │ embeddings.myia.io      │
  │ SD Forge   (po-2023) │   │ skagents.myia.io        │
  │ Whisper    (po-2023) │   │ search.myia.io          │
  │ vLLM x2   (ai-01)   │   │ turbo.sd-forge.myia.io  │
  └──────────────────────┘   └─────────────────────────┘
```

### Ports par tenant

| Tenant    | Port | Redis DB | Database      |
|-----------|------|----------|---------------|
| myia      | 2090 | 0        | myia_db       |
| epf       | 3010 | 1        | epf_db        |
| esg       | 3011 | 4        | esg_db        |
| ece       | 3012 | 3        | ece_db        |
| epf-genai | 3013 | 2        | epf_genai_db  |
| epita     | 3014 | 5        | epita_db      |
| pauwels   | 3016 | 6        | pauwels_db    |

---

## Operations courantes

### Demarrer / arreter l'infrastructure

```bash
# Demarrer les services partages (PostgreSQL + Tika + Redis)
docker compose -p open-webui-infra -f docker-compose-infra.yaml up -d

# Demarrer myia avec sidecars (Pipelines, Kokoro TTS, Whisper STT, sk-agent)
docker compose -p myia-open-webui --env-file myia.env -f docker-compose-myia.yaml up -d

# Demarrer un tenant
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml up -d

# Arreter un tenant
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml down

# Logs d'un tenant
docker compose -p <tenant>-open-webui --env-file <tenant>.env -f docker-compose-<tenant>.yaml logs -f
```

### Verifier la sante des tenants

```bash
# Health check rapide (tous les tenants)
for port in 2090 3010 3011 3012 3013 3014 3016; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','FAIL'))" 2>/dev/null || echo "DOWN"
done
```

### Consulter les logs

```bash
# Logs d'un tenant specifique
docker logs <tenant>-open-webui-open-webui-1 --tail 100 -f

# Logs PostgreSQL
docker logs open-webui-postgres --tail 50

# Logs infrastructure
docker compose -p open-webui-infra -f docker-compose-infra.yaml logs --tail 50
```

---

## Montee de version

### Procedure (testee v0.8.3 -> v0.8.5)

**Prerequis** : Les `.env` de tous les tenants utilisent `WEBUI_DOCKER_TAG='cuda'` (tag flottant).

```bash
# 1. Backup PostgreSQL
docker exec open-webui-postgres pg_dumpall -U openwebui > backups/all_dbs_backup_$(date +%Y%m%d).sql

# 2. Pull la nouvelle image
docker pull ghcr.io/open-webui/open-webui:cuda

# 3. Upgrade myia d'abord (instance de reference)
docker compose -p myia-open-webui --env-file myia.env \
  -f docker-compose-myia.yaml up -d --force-recreate

# 4. Verifier myia
curl -s http://localhost:2090/health  # Doit retourner la nouvelle version

# 5. Upgrade les autres tenants
for tenant in epf epita esg ece pauwels; do
  docker compose -p ${tenant}-open-webui --env-file ${tenant}.env \
    -f docker-compose-${tenant}.yaml up -d --force-recreate
done
docker compose -p epf-genai-open-webui --env-file epf-genai.env \
  -f docker-compose-epf-genai.yaml up -d --force-recreate

# 6. Verifier tous les tenants
for port in 2090 3010 3011 3012 3013 3014 3016; do
  echo -n "Port $port: "
  curl -s http://localhost:$port/health | python3 -c "import sys,json; print(json.load(sys.stdin).get('version','FAIL'))" 2>/dev/null || echo "DOWN"
done
```

**Important** :
- `--force-recreate` est **obligatoire** apres un `docker pull` — `up -d` seul ne detecte pas le changement d'image
- `--force-recreate` est aussi requis apres modification des fichiers `.env`
- Toujours upgrader myia en premier, tester, puis les autres tenants

---

## Deployer un nouveau tenant

### 1. Creer la base de donnees

```bash
docker exec -i open-webui-postgres psql -U openwebui -d postgres \
  -c "CREATE DATABASE nouveau_tenant_db OWNER openwebui;"
```

### 2. Creer le fichier .env

Copier le template et remplir les valeurs :

```bash
cp tenant.env.example nouveau-tenant.env
```

Valeurs a modifier dans `nouveau-tenant.env` :
- `WEBUI_NAME` — Nom affiche dans l'UI
- `OPEN_WEBUI_PORT` — Port unique (ex: 3017)
- `DATABASE_URL` — Nom de la base (ex: `nouveau_tenant_db`)
- `WEBSOCKET_REDIS_URL` — Numero de DB Redis unique (ex: `redis://redis:6379/7`)
- `QDRANT_API_KEY` — Copier depuis un tenant existant
- `ADMIN_EMAIL` — Email de l'administrateur

### 3. Creer le fichier docker-compose

Copier un tenant existant comme base :

```bash
cp docker-compose-epita.yaml docker-compose-nouveau-tenant.yaml
```

Modifier :
- Le chemin du volume WSL (`\\wsl.localhost\Ubuntu\home\...`) pour pointer vers le repertoire de donnees du nouveau tenant
- Le port dans `ports:` correspond a `OPEN_WEBUI_PORT`

### 4. Creer le repertoire de donnees WSL

```bash
# Dans WSL
mkdir -p ~/NouveauTenant/open-webui
```

### 5. Demarrer le container

```bash
docker compose -p nouveau-tenant-open-webui --env-file nouveau-tenant.env \
  -f docker-compose-nouveau-tenant.yaml up -d
```

Le premier demarrage execute les migrations Alembic et cree les tables.

### 6. Se connecter et creer l'admin

Ouvrir `http://localhost:<port>` dans un navigateur. Le premier utilisateur devient automatiquement administrateur.

### 7. Cloner la configuration depuis myia

Ajouter les credentials du nouveau tenant dans `.env` :

```bash
# Ajouter dans .env (gitignored)
NOUVEAU_TENANT_URL='http://localhost:3017'
NOUVEAU_TENANT_EMAIL='admin@example.com'
NOUVEAU_TENANT_PASSWORD='...'
```

Puis ajouter le tenant dans `scripts/configure-tenant.py` (dictionnaire `TENANTS`), et executer :

```bash
# Via Docker (Python pas en PATH sur Windows)
docker run --rm --network host \
  -v "$(pwd)/scripts:/app/scripts:ro" \
  -v "$(pwd)/.env:/app/.env:ro" \
  python:3.11-slim \
  python /app/scripts/configure-tenant.py --tenants nouveau-tenant
```

### 8. Copier les Knowledge Bases

```bash
docker run --rm --network host \
  -v "$(pwd)/scripts:/app/scripts:ro" \
  -v "$(pwd)/.env:/app/.env:ro" \
  python:3.11-slim \
  python /app/scripts/shallow-copy-kbs.py --target nouveau-tenant
```

### 9. Creer les symlinks pour les fichiers KB

Les fichiers PDF sont stockes dans le volume myia. Chaque tenant a besoin de symlinks individuels :

```bash
# Dans WSL, pour chaque fichier dans le repertoire uploads de myia
# Generer la liste des symlinks necessaires :
docker run --rm --network host \
  -v "$(pwd)/scripts:/app/scripts:ro" \
  -v "$(pwd)/.env:/app/.env:ro" \
  python:3.11-slim \
  python /app/scripts/shallow-copy-kbs.py --target nouveau-tenant --show-symlinks

# Puis creer les symlinks dans le repertoire uploads du nouveau tenant
```

### 10. Installer les fonctions communautaires

```bash
docker run --rm --network host \
  -v "$(pwd)/scripts:/app/scripts:ro" \
  -v "$(pwd)/.env:/app/.env:ro" \
  python:3.11-slim \
  python /app/scripts/install-community-functions.py --tenant nouveau-tenant
```

---

## Cloner la configuration

Le script `configure-tenant.py` clone 6 sections de configuration depuis l'instance myia de reference vers les tenants cibles :

| Section | Source API | Description |
|---------|-----------|-------------|
| OpenAI Connections | `/openai/config` | Toutes les connexions LLM (OpenAI, OpenRouter, Groq, etc.) |
| Embedding | `/api/v1/retrieval/embedding` | Service d'embedding (Qwen3 @ embeddings.myia.io) |
| Audio | `/api/v1/audio/config` | TTS (Kokoro) + STT (Whisper) |
| Image Generation | `/api/v1/images/config` | SD Forge (turbo.sd-forge.myia.io) |
| RAG & Web Search | `/api/v1/retrieval/config` | Qdrant + SearXNG |
| Tool Servers | `/api/v1/configs/tool_servers` | MCP Tool Servers (sk-agent) |

### Usage

```bash
# Cloner toutes les sections vers tous les tenants
python scripts/configure-tenant.py

# Dry run (affiche le plan sans executer)
python scripts/configure-tenant.py --dry-run

# Un seul tenant
python scripts/configure-tenant.py --tenants epita

# Sections specifiques seulement
python scripts/configure-tenant.py --sections "Tool Servers" "Audio"
```

**Note** : le script lit les credentials depuis `.env` (gitignored). Variables requises :
- `MYIA_URL`, `MYIA_EMAIL`, `MYIA_PASSWORD` — Instance de reference
- `{TENANT}_URL`, `{TENANT}_EMAIL`, `{TENANT}_PASSWORD` — Pour chaque tenant

---

## Backup et restauration

### Backup PostgreSQL

```bash
# Toutes les bases
docker exec open-webui-postgres pg_dumpall -U openwebui \
  > backups/all_dbs_$(date +%Y%m%d).sql

# Une base specifique
docker exec open-webui-postgres pg_dump -U openwebui myia_db \
  > backups/myia_db_$(date +%Y%m%d).sql
```

### Restaurer une base

```bash
# Restaurer une base specifique
docker exec -i open-webui-postgres psql -U openwebui -d myia_db \
  < backups/myia_db_20260223.sql

# Restaurer toutes les bases (attention: ecrase tout)
docker exec -i open-webui-postgres psql -U openwebui -d postgres \
  < backups/all_dbs_20260223.sql
```

### Backup Qdrant

Les snapshots Qdrant couvrent tous les tenants (collection unique `open-webui_knowledge`).

```bash
# Creer un snapshot via l'API Qdrant
curl -X POST "https://qdrant.myia.io:443/collections/open-webui_knowledge/snapshots"

# Lister les snapshots
curl "https://qdrant.myia.io:443/collections/open-webui_knowledge/snapshots"
```

---

## Depannage

### Le container ne demarre pas

```bash
# Verifier les logs
docker logs <tenant>-open-webui-open-webui-1 --tail 200

# Causes frequentes :
# - Port deja utilise : changer OPEN_WEBUI_PORT dans .env
# - PostgreSQL non accessible : verifier docker-compose-infra.yaml est up
# - Volume WSL introuvable : verifier le chemin \\wsl.localhost\...
```

### Erreur "relation does not exist"

La base n'a pas ete initialisee. Le premier demarrage du container cree les tables via Alembic. Verifier que le container a pu demarrer au moins une fois avec la bonne `DATABASE_URL`.

### Les modeles ne s'affichent pas

Les connexions LLM sont en base de donnees. Executer `configure-tenant.py` pour cloner la configuration depuis myia :

```bash
python scripts/configure-tenant.py --tenants <tenant> --sections "OpenAI Connections"
```

### Les Knowledge Bases sont vides

1. Verifier que `shallow-copy-kbs.py` a ete execute (copie les metadonnees PG)
2. Verifier que les symlinks WSL existent dans le repertoire uploads du tenant
3. Verifier que Qdrant est accessible (`QDRANT_URI=https://qdrant.myia.io:443`)

### Rate limiting sur l'API d'auth

L'endpoint `/api/v1/auths/signin` est rate-limite. Attendre 2+ minutes entre les tentatives. Les scripts de deploiement doivent etre executes en sequence, pas en parallele.

### Les changements .env ne prennent pas effet

`docker compose up -d` ne detecte PAS les changements de fichier `.env`. Utiliser `--force-recreate` :

```bash
docker compose -p <tenant>-open-webui --env-file <tenant>.env \
  -f docker-compose-<tenant>.yaml up -d --force-recreate
```

### Redis lock timeout

Si les WebSockets se deconnectent regulierement, verifier que `WEBSOCKET_REDIS_LOCK_TIMEOUT=300` est configure (la valeur par defaut de 60s est trop basse, doit etre > `SESSION_POOL_TIMEOUT=120s`).

### sk-agent ne repond pas

1. Verifier que le container tourne : `docker ps | grep sk-agent`
2. Tester directement : `curl https://skagents.myia.io/mcp` (doit repondre, pas timeout)
3. Le vLLM peut avoir un `EngineDeadError` apres inactivite — l'API `/v1/models` repond OK mais les completions bloquent. Attendre ~3 min pour la recuperation automatique

### Tika : healthcheck echoue

L'image Tika a `wget`, PAS `curl`. Le healthcheck doit utiliser `wget --spider -q`.

---

## Scripts de deploiement

| Script | Usage |
|--------|-------|
| `scripts/configure-tenant.py` | Cloner la config des 6 sections depuis myia vers les tenants |
| `scripts/shallow-copy-kbs.py` | Copier les metadonnees KB entre bases PostgreSQL (memes UUIDs Qdrant) |
| `scripts/install-community-functions.py` | Installer/mettre a jour les 8 fonctions communautaires |
| `scripts/preflight-cleanup.py` | Nettoyer fonctions cassees, spam, filterIds invalides |
| `scripts/migrate-sqlite-to-postgres.py` | Migration SQLite vers PostgreSQL (usage initial uniquement) |
| `scripts/bulk-kb-upload.py` | Upload de PDFs vers une KB via l'API |
| `scripts/create-thematic-kbs.py` | Creer des KBs thematiques depuis les sous-repertoires Bibliographie IA |

### Execution des scripts Python sur Windows

Python n'est pas dans le PATH du sandbox Windows. Utiliser un container Docker ephemere :

```bash
docker run --rm --network host \
  -v "$(pwd)/scripts:/app/scripts:ro" \
  -v "$(pwd)/.env:/app/.env:ro" \
  python:3.11-slim \
  python /app/scripts/<script.py> [args]
```

---

## Services externes (LAN)

Tous les services sont heberges sur des machines physiques du LAN, exposes via des reverse proxies IIS HTTPS.

| Service | URL | Machine | GPU |
|---------|-----|---------|-----|
| Qdrant | `https://qdrant.myia.io:443` | myia-ai-01 | - |
| Embedding | `https://embeddings.myia.io/v1` | myia-po-2026 | RTX 3080 16GB |
| SearXNG | `https://search.myia.io` | myia-ai-01 | - |
| SD Forge | `https://turbo.sd-forge.myia.io` | myia-po-2023 | RTX 3090+3080 |
| Whisper STT | `https://whisper-webui.myia.io` | myia-po-2023 | RTX 3090 |
| sk-agent | `https://skagents.myia.io/mcp` | myia-ai-01 | - |
| vLLM mini | `http://host.docker.internal:5001` | myia-ai-01 | RTX 4090 (GPU 2) |
| vLLM medium | `http://host.docker.internal:5002` | myia-ai-01 | RTX 4090 (GPU 0+1) |

**Gotcha Qdrant** : le client Python qdrant-client ajoute automatiquement `:6333` au port. Toujours specifier `https://qdrant.myia.io:443` dans `QDRANT_URI`.
