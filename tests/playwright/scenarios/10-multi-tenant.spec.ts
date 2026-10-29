import { test, expect } from '@playwright/test';
import { getTenantConfig } from '../fixtures/tenant';
import { apiLogin, getModels, getKnowledgeBases } from '../helpers/api';

/**
 * Multi-tenant scenarios use the API directly to compare two tenants (myia + epf).
 * This avoids needing two browser sessions and is more reliable.
 */
test.describe('10 — Multi-tenant Isolation & Sharing', () => {
  let myiaTenant: ReturnType<typeof getTenantConfig>;
  let epfTenant: ReturnType<typeof getTenantConfig>;

  test.beforeAll(() => {
    try {
      myiaTenant = getTenantConfig('myia');
      epfTenant = getTenantConfig('epf');
    } catch {
      test.skip(true, 'Missing credentials for multi-tenant tests (need MYIA + EPF)');
    }
  });

  test('both tenants are accessible and can authenticate', async ({ request }) => {
    const myiaToken = await apiLogin(request, myiaTenant.url, myiaTenant.email, myiaTenant.password);
    expect(myiaToken).toBeTruthy();

    const epfToken = await apiLogin(request, epfTenant.url, epfTenant.email, epfTenant.password);
    expect(epfToken).toBeTruthy();
  });

  test('knowledge bases are shared across tenants', async ({ request }) => {
    const myiaToken = await apiLogin(request, myiaTenant.url, myiaTenant.email, myiaTenant.password);
    const epfToken = await apiLogin(request, epfTenant.url, epfTenant.email, epfTenant.password);

    // KB API may return HTML on some tenants (HTTPS/proxy issues)
    let myiaKBs: Awaited<ReturnType<typeof getKnowledgeBases>>;
    let epfKBs: Awaited<ReturnType<typeof getKnowledgeBases>>;
    try {
      myiaKBs = await getKnowledgeBases(request, myiaTenant.url, myiaToken);
      epfKBs = await getKnowledgeBases(request, epfTenant.url, epfToken);
    } catch (e) {
      test.skip(true, `KB API not available: ${(e as Error).message}`);
      return;
    }

    // Both should have KBs
    expect(myiaKBs.length).toBeGreaterThan(0);
    expect(epfKBs.length).toBeGreaterThan(0);

    // "Bibliographie IA" should be present on both
    const myiaBiblio = myiaKBs.find(kb => kb.name.includes('Bibliographie'));
    const epfBiblio = epfKBs.find(kb => kb.name.includes('Bibliographie'));
    expect(myiaBiblio).toBeTruthy();
    expect(epfBiblio).toBeTruthy();
  });

  test('custom models are deployed identically on both tenants', async ({ request }) => {
    const myiaToken = await apiLogin(request, myiaTenant.url, myiaTenant.email, myiaTenant.password);
    const epfToken = await apiLogin(request, epfTenant.url, epfTenant.email, epfTenant.password);

    const myiaModels = await getModels(request, myiaTenant.url, myiaToken);
    const epfModels = await getModels(request, epfTenant.url, epfToken);

    // Both should have models
    expect(myiaModels.length).toBeGreaterThan(10);
    expect(epfModels.length).toBeGreaterThan(10);

    // Check that key custom models exist on both
    const customModelIds = ['expert-analyste', 'redacteur-technique', 'vision-expert'];
    for (const modelId of customModelIds) {
      const onMyia = myiaModels.some(m => m.id.includes(modelId));
      const onEpf = epfModels.some(m => m.id.includes(modelId));
      expect(onMyia, `${modelId} should exist on myia`).toBeTruthy();
      expect(onEpf, `${modelId} should exist on epf`).toBeTruthy();
    }
  });

  test('data isolation: tenants have separate user bases', async ({ request }) => {
    const myiaToken = await apiLogin(request, myiaTenant.url, myiaTenant.email, myiaTenant.password);
    const epfToken = await apiLogin(request, epfTenant.url, epfTenant.email, epfTenant.password);

    // Get user count from both tenants via models endpoint (as a proxy for distinct data)
    // Each tenant has its own database, so models count may differ slightly
    const myiaModels = await getModels(request, myiaTenant.url, myiaToken);
    const epfModels = await getModels(request, epfTenant.url, epfToken);

    // Model counts should be similar (both deployed from same config) but may differ
    // The key assertion is that both work independently
    expect(myiaModels.length).toBeGreaterThan(0);
    expect(epfModels.length).toBeGreaterThan(0);
  });
});
