import { test, expect } from '@playwright/test';
import { getTenantConfig } from '../fixtures/tenant';
import { apiLogin, getModels, getModelDetail } from '../helpers/api';

/**
 * Scenario 16 — TP Tutor Models: Configuration Validation (API-only)
 *
 * Validates that all 5 tutor models are correctly deployed and configured
 * on the myia tenant. Checks model existence, base_model_id, system prompts,
 * and function_calling settings.
 */

const TUTOR_MODELS = [
  {
    id: 'tp-linux-debutant',
    name: /linux/i,
    expectFunctionCalling: true, // Uses Open Terminal for Linux commands
    systemKeywords: ['linux', 'terminal', 'commande'],
  },
  {
    id: 'tp-git-workflow',
    name: /git/i,
    expectFunctionCalling: true, // Uses Open Terminal for Git exercises
    systemKeywords: ['git', 'version', 'commit'],
  },
  {
    id: 'tp-python-data',
    name: /python/i,
    expectFunctionCalling: true, // Uses Open Terminal for Python/Pandas
    systemKeywords: ['python', 'pandas', 'données'],
  },
  {
    id: 'tp-prompt-engineering',
    name: /prompt/i,
    expectFunctionCalling: false, // Conversational only, no tools
    systemKeywords: ['prompt', 'module'],
  },
  {
    id: 'tp-data-analyst-agent',
    name: /data.*analyst|analyst.*data/i,
    expectFunctionCalling: true, // Uses Open Terminal for data analysis
    systemKeywords: ['pandas', 'analyse', 'dataset'],
  },
];

test.describe('16 — TP Tutor Models: Configuration Validation', () => {
  let tenant: ReturnType<typeof getTenantConfig>;
  let token: string;

  test.beforeAll(async ({ request }) => {
    try {
      tenant = getTenantConfig('myia');
    } catch {
      test.skip(true, 'Missing myia credentials');
      return;
    }
    token = await apiLogin(request, tenant.url, tenant.email, tenant.password);
  });

  test('all 5 tutor models exist on myia', async ({ request }) => {
    const models = await getModels(request, tenant.url, token);
    const modelIds = models.map(m => m.id);

    for (const tutor of TUTOR_MODELS) {
      const found = modelIds.some(id => id.includes(tutor.id));
      expect(found, `Tutor model "${tutor.id}" should exist`).toBeTruthy();
    }
  });

  for (const tutor of TUTOR_MODELS) {
    test(`${tutor.id}: has valid base_model_id`, async ({ request }) => {
      let detail: Awaited<ReturnType<typeof getModelDetail>>;
      try {
        detail = await getModelDetail(request, tenant.url, token, tutor.id);
      } catch {
        test.skip(true, `Model ${tutor.id} not found`);
        return;
      }

      expect(detail.base_model_id, `${tutor.id} should have a base_model_id`).toBeTruthy();
      // base_model_id should reference a real model (not null or empty)
      expect(detail.base_model_id!.length).toBeGreaterThan(0);
    });

    test(`${tutor.id}: has system prompt with expected keywords`, async ({ request }) => {
      let detail: Awaited<ReturnType<typeof getModelDetail>>;
      try {
        detail = await getModelDetail(request, tenant.url, token, tutor.id);
      } catch {
        test.skip(true, `Model ${tutor.id} not found`);
        return;
      }

      const systemPrompt = (detail.params?.system as string) || '';
      expect(systemPrompt.length, `${tutor.id} should have a system prompt`).toBeGreaterThan(50);

      // Check at least one keyword is present
      const hasKeyword = tutor.systemKeywords.some(kw =>
        systemPrompt.toLowerCase().includes(kw.toLowerCase())
      );
      expect(hasKeyword, `${tutor.id} system prompt should contain one of: ${tutor.systemKeywords.join(', ')}`).toBeTruthy();
    });

    test(`${tutor.id}: function_calling is ${tutor.expectFunctionCalling ? 'enabled' : 'disabled'}`, async ({ request }) => {
      let detail: Awaited<ReturnType<typeof getModelDetail>>;
      try {
        detail = await getModelDetail(request, tenant.url, token, tutor.id);
      } catch {
        test.skip(true, `Model ${tutor.id} not found`);
        return;
      }

      const functionCalling = detail.params?.function_calling as string | undefined;
      if (tutor.expectFunctionCalling) {
        expect(functionCalling, `${tutor.id} should have function_calling enabled`).toBe('native');
      } else {
        // Should be absent, null, or empty — NOT "native"
        expect(functionCalling !== 'native', `${tutor.id} should NOT have function_calling: native`).toBeTruthy();
      }
    });
  }
});
