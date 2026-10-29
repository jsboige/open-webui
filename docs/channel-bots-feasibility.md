# Étude de faisabilité : Bots dans les Channels OWUI

**Issue**: [#8 — Intégration de bots dans les Channels OWUI](https://github.com/jsboige/open-webui/issues/8)
**Date**: 2026-03-03
**Version OWUI**: v0.8.7
**Statut**: Phase 1 — Étude de faisabilité (complétée)

---

## 1. Résumé exécutif

L'intégration de bots dans les Channels OWUI est **techniquement faisable** avec deux approches complémentaires :

| Approche | Complexité | Cas d'usage |
|----------|-----------|-------------|
| **@mention native** | Aucune (built-in) | Bot conversationnel simple, Q&A |
| **Bot externe Socket.IO** | Moyenne (~200 lignes) | Logique custom, outils, workflow |

**Recommandation** : Commencer par la @mention native (zéro développement), puis évaluer si un bot externe apporte une valeur ajoutée pour des cas spécifiques.

---

## 2. Architecture OWUI Channels (v0.8.7)

### 2.1 Socket.IO Protocol

| Aspect | Détail |
|--------|--------|
| **Chemin** | `/ws/socket.io` |
| **Transports** | WebSocket (préféré) + polling fallback |
| **Auth** | JWT token via `auth: { token }` à la connexion |
| **Scaling** | Redis PubSub (optionnel, pour multi-serveur) |
| **Ping** | Configurable (`WEBSOCKET_SERVER_PING_INTERVAL`) |

### 2.2 Événements Socket.IO (`events:channel`)

> **Breaking change v0.6.33** : L'événement a été renommé de `channel-events` à `events:channel`.

#### Client → Serveur

| Événement | Payload | Usage |
|-----------|---------|-------|
| `user-join` | `{ auth: { token } }` | Authentification + join des rooms |
| `join-channels` | `{ auth: { token } }` | Re-join après reconnexion |
| `events:channel` | `{ channel_id, data: { type: "typing" } }` | Indicateur de frappe |
| `events:channel` | `{ channel_id, data: { type: "last_read_at" } }` | Marquer comme lu |

#### Serveur → Client

| Type d'événement | Quand | Payload clé |
|-----------------|-------|-------------|
| `message` | Nouveau message | `data.data` = message complet |
| `message:update` | Message modifié | `data.data` = message mis à jour |
| `message:delete` | Message supprimé | `data.data.id` = ID du message |
| `message:reply` | Réponse en thread | `data.data` = message parent mis à jour |
| `message:reaction:add` | Réaction ajoutée | `data.data` = message + réactions |
| `message:reaction:remove` | Réaction retirée | Idem |
| `typing` | Quelqu'un tape | `data.data.typing` = bool |
| `channel:created` | Nouveau channel | Métadonnées du channel |

#### Structure complète d'un événement

```typescript
{
  channel_id: string;
  message_id: string | null;  // null = message principal, sinon = thread
  data: {
    type: "message" | "message:update" | "typing" | ...;
    data: {
      id: string;
      user_id: string;
      channel_id: string;
      content: string;
      meta: { model_id?: string; model_name?: string; done?: boolean } | null;
      parent_id: string | null;
      reply_to_id: string | null;
      created_at: number;
      updated_at: number;
      reactions: object[];
      reply_count: number;
      // ...
    }
  };
  user: { id: string; name: string };
  channel: { id: string; name: string; ... };
}
```

### 2.3 Format des @mentions

```
<@{TYPE}:{ID}|{LABEL}>
```

| Type | Signification | Exemple |
|------|--------------|---------|
| `U` | Utilisateur | `<@U:user-123\|Alice>` |
| `M` | Modèle | `<@M:expert-analyste\|Expert Analyste>` |
| `C` | Channel | `<@C:chan-456\|general>` |

**Regex backend** (`utils/channels.py`) : `<@([A-Z]):([^|>]+)`

### 2.4 Authentification

| Méthode | REST API | Socket.IO |
|---------|----------|-----------|
| JWT token | ✓ (`Bearer {jwt}`) | ✓ (`auth: { token }`) |
| API key (`sk-...`) | ✓ (`Bearer {sk-...}`) | **✗ Non supporté** |

**Implication** : Un bot externe doit obtenir un JWT via `POST /api/v1/auths/signin` — les API keys ne fonctionnent pas pour Socket.IO.

---

## 3. Approche 1 : @mention native (built-in)

### 3.1 Mécanisme

Quand un utilisateur poste un message contenant `<@M:model-id|Label>` dans un channel :

1. `model_response_handler()` (`channels.py:1031`) détecte la mention
2. Crée un message vide avec `meta.model_id`
3. Assemble le contexte de thread (historique des réponses)
4. Appelle `generate_chat_completion()` avec le modèle mentionné
5. Met à jour le message avec la réponse du modèle

### 3.2 Avantages

- **Zéro développement** — fonctionne immédiatement
- **Contexte automatique** — l'historique du thread est inclus
- **Intégré à l'UI** — mentions autocomplete, avatars, threads
- **Tous les modèles** — fonctionne avec n'importe quel modèle configuré
- **Multi-tenant** — chaque tenant a ses propres modèles

### 3.3 Limites

- **Réactif uniquement** — le modèle ne peut pas initier de conversation
- **Pas de logique custom** — pas d'accès aux outils, APIs externes, workflows
- **Pas de mémoire persistante** — le contexte se limite au thread actuel
- **Pas de filtrage de messages** — ne peut pas réagir sélectivement (modération, FAQ)
- **Pas de tâches planifiées** — pas d'annonces automatiques, rappels

### 3.4 Cas d'usage couverts

| Cas | Couvert ? | Comment |
|-----|-----------|---------|
| Bot tuteur par TP | ✓ | `@expert-analyste` avec system prompt spécialisé |
| Q&A sur les KBs | **Partiellement** | Le modèle n'a pas accès aux KBs dans les channels |
| Modération | ✗ | Ne peut pas intercepter tous les messages |
| Annonces | ✗ | Ne peut pas poster proactivement |
| Exercices interactifs | ✗ | Pas d'accès à Open Terminal via channels |

### 3.5 Test vérifié

```
✓ POST message avec <@M:expert-analyste|...> → modèle invoqué automatiquement
✓ Réponse créée en thread (message:reply)
✓ meta.model_id et meta.model_name présents dans les événements
```

---

## 4. Approche 2 : Bot externe Socket.IO

### 4.1 Architecture

```
┌─────────────────┐     Socket.IO      ┌──────────────┐
│   Bot Python     │◄──events:channel──│   OWUI        │
│  (container)     │                    │  (v0.8.7)     │
│                  │──POST /api/v1/──►│              │
│  - Écoute msgs   │   channels/msg     │              │
│  - Logique custom│                    │              │
│  - Outils (API)  │                    │              │
└─────────────────┘                    └──────────────┘
```

### 4.2 Flux de messages

1. Bot se connecte via Socket.IO avec JWT
2. Serveur join le bot aux rooms `channel:{id}` via `user-join`
3. Quand un message arrive, bot reçoit `events:channel` type `message`
4. Bot applique sa logique (filtrage, NLP, outils)
5. Bot répond via REST `POST /api/v1/channels/{id}/messages/post`
6. (Optionnel) Bot envoie indicateur de frappe via Socket.IO

### 4.3 Avantages

- **Logique arbitraire** — peut implémenter n'importe quelle logique
- **Proactif** — peut poster sans être mentionné (annonces, rappels)
- **Accès aux outils** — peut appeler des APIs (Qdrant, SearXNG, Tika, Open Terminal)
- **Filtrage intelligent** — peut réagir sélectivement (keywords, sentiment, regex)
- **Multi-channel** — peut écouter et répondre sur plusieurs channels
- **Mémoire** — peut maintenir un état persistant (base de données, fichiers)

### 4.4 Inconvénients

- **Maintenance** — code custom à maintenir, tests, déploiement Docker
- **Authentification** — nécessite un compte utilisateur dédié + JWT (pas d'API key pour Socket.IO)
- **Stabilité** — Socket.IO peut se déconnecter (nécessite reconnexion automatique)
- **Sécurité** — le bot a les permissions complètes de son compte utilisateur
- **Repo upstream abandonné** — `open-webui/bot` non maintenu, event names déjà cassés

### 4.5 Modifications nécessaires (vs repo open-webui/bot)

| Modification | Ancien | Nouveau |
|-------------|--------|---------|
| Event name | `channel-events` | `events:channel` |
| Callback | `async def join_callback(data)` | `async def join_callback(*args)` |
| Socket path | (implicite) | `/ws/socket.io` |
| SSL | Non géré | `ssl_verify=False` pour self-signed |

### 4.6 Cas d'usage supplémentaires

| Cas | Faisabilité | Effort |
|-----|-------------|--------|
| Bot d'accueil | Haute | ~50 lignes |
| FAQ auto-répondeur (RAG) | Haute | ~100 lignes + API Qdrant |
| Bot modérateur | Moyenne | ~150 lignes + logique NLP |
| Bot d'annonces | Haute | ~80 lignes + cron |
| Bot d'exercices (Terminal) | Moyenne | ~200 lignes + API Terminal |
| Bot admin multi-tenant | Basse | ~300 lignes + multi-connexion |

### 4.7 Tests vérifiés

```
✓ JWT auth via POST /api/v1/auths/signin
✓ Socket.IO connect (WebSocket transport, /ws/socket.io)
✓ user-join → retourne {id, name}, join les rooms channels
✓ events:channel reçu pour les messages postés
✓ POST /api/v1/channels/{id}/messages/post → message affiché dans le channel
✓ Payload complet: id, content, user, meta, reactions, reply_count, etc.
```

---

## 5. Comparaison : @mention vs Bot externe

| Critère | @mention native | Bot externe |
|---------|----------------|-------------|
| **Effort** | 0 | Moyen (~200-400 LOC) |
| **Maintenance** | 0 | Faible-moyen |
| **Réactivité** | Sur mention uniquement | Sur tout message |
| **Proactivité** | ✗ | ✓ (annonces, rappels) |
| **Outils** | ✗ (pas de tools dans channels) | ✓ (APIs, Terminal, etc.) |
| **KBs/RAG** | ✗ (pas de RAG dans channels) | ✓ (via API) |
| **Multi-tenant** | ✓ (automatique) | Complexe (1 connexion/tenant) |
| **Avatars** | ✓ (avatar du modèle) | ✓ (avatar du compte bot) |
| **Threading** | ✓ (automatique) | Manuel |
| **Contexte** | Thread historique | Custom (peut être plus riche) |

### 5.1 Quand utiliser quoi ?

**Utiliser @mention native si** :
- L'interaction est conversationnelle simple (Q&A)
- Le modèle a un system prompt suffisant
- Pas besoin d'outils externes
- L'utilisateur déclenche explicitement le bot

**Utiliser un bot externe si** :
- Le bot doit être proactif (accueil, annonces, modération)
- Le bot doit accéder à des APIs (Qdrant pour RAG, Terminal pour exécution)
- Le bot doit réagir à des patterns (keywords, sentiment)
- Le bot doit maintenir un état entre conversations

---

## 6. État des Channels sur notre déploiement

| Tenant | Channels | Messages | Commentaire |
|--------|----------|----------|-------------|
| myia | 2 (`general`, `ai-playground`) | 3 | Seuls messages de test |

Les channels sont sous-utilisés actuellement. Un bot pourrait stimuler l'adoption.

---

## 7. Architecture proposée (Phase 2)

### 7.1 Bot minimal viable (MVP)

```
docker-compose-myia.yaml
├── myia-channel-bot        # Container Python
│   ├── Connexion Socket.IO au tenant myia
│   ├── Écoute events:channel
│   ├── Logique: accueil + FAQ (RAG via API Qdrant)
│   └── Réponse via REST API
```

### 7.2 Bot multi-tenant (Phase 3)

```
docker-compose-bots.yaml
├── channel-bot-myia
├── channel-bot-epf
├── channel-bot-epf-genai
├── channel-bot-ece
├── channel-bot-esg
├── channel-bot-epita
└── channel-bot-pauwels
```

Ou un seul container multi-connexion avec config par tenant.

### 7.3 Stack technique recommandé

| Composant | Choix | Raison |
|-----------|-------|--------|
| Language | Python 3.11+ | Cohérent avec OWUI backend |
| Socket.IO | `python-socketio[asyncio]` 5.x | Déjà installé sur la machine |
| HTTP | `aiohttp` ou `httpx` | Appels REST asynchrones |
| Config | `.env` par tenant | Cohérent avec l'infra existante |
| Docker | Python 3.11-slim | Léger (~50MB) |

---

## 8. Risques identifiés

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| Socket.IO déconnexion | Moyen | Moyenne | Reconnexion auto avec backoff exponentiel |
| Repo upstream abandonné | Faible | Certaine | Notre code est indépendant (~200 LOC) |
| Boucle infinie (bot répond à bot) | Élevé | Moyenne | Filtrer `user_id == bot_id` + `meta.model_id` |
| Permissions trop larges | Moyen | Certaine | Compte dédié avec rôle "user" (pas admin) |
| Rate limiting API | Faible | Faible | Respecter les limites, queue de messages |
| vLLM down | Moyen | Faible | Fallback vers modèle cloud (GPT-4.1-mini) |

---

## 9. Prochaines étapes

### Phase 2 : Prototype (estimé ~2-3h)
1. Créer un bot Python minimal fonctionnel sur v0.8.7
2. Implémenter le cas "FAQ auto-répondeur" (RAG via API OWUI)
3. Dockeriser et tester sur le tenant myia
4. Valider la reconnexion automatique

### Phase 3 : Déploiement (estimé ~2-3h, si Phase 2 concluante)
1. Architecture multi-tenant
2. Intégration docker-compose
3. Configuration par tenant
4. Monitoring

---

## 10. Conclusion

La fonctionnalité de bots dans les Channels est **faisable et prometteuse**. Le mécanisme @mention natif couvre déjà les cas conversationnels simples sans aucun développement. Pour les cas plus avancés (accueil, FAQ RAG, modération), un bot externe Socket.IO de ~200-400 lignes est suffisant.

**Verdict** : ✅ Faisable — recommandation de passer en Phase 2 avec un bot FAQ/accueil minimal.
