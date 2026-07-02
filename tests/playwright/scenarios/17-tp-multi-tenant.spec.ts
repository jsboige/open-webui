import { test, expect } from '@playwright/test';
import { getTenantConfig, type TenantConfig } from '../fixtures/tenant';
import { apiLogin, getModels, getModelDetail } from '../helpers/api';

/**
 * Scenario 17 — TP Tutor Models: Multi-Tenant Deployment Validation
 *
 * Verifies that all 5 tutor models are deployed consistently across
 * all 7 tenants with matching configuration.
 */

const TUTOR_MODEL_IDS = [
  'tp-linux-debutant',
  'tp-git-workflow',
  'tp-python-data',
  'tp-prompt-engineering',
  'tp-data-analyst-agent',
];

const TENANT_NAMES = ['myia', 'epf', 'epf-genai', 'ece', 'esg', 'epita', 'pauwels'];

test.describe('17 — TP Tutor Models: Multi-Tenant Deployment', () => {
  const tenantTokens: Record<string, { config: TenantConfig; token: string }> = {};

  test.beforeAll(async ({ request }) => {
    // Login to all tenants, skipping those without credentials
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

  test('at least 3 tenants are accessible', () => {
    const count = Object.keys(tenantTokens).length;
    expect(count, `Only ${count} tenants accessible, need at least 3`).toBeGreaterThanOrEqual(3);
  });

  for (const modelId of TUTOR_MODEL_IDS) {
    test(`${modelId} exists on all accessible tenants`, async ({ request }) => {
      const missing: string[] = [];

      for (const [name, { config, token }] of Object.entries(tenantTokens)) {
        // The subject here is deployment consistency, not API availability:
        // under full-suite load /api/models can transiently time out or serve
        // a partial list mid connector-cache refresh, so retry once before
        // declaring the tutor missing on a tenant.
        let found = false;
        let lastError = '';
        for (let attempt = 0; attempt < 2 && !found; attempt++) {
          if (attempt > 0) await new Promise(resolve => setTimeout(resolve, 3_000));
          try {
            const models = await getModels(request, config.url, token);
            found = models.some(m => m.id.includes(modelId));
            lastError = '';
          } catch (error) {
            lastError = error instanceof Error ? error.message : String(error);
          }
        }
        if (!found) missing.push(lastError ? `${name} (fetch failed: ${lastError})` : name);
      }

      expect(missing, `${modelId} missing on: ${missing.join(', ')}`).toHaveLength(0);
    });
  }

  test('tutor models have consistent base_model_id across tenants', async ({ request }) => {
    // Use myia as reference
    const myia = tenantTokens['myia'];
    test.skip(!myia, 'myia tenant not available');

    const referenceBaseModels: Record<string, string> = {};

    // Get base_model_id from myia for each tutor
    for (const modelId of TUTOR_MODEL_IDS) {
      try {
        const detail = await getModelDetail(request, myia.config.url, myia.token, modelId);
        if (detail.base_model_id) {
          referenceBaseModels[modelId] = detail.base_model_id;
        }
      } catch {
        // Model might not exist
      }
    }

    // Compare with other tenants
    const mismatches: string[] = [];
    for (const [name, { config, token }] of Object.entries(tenantTokens)) {
      if (name === 'myia') continue;

      for (const [modelId, expectedBase] of Object.entries(referenceBaseModels)) {
        try {
          const detail = await getModelDetail(request, config.url, token, modelId);
          if (detail.base_model_id !== expectedBase) {
            mismatches.push(`${name}/${modelId}: ${detail.base_model_id} != ${expectedBase}`);
          }
        } catch {
          // Model not found on this tenant — caught by existence test
        }
      }
    }

    expect(mismatches, `base_model_id mismatches: ${mismatches.join('; ')}`).toHaveLength(0);
  });

  test('function_calling config is consistent across tenants', async ({ request }) => {
    const myia = tenantTokens['myia'];
    test.skip(!myia, 'myia tenant not available');

    // Terminal tutors (linux, git, python-data, data-analyst) need function_calling: native
    // Only tp-prompt-engineering is conversational (no tools)
    const TERMINAL_TUTORS = ['tp-linux-debutant', 'tp-git-workflow', 'tp-python-data', 'tp-data-analyst-agent'];
    const errors: string[] = [];

    for (const [name, { config, token }] of Object.entries(tenantTokens)) {
      for (const modelId of TUTOR_MODEL_IDS) {
        try {
          const detail = await getModelDetail(request, config.url, token, modelId);
          const fc = detail.params?.function_calling as string | undefined;
          const needsTools = TERMINAL_TUTORS.includes(modelId);

          if (needsTools && fc !== 'native') {
            errors.push(`${name}/${modelId}: should have function_calling=native but has ${fc}`);
          } else if (!needsTools && fc === 'native') {
            errors.push(`${name}/${modelId}: should NOT have function_calling=native`);
          }
        } catch {
          // Skip missing models
        }
      }
    }

    expect(errors, `function_calling issues: ${errors.join('; ')}`).toHaveLength(0);
  });
});
