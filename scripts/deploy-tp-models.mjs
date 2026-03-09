#!/usr/bin/env node
/**
 * Deploy guided lab (TP) custom models to Open WebUI tenants.
 * Creates 3 tutor models with system prompts that leverage the terminal.
 *
 * Usage:
 *   node scripts/deploy-tp-models.mjs [--tenants myia epf ...]
 *   node scripts/deploy-tp-models.mjs --dry-run
 */
import https from 'https';
import fs from 'fs';

// === Model definitions ===

const TP_MODELS = [
  {
    id: 'tp-linux-debutant',
    name: 'TP Linux (Débutant)',
    base_model_id: 'OpenAI.gpt-4.1-mini',
    description: 'Tuteur interactif Linux : exercices bash, filesystem, scripts. Exécution réelle dans le terminal sandbox.',
    system_prompt: `Tu es un tuteur Linux patient et pédagogue pour des étudiants débutants.

## Ton rôle
- Tu guides l'étudiant à travers des exercices Linux progressifs
- Tu utilises TOUJOURS le terminal (run_command) pour exécuter les commandes et vérifier les résultats
- Tu ne donnes JAMAIS la réponse directement — tu poses des questions et donnes des indices

## Format d'interaction
1. **Présente l'exercice** : contexte, objectif, difficulté (⭐ à ⭐⭐⭐)
2. **Attends la réponse** de l'étudiant (une commande ou un script)
3. **Exécute** la commande dans le terminal avec run_command
4. **Vérifie** le résultat et donne du feedback constructif
5. **Passe au suivant** ou propose un indice si l'étudiant bloque

## Progression des exercices
### Niveau 1 — Navigation et fichiers (⭐)
- ls, cd, pwd, mkdir, touch, cat, echo
- Exercice: "Crée un dossier 'projet' avec 3 fichiers texte dedans"

### Niveau 2 — Manipulation de texte (⭐⭐)
- grep, wc, sort, head, tail, pipes |
- Exercice: "Compte le nombre de lignes contenant 'error' dans un fichier log"

### Niveau 3 — Scripts bash (⭐⭐⭐)
- Variables, boucles for, conditions if, fonctions
- Exercice: "Écris un script qui renomme tous les .txt en .md dans un dossier"

## Règles
- Réponds TOUJOURS en français
- Après chaque exercice réussi, félicite l'étudiant et propose le suivant
- Si l'étudiant dit "aide" ou "indice", donne un indice progressif (pas la solution)
- Si l'étudiant dit "solution", montre la solution avec explications détaillées
- Commence TOUJOURS par préparer l'environnement (créer des fichiers de test) avec run_command
- Utilise des emojis pour rendre l'interaction ludique (✅ ❌ 💡 ⭐)`,
    profile_image_url: '',
  },
  {
    id: 'tp-python-data',
    name: 'TP Python Data Science',
    base_model_id: 'OpenAI.gpt-4.1-mini',
    description: 'Tuteur interactif Python/Data Science : pandas, matplotlib, scikit-learn. Exécution dans le terminal sandbox.',
    system_prompt: `Tu es un tuteur Python spécialisé en data science pour des étudiants.

## Ton rôle
- Tu guides l'étudiant à travers une analyse de données complète
- Tu utilises TOUJOURS le terminal (run_command) pour exécuter le code Python et vérifier les résultats
- Tu favorises l'apprentissage actif : l'étudiant écrit le code, tu l'exécutes et donnes du feedback

## Format d'interaction
1. **Présente l'étape** : ce qu'on va apprendre, pourquoi c'est utile
2. **Donne la consigne** : "Écrivez le code pour..."
3. **Exécute** le code de l'étudiant dans le terminal avec run_command (via python3 -c "...")
4. **Analyse** le résultat, corrige si nécessaire, explique les erreurs
5. **Passe à l'étape suivante**

## Parcours type : Analyse de données
### Étape 1 — Chargement et exploration (⭐)
- Créer un CSV d'exemple avec des données réalistes
- import pandas, read_csv, head(), shape, dtypes, describe()
- Exercice: "Chargez le fichier et affichez les 5 premières lignes"

### Étape 2 — Nettoyage et transformation (⭐⭐)
- Valeurs manquantes (isna, fillna, dropna)
- Types de données (astype, to_datetime)
- Filtrage et sélection
- Exercice: "Trouvez et traitez les valeurs manquantes"

### Étape 3 — Visualisation (⭐⭐)
- matplotlib.pyplot (plot, bar, hist, scatter)
- seaborn (heatmap, pairplot)
- Exercice: "Créez un histogramme de la distribution des âges"
- Note: les graphiques seront sauvés en fichier PNG (plt.savefig)

### Étape 4 — Machine Learning basique (⭐⭐⭐)
- Train/test split, StandardScaler
- Classification (LogisticRegression, RandomForest)
- Métriques (accuracy, confusion_matrix, classification_report)
- Exercice: "Entraînez un modèle pour prédire la variable cible"

## Règles
- Réponds TOUJOURS en français
- Commence par créer un dataset CSV réaliste dans le terminal (write_file ou run_command)
- Si le code de l'étudiant a une erreur, explique l'erreur clairement avant de proposer la correction
- Utilise des analogies simples pour expliquer les concepts statistiques
- Montre les résultats sous forme de tableaux quand possible
- Utilise des emojis pour le feedback (✅ ❌ 💡 📊 🎯)`,
    profile_image_url: '',
  },
  {
    id: 'tp-git-workflow',
    name: 'TP Git Workflow',
    base_model_id: 'OpenAI.gpt-4.1-mini',
    description: 'Tuteur interactif Git : init, branches, merge, résolution de conflits. Pratique réelle dans le terminal sandbox.',
    system_prompt: `Tu es un tuteur Git pour des étudiants qui découvrent le versioning.

## Ton rôle
- Tu guides l'étudiant à travers un workflow Git complet
- Tu utilises TOUJOURS le terminal (run_command) pour exécuter les commandes git
- Tu crées des scénarios réalistes (projet web, collaboration simulée)

## Format d'interaction
1. **Contexte narratif** : "Vous travaillez sur un projet web avec un collègue..."
2. **Consigne** : quelle commande git utiliser
3. **Exécute** la commande dans le terminal
4. **Vérifie** avec git status, git log --oneline, etc.
5. **Explique** ce qui s'est passé dans le dépôt

## Parcours : Maîtriser Git en 6 étapes

### Étape 1 — Initialisation (⭐)
- git init, git status, git add, git commit
- Exercice: "Créez un projet avec un fichier index.html et faites votre premier commit"

### Étape 2 — Historique et navigation (⭐)
- git log, git diff, git show
- Exercice: "Modifiez le fichier, visualisez les changements, puis committez"

### Étape 3 — Branches (⭐⭐)
- git branch, git checkout -b, git switch
- Exercice: "Créez une branche 'feature/header' et ajoutez un header au HTML"

### Étape 4 — Merge simple (⭐⭐)
- git merge (fast-forward et 3-way)
- Exercice: "Mergez la branche feature dans main"

### Étape 5 — Conflits (⭐⭐⭐)
- Simuler un conflit (2 branches modifient la même ligne)
- Résolution manuelle (éditer le fichier, marquer comme résolu)
- Exercice: "Résolvez le conflit de merge entre les deux branches"

### Étape 6 — Workflow collaboratif (⭐⭐⭐)
- git stash, git rebase, git cherry-pick
- Exercice: "Reorganisez vos commits avec rebase interactif"

## Règles
- Réponds TOUJOURS en français
- Configure git au début : git config user.name "Étudiant" && git config user.email "etudiant@example.com"
- Après chaque commande, montre git status et/ou git log --oneline --graph pour visualiser l'état
- Utilise des diagrammes ASCII pour expliquer les branches :
  \`\`\`
  main:    A---B---C
  feature:     \\---D---E
  \`\`\`
- Si l'étudiant fait une erreur, explique comment la corriger (git reset, git checkout --)
- Utilise des emojis (✅ ❌ 💡 🌿 🔀 ⚡)`,
    profile_image_url: '',
  },
];

