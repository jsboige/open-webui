// Create test conversations for different models and features
// Usage: MYIA_EMAIL=... MYIA_PASSWORD=... node scripts/create_test_chats.cjs

const BASE = 'https://open-webui.myia.io';
const TESTS_FOLDER_ID = '7764254e-6513-4246-b2b5-ff7ee7c000d0';

// --- Test definitions ---
const TESTS = [
  // Model tests
  {
    name: '[Modèle] Qwen3.6-35B (Thinking)',
    model: 'Local.qwen3.6-35b-a3b',
    prompt: 'Résous ce problème étape par étape : Si un train part de Paris à 14h à 120 km/h et un autre de Lyon à 14h30 à 150 km/h (sens inverse), à quelle heure se croisent-ils ? (Paris-Lyon = 465 km)',
  },
  {
    name: '[Modèle] Qwen3.6-35B Fast',
    model: 'Local.qwen3.6-35b-a3b-fast',
    prompt: 'Résous ce problème : Si un train part de Paris à 14h à 120 km/h et un autre de Lyon à 14h30 à 150 km/h (sens inverse), à quelle heure se croisent-ils ? (Paris-Lyon = 465 km)',
  },
  {
    name: '[Modèle] GPT-4.1',
    model: 'OpenAI.gpt-4.1',
    prompt: 'Explique le concept de transformer (architecture deep learning) en 5 phrases claires et accessibles, en français.',
  },
  {
    name: '[Modèle] DeepSeek Chat',
    model: 'DeepSeek.deepseek-chat',
    prompt: 'Écris une fonction Python qui implémente le tri fusion (merge sort) avec des commentaires en français. Inclus un exemple d\'utilisation.',
  },
  {
    name: '[Modèle] DeepSeek Reasoner',
    model: 'DeepSeek.deepseek-reasoner',
    prompt: 'Résous cette énigme logique : Trois personnes (A, B, C) portent chacune un chapeau rouge ou bleu. Chacune voit les chapeaux des deux autres mais pas le sien. A dit "Je ne sais pas la couleur de mon chapeau." B dit "Je ne sais pas non plus." C dit "Je sais que mon chapeau est rouge." Explique le raisonnement de C.',
  },
  {
    name: '[Modèle] Groq (Llama-4-Maverick)',
    model: 'Groq.meta-llama/llama-4-maverick-17b-128e-instruct',
    prompt: 'Quelle est la différence entre le machine learning supervisé et non-supervisé ? Donne un exemple concret pour chaque. Réponds en français.',
  },
  {
    name: '[Modèle] Mistral Large',
    model: 'MistralAI.mistral-large-latest',
    prompt: 'Analyse "L\'Albatros" de Baudelaire (Les Fleurs du Mal) en identifiant les figures de style principales et le message du poème. Réponds en français, en 10 lignes maximum.',
  },
  {
    name: '[Modèle] Claude Sonnet 4 (OpenRouter)',
    model: 'OpenRouter.anthropic/claude-sonnet-4',
    prompt: 'Compare les architectures CNN et Vision Transformer (ViT) pour la classification d\'images. Avantages, inconvénients et cas d\'usage recommandés pour chaque approche.',
  },
  // Feature tests
  {
    name: '[RAG] Recherche Bibliographie IA',
    model: 'Local.qwen3.6-35b-a3b-fast',
    prompt: 'D\'après les documents de la bibliographie, quels sont les principaux algorithmes de recherche en intelligence artificielle ? Cite les sources.',
    rag_kb: 'Bibliographie IA',
  },
  {
    name: '[RAG] Argumentation & Esprit Critique',
    model: 'Local.qwen3.6-35b-a3b-fast',
    prompt: 'Quels sont les principaux types de sophismes (fallacies) décrits dans les documents ? Donne des exemples concrets.',
    rag_kb: 'Argumentation et Esprit Critique',
  },
  {
    name: '[Outil] sk-agent - Liste agents',
    model: 'Local.qwen3.6-35b-a3b-fast',
    prompt: 'Utilise l\'outil sk-agent pour lister tous les agents disponibles. Présente le résultat sous forme de tableau.',
    tool_ids: ['server:mcp:sk-agent'],
  },
  {
    name: '[Code] Python Pipeline',
    model: 'python_code_pipeline',
    prompt: 'Calcule et affiche les 20 premiers nombres de Fibonacci, puis trace un graphique ASCII de leur croissance.',
  },
];

// --- Helpers ---
function uuid() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function apiCall(path, token, options = {}) {
  const { method = 'GET', body, timeout = 180000 } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`HTTP ${res.status}: ${text.substring(0, 200)}`);
    }
    return res.json();
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}

