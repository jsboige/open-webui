import { test, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { getTenantConfig, type TenantConfig } from '../fixtures/tenant';
import {
  apiLogin,
  chatCompletion,
  generateTTS,
  transcribeAudio,
  getOpenAIConfig,
  getEmbeddingConfig,
  getAudioConfig,
  getImageConfig,
  getToolServers,
  getChannels,
  getModels,
  getModelDetail,
  getKnowledgeBases,
  getFunctions,
} from '../helpers/api';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Scenario 18 — Full Stack Services Verification
 *
 * End-to-end functional tests for ALL services on a tenant instance.
 * Covers: LLM connectors, personas, embedding/RAG, TTS, STT, image gen,
 * MCP tools, channels, and infrastructure checks.
 *
 * Run: npx playwright test scenarios/18-full-stack-services.spec.ts --project=myia
 */

const TENANT_NAMES = ['myia', 'epf', 'epf-genai', 'ece', 'esg', 'epita', 'pauwels'];

// Audio fixture for STT testing
const AUDIO_FIXTURE = path.resolve(__dirname, '../fixtures/audio/test-audio.mp3');

test.describe('18 — Full Stack Services Verification', () => {
  const tenantTokens: Record<string, { config: TenantConfig; token: string }> = {};

  test.beforeAll(async ({ request }) => {
    for (const name of TENANT_NAMES) {
      try {
        const config = getTenantConfig(name);
        const token = await apiLogin(request, config.url, config.email, config.password);
        tenantTokens[name] = { config, token };
      } catch {
        // Skip tenants without credentials
      }
    }
  });

  // ─── 18.1 Connectors ───────────────────────────────────────────

  test.describe('18.1 — OpenAI Connectors', () => {
    test('connectors are configured (12 expected, no Groq)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const config = await getOpenAIConfig(request, myia.config.url, myia.token);
      expect(config.urls.length).toBe(12);
      const hasGroq = config.urls.some(u => u.includes('groq.com'));
      expect(hasGroq, 'Groq should be removed').toBe(false);
    });

    test('connectors are consistent across tenants', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const refConfig = await getOpenAIConfig(request, myia.config.url, myia.token);
      const mismatches: string[] = [];

      for (const [name, { config, token }] of Object.entries(tenantTokens)) {
        if (name === 'myia') continue;
        const tConfig = await getOpenAIConfig(request, config.url, token);
        if (tConfig.urls.length !== refConfig.urls.length) {
          mismatches.push(`${name}: ${tConfig.urls.length} urls vs ${refConfig.urls.length}`);
        }
      }
      expect(mismatches, mismatches.join('; ')).toHaveLength(0);
    });
  });

  // ─── 18.2 LLM Connectivity ────────────────────────────────────

  test.describe('18.2 — LLM Connectivity', () => {
    const LLM_TESTS = [
      { name: 'MistralAI devstral-small', model: 'MistralAI.devstral-small-latest' },
      { name: 'MistralAI mistral-medium', model: 'MistralAI.mistral-medium-latest' },
      { name: 'OpenAI gpt-4.1-mini', model: 'OpenAI.gpt-4.1-mini' },
      { name: 'DeepSeek', model: 'DeepSeek.deepseek-v4-flash' },
      { name: 'vLLM medium (Qwen 3.6)', model: 'Local.qwen3.6-35b-a3b' },
    ];

    for (const { name, model } of LLM_TESTS) {
      test(`${name} responds`, async ({ request }) => {
        const myia = tenantTokens['myia'];
        test.skip(!myia, 'myia not available');

        const response = await chatCompletion(
          request, myia.config.url, myia.token, model, 'Say OK', { timeout: 90_000 },
        );
        expect(response, `${name} should respond`).toBeTruthy();
      });
    }
  });

  // ─── 18.3 Personas ────────────────────────────────────────────

  test.describe('18.3 — Persona Functional Tests', () => {
    const PERSONAS = [
      { id: 'samantha', name: 'Samantha', expectedBase: 'OpenAI.gpt-5' },
      { id: 'emilio:latest', name: 'Emilio', expectedBase: 'OpenAI.gpt-5' },
      { id: 'professeur-psychanalyste', name: 'Dr. Charpentier', expectedBase: 'OpenAI.o4-mini' },
      { id: 'codewriter:latest', name: 'codewriter', expectedBase: 'OpenAI.gpt-5.2' },
      { id: 'expert-analyste', name: 'Expert Analyste', expectedBase: 'Local.qwen3.6-35b-a3b' },
    ];

    for (const { id, name, expectedBase } of PERSONAS) {
      test(`${name} (${expectedBase}) responds`, async ({ request }) => {
        const myia = tenantTokens['myia'];
        test.skip(!myia, 'myia not available');

        // Check base model is correct
        const detail = await getModelDetail(request, myia.config.url, myia.token, id);
        expect(detail.base_model_id).toBe(expectedBase);

        // Functional test: send a message
        const response = await chatCompletion(
          request, myia.config.url, myia.token, id, 'Say hello in one sentence.', { timeout: 90_000 },
        );
        expect(response, `${name} should respond`).toBeTruthy();
        expect(response!.length).toBeGreaterThan(2);
      });
    }

    test('no persona uses retired models', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const models = await getModels(request, myia.config.url, myia.token);
      const retired = ['OpenAI.o3-mini', 'OpenAI.chatgpt-4o-latest', 'Local.Qwen/QwQ-32B-AWQ'];
      const errors: string[] = [];

      for (const m of models) {
        if (!m.id || m.id.includes('.')) continue; // skip connector models
        try {
          const detail = await getModelDetail(request, myia.config.url, myia.token, m.id);
          if (retired.includes(detail.base_model_id ?? '')) {
            errors.push(`${m.id} uses retired model ${detail.base_model_id}`);
          }
        } catch {
          // Model detail not available
        }
      }
      expect(errors, errors.join('; ')).toHaveLength(0);
    });

    test('no persona uses Groq base model', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const models = await getModels(request, myia.config.url, myia.token);
      const errors: string[] = [];

      for (const m of models) {
        if (!m.id || m.id.includes('.')) continue;
        try {
          const detail = await getModelDetail(request, myia.config.url, myia.token, m.id);
          if ((detail.base_model_id ?? '').startsWith('Groq.')) {
            errors.push(`${m.id} uses Groq model ${detail.base_model_id}`);
          }
        } catch {
          // skip
        }
      }
      expect(errors, errors.join('; ')).toHaveLength(0);
    });
  });

  // ─── 18.4 Embedding & RAG ─────────────────────────────────────

  test.describe('18.4 — Embedding & RAG', () => {
    test('embedding config is correct', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const config = await getEmbeddingConfig(request, myia.config.url, myia.token);
      expect(config.RAG_EMBEDDING_ENGINE).toBe('openai');
      expect(config.RAG_EMBEDDING_MODEL).toBe('qwen3-4b-awq-embedding');
      const openaiCfg = config.openai_config as Record<string, string>;
      expect(openaiCfg.url).toBe('https://embeddings.myia.io/v1');
      expect(openaiCfg.key?.length).toBeGreaterThan(30);
    });

    test('RAG works end-to-end (chat with KB)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      // Find a KB
      const kbs = await getKnowledgeBases(request, myia.config.url, myia.token);
      const biblio = kbs.find(kb => kb.name.includes('Bibliographie'));
      test.skip(!biblio, 'No Bibliographie KB found');

      // Chat with KB attached
      const response = await chatCompletion(
        request, myia.config.url, myia.token,
        'MistralAI.mistral-medium-latest',
        'Que sais-tu sur la programmation par contraintes?',
        { files: [{ type: 'collection', id: biblio!.id }], timeout: 90_000 },
      );
      expect(response).toBeTruthy();
      expect(response!.toLowerCase()).toMatch(/contrainte|csp|satisfaction|variable/i);
    });

    test('embedding config is consistent across tenants', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const refConfig = await getEmbeddingConfig(request, myia.config.url, myia.token);
      const refKey = (refConfig.openai_config as Record<string, string>)?.key;
      const mismatches: string[] = [];

      for (const [name, { config, token }] of Object.entries(tenantTokens)) {
        if (name === 'myia') continue;
        const tConfig = await getEmbeddingConfig(request, config.url, token);
        const tKey = (tConfig.openai_config as Record<string, string>)?.key;
        if (tKey !== refKey) {
          mismatches.push(`${name}: key mismatch`);
        }
      }
      expect(mismatches, mismatches.join('; ')).toHaveLength(0);
    });
  });

  // ─── 18.5 Audio (TTS & STT) ───────────────────────────────────

  test.describe('18.5 — Audio Services', () => {
    test('audio config is set (TTS=kokoro, STT=whisper)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const config = await getAudioConfig(request, myia.config.url, myia.token);
      expect(config.tts.ENGINE).toBe('openai');
      expect(config.tts.MODEL).toBe('kokoro');
      expect(config.stt.ENGINE).toBe('openai');
      expect(config.stt.MODEL).toBe('whisper-1');
    });

    test('TTS generates audio', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      // Unique suffix busts OWUI's speech cache (keyed on raw request body):
      // a cached hit would mask a dead TTS backend (false-green, 2026-07-02).
      const audioSize = await generateTTS(
        request, myia.config.url, myia.token, `Bonjour, ceci est un test. ${Date.now()}`,
      );
      expect(audioSize, 'TTS should return audio data').toBeGreaterThan(1000);
    });

    test('STT transcribes audio', async ({ request }) => {
      test.setTimeout(300_000); // 5 min — Whisper can be slow on large files
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const fs = await import('fs');
      test.skip(!fs.existsSync(AUDIO_FIXTURE), 'Audio fixture not found');

      const transcript = await transcribeAudio(
        request, myia.config.url, myia.token, AUDIO_FIXTURE,
      );
      expect(transcript, 'STT should return text').toBeTruthy();
      expect(transcript!.length).toBeGreaterThan(10);
    });
  });

  // ─── 18.6 Image Generation ────────────────────────────────────

  test.describe('18.6 — Image Generation', () => {
    test('image config is set (SD Forge)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const config = await getImageConfig(request, myia.config.url, myia.token);
      expect(config.ENABLE_IMAGE_GENERATION).toBe(true);
      expect(config.IMAGE_GENERATION_ENGINE).toBe('automatic1111');
      expect(config.AUTOMATIC1111_BASE_URL).toContain('stable-diffusion');
    });

    test('SD Forge is reachable and has models', async ({ request }) => {
      const response = await request.get(
        'https://turbo.stable-diffusion-webui-forge.myia.io/sdapi/v1/sd-models',
        { timeout: 15_000 },
      );
      expect(response.ok()).toBeTruthy();
      const models = await response.json();
      expect(Array.isArray(models)).toBeTruthy();
      expect(models.length).toBeGreaterThan(0);
    });
  });

  // ─── 18.7 Tools & MCP ─────────────────────────────────────────

  test.describe('18.7 — Tools & MCP', () => {
    test('functions are installed (>= 5 active)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const funcs = await getFunctions(request, myia.config.url, myia.token);
      expect(funcs.length).toBeGreaterThanOrEqual(5);
      const active = funcs.filter((f: Record<string, unknown>) => f.is_active);
      expect(active.length).toBeGreaterThanOrEqual(3);
    });

    test('MCP tool server is configured (SK-Agent)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const servers = await getToolServers(request, myia.config.url, myia.token);
      expect(servers.length).toBeGreaterThanOrEqual(1);
      const skAgent = servers.find((s: Record<string, unknown>) => {
        const url = s.url as string;
        return url?.includes('sk-agent');
      });
      expect(skAgent, 'SK-Agent should be configured').toBeTruthy();
    });
  });

  // ─── 18.8 Channels & Infrastructure ───────────────────────────

  test.describe('18.8 — Channels & Infrastructure', () => {
    test('EPITA has the PPC channel', async ({ request }) => {
      const epita = tenantTokens['epita'];
      test.skip(!epita, 'epita not available');

      const channels = await getChannels(request, epita.config.url, epita.token);
      const ppc = channels.find(c => c.name.includes('ppc'));
      expect(ppc, 'PPC channel should exist on EPITA').toBeTruthy();
    });

    test('knowledge bases exist (>= 10)', async ({ request }) => {
      const myia = tenantTokens['myia'];
      test.skip(!myia, 'myia not available');

      const kbs = await getKnowledgeBases(request, myia.config.url, myia.token);
      expect(kbs.length).toBeGreaterThanOrEqual(10);
    });
  });
});