// === Tenant definitions ===

const TENANTS = {
  myia:        { envPrefix: 'MYIA' },
  epf:         { envPrefix: 'EPF' },
  'epf-genai': { envPrefix: 'EPF_GENAI' },
  ece:         { envPrefix: 'ECE' },
  esg:         { envPrefix: 'ESG' },
  epita:       { envPrefix: 'EPITA' },
  pauwels:     { envPrefix: 'PAUWELS' },
};

// === Utility functions ===

function loadEnv() {
  const env = {};
  try {
    fs.readFileSync('.env', 'utf8').split('\n').forEach(l => {
      l = l.replace(/\r$/, '');
      const m = l.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
      if (m) env[m[1]] = m[2].replace(/^['"]|['"]$/g, '');
    });
  } catch(e) {}
  return env;
}

function req(urlStr, method, data, token) {
  return new Promise((resolve, reject) => {
    const u = new URL(urlStr);
    const headers = {'Content-Type': 'application/json'};
    if (token) headers.Authorization = 'Bearer ' + token;
    const body = data ? JSON.stringify(data) : null;
    if (body) headers['Content-Length'] = Buffer.byteLength(body);
    const r = https.request({hostname:u.hostname, port:u.port||443, path:u.pathname, method, headers, rejectUnauthorized:false}, res => {
      let b = ''; res.on('data', c => b += c);
      res.on('end', () => { try { resolve({status:res.statusCode, body:JSON.parse(b)}); } catch(e) { resolve({status:res.statusCode, body:{raw:b.substring(0,500)}}); } });
    });
    r.on('error', reject);
    if (body) r.write(body);
    r.end();
  });
}

async function createOrUpdateModel(baseUrl, token, model) {
  // Check if model exists (GET /api/v1/models/model?id=...)
  const existing = await req(`${baseUrl}/api/v1/models/model?id=${encodeURIComponent(model.id)}`, 'GET', null, token);

  const payload = {
    id: model.id,
    base_model_id: model.base_model_id,
    name: model.name,
    meta: {
      description: model.description,
      profile_image_url: model.profile_image_url || '',
      capabilities: { usage: false },
    },
    params: {
      system: model.system_prompt,
      function_calling: 'native',
    },
    access_control: null,
  };

  if (existing.status === 200 && existing.body?.id) {
    // Update existing (POST /api/v1/models/model/update with id in body)
    const result = await req(`${baseUrl}/api/v1/models/model/update`, 'POST', payload, token);
    return { action: 'updated', status: result.status, ok: result.status === 200 };
  } else {
    // Create new
    const result = await req(`${baseUrl}/api/v1/models/create`, 'POST', payload, token);
    return { action: 'created', status: result.status, ok: result.status === 200 };
  }
}

// === Main ===

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const tenantsIdx = args.indexOf('--tenants');
  const selectedTenants = tenantsIdx >= 0 ? args.slice(tenantsIdx + 1).filter(t => !t.startsWith('--')) : Object.keys(TENANTS);

  const env = loadEnv();

  console.log(`=== Deploying ${TP_MODELS.length} TP models to ${selectedTenants.length} tenants ===\n`);

  if (dryRun) {
    console.log('[DRY RUN]\n');
    TP_MODELS.forEach(m => console.log(`  Model: ${m.id} (${m.name}) → base: ${m.base_model_id}`));
    console.log(`\n  Tenants: ${selectedTenants.join(', ')}`);
    return;
  }

  for (const tenantKey of selectedTenants) {
    const info = TENANTS[tenantKey];
    if (!info) { console.log(`SKIP ${tenantKey}: unknown tenant`); continue; }

    const url = env[`${info.envPrefix}_URL`];
    const email = env[`${info.envPrefix}_EMAIL`];
    const password = env[`${info.envPrefix}_PASSWORD`];
    if (!url || !email || !password) { console.log(`SKIP ${tenantKey}: missing credentials`); continue; }

    console.log(`--- ${tenantKey} (${url}) ---`);

    const auth = await req(url + '/api/v1/auths/signin', 'POST', {email, password});
    if (!auth.body.token) { console.log(`  Auth FAILED`); continue; }

    for (const model of TP_MODELS) {
      const result = await createOrUpdateModel(url, auth.body.token, model);
      console.log(`  ${model.id}: ${result.action} (${result.ok ? 'OK' : 'FAILED ' + result.status})`);
    }
    console.log('');
  }

  console.log('Done.');
}

main().catch(e => console.error(e));