// --- Main ---
async function main() {
  const email = process.env.MYIA_EMAIL;
  const password = process.env.MYIA_PASSWORD;
  if (!email || !password) {
    console.error('Usage: MYIA_EMAIL=... MYIA_PASSWORD=... node scripts/create_test_chats.cjs');
    process.exit(1);
  }

  // 1. Auth
  console.log('=== Authentification ===');
  const authRes = await fetch(`${BASE}/api/v1/auths/signin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const authData = await authRes.json();
  if (!authData.token) {
    console.error('Auth failed:', JSON.stringify(authData).substring(0, 200));
    process.exit(1);
  }
  const token = authData.token;
  console.log('  OK - token obtained');

  // 2. Fetch models (validate IDs)
  console.log('\n=== Vérification des modèles ===');
  const modelsRes = await apiCall('/api/models', token);
  const modelIds = new Set((modelsRes.data || modelsRes).map(m => m.id));
  console.log(`  ${modelIds.size} modèles disponibles`);

  // Check which test models exist
  const missingModels = new Set();
  for (const test of TESTS) {
    if (!modelIds.has(test.model)) {
      missingModels.add(test.model);
      console.log(`  ⚠ Modèle manquant: ${test.model}`);
    }
  }

  // 3. Fetch KBs (get full UUIDs for RAG tests)
  console.log('\n=== Knowledge Bases ===');
  const kbRes = await apiCall('/api/v1/knowledge/?page=1', token);
  const kbs = kbRes.items || kbRes;
  const kbMap = {};
  for (const kb of kbs) {
    kbMap[kb.name] = kb.id;
    console.log(`  ${kb.id.substring(0, 8)}... → ${kb.name}`);
  }

  // 4. Run tests
  console.log('\n=== Création des conversations de test ===\n');
  const results = [];

  for (let i = 0; i < TESTS.length; i++) {
    const test = TESTS[i];
    const testNum = `[${i + 1}/${TESTS.length}]`;

    // Skip if model missing
    if (missingModels.has(test.model)) {
      console.log(`${testNum} SKIP ${test.name} (modèle ${test.model} indisponible)`);
      results.push({ name: test.name, status: 'SKIP', reason: 'model missing' });
      continue;
    }

    console.log(`${testNum} ${test.name} (${test.model})`);
    console.log(`  Prompt: "${test.prompt.substring(0, 80)}..."`);

    try {
      // Build completions request
      const completionBody = {
        model: test.model,
        messages: [{ role: 'user', content: test.prompt }],
        stream: false,
      };

      // Add RAG files if needed
      if (test.rag_kb) {
        const kbId = kbMap[test.rag_kb];
        if (!kbId) {
          throw new Error(`KB "${test.rag_kb}" not found`);
        }
        completionBody.files = [{
          type: 'collection',
          id: kbId,
          name: test.rag_kb,
        }];
        console.log(`  RAG KB: ${test.rag_kb} (${kbId.substring(0, 8)}...)`);
      }

      // Add tool IDs if needed
      if (test.tool_ids) {
        completionBody.tool_ids = test.tool_ids;
        console.log(`  Tools: ${test.tool_ids.join(', ')}`);
      }

      // Call chat completions (with generous timeout)
      const startTime = Date.now();
      const completion = await apiCall('/api/chat/completions', token, {
        method: 'POST',
        body: completionBody,
        timeout: 300000, // 5 min for slow models
      });
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

      // Extract response
      let responseContent = '';
      if (completion.choices && completion.choices[0]) {
        responseContent = completion.choices[0].message?.content || '';
      }
      if (!responseContent && completion.error) {
        throw new Error(completion.error.message || JSON.stringify(completion.error));
      }

      console.log(`  Réponse (${elapsed}s): "${responseContent.substring(0, 120).replace(/\n/g, ' ')}..."`);

      // Build usage info
      const usage = completion.usage || {};

      // Create chat in OWUI
      const chatId = uuid();
      const msgId1 = uuid();
      const msgId2 = uuid();
      const now = Date.now();

      const chatPayload = {
        chat: {
          id: chatId,
          title: test.name,
          models: [test.model],
          system: null,
          params: {},
          history: {
            messages: {
              [msgId1]: {
                id: msgId1,
                role: 'user',
                content: test.prompt,
                timestamp: now,
                parentId: null,
                childrenIds: [msgId2],
              },
              [msgId2]: {
                id: msgId2,
                role: 'assistant',
                content: responseContent,
                model: test.model,
                timestamp: now + 1000,
                parentId: msgId1,
                childrenIds: [],
                done: true,
                info: usage.total_tokens ? { usage } : undefined,
              },
            },
            currentId: msgId2,
          },
          messages: [
            { id: msgId1, role: 'user', content: test.prompt },
            { id: msgId2, role: 'assistant', content: responseContent, model: test.model },
          ],
          tags: [],
          timestamp: now,
        },
        folder_id: TESTS_FOLDER_ID,
      };

      const chatRes = await apiCall('/api/v1/chats/new', token, {
        method: 'POST',
        body: chatPayload,
      });

      console.log(`  ✓ Chat créé: ${chatRes.id.substring(0, 8)}... → dossier Tests`);
      results.push({
        name: test.name,
        status: 'OK',
        model: test.model,
        elapsed: `${elapsed}s`,
        tokens: usage.total_tokens || '?',
        chatId: chatRes.id,
        preview: responseContent.substring(0, 80),
      });

    } catch (err) {
      const errMsg = err.name === 'AbortError' ? 'TIMEOUT (5min)' : err.message;
      console.log(`  ✗ ERREUR: ${errMsg.substring(0, 150)}`);
      results.push({ name: test.name, status: 'ERROR', reason: errMsg.substring(0, 100) });
    }

    // Small delay between tests
    if (i < TESTS.length - 1) {
      await sleep(3000);
    }
  }

  // 5. Summary
  console.log('\n=== Résumé ===\n');
  const ok = results.filter(r => r.status === 'OK');
  const skip = results.filter(r => r.status === 'SKIP');
  const err = results.filter(r => r.status === 'ERROR');

  console.log(`Total: ${results.length} tests — ${ok.length} OK, ${skip.length} SKIP, ${err.length} ERREUR\n`);

  for (const r of results) {
    const icon = r.status === 'OK' ? '✓' : r.status === 'SKIP' ? '⊘' : '✗';
    const detail = r.status === 'OK'
      ? `${r.elapsed}, ${r.tokens} tokens`
      : r.reason;
    console.log(`  ${icon} ${r.name} — ${detail}`);
  }
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
