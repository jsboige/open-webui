import { test as setup } from '@playwright/test';
import { getTenantConfig, getTenantFromProjectName } from './tenant';
import { AUTH, NAV } from '../helpers/selectors';
import { apiLogin } from '../helpers/api';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Authentication setup — runs once per tenant project.
 * Logs in via the UI and saves the browser storageState for reuse by all tests.
 */
setup('authenticate', async ({ page, browser, request }, testInfo) => {
  const tenantName = getTenantFromProjectName(testInfo.project.name);
  const tenant = getTenantConfig(tenantName);
  const authFile = path.resolve(__dirname, `../.auth/${tenantName}.json`);
  const baseURL = (testInfo.project.use.baseURL as string) ?? tenant.url;

  // Mark the current version as seen BEFORE the browser opens.
  //
  // The "What's New" changelog modal is rendered for admin accounts only
  // (src/routes/(app)/+layout.svelte: `$user?.role === 'admin' &&
  // $settings?.version !== $config.version`) and it intercepts every pointer
  // event. Clicking "Close" only fixed the symptom; the modal reappears on
  // every account whose version was never persisted. OWUI itself marks it as
  // seen with `updateUserSettings(token, { ui: { version } })`
  // (src/lib/components/ChangelogModal.svelte:44), so we do exactly that
  // through the API first — the modal then never renders.
  const token = await apiLogin(request, baseURL, tenant.email, tenant.password);
  const configResponse = await request.get(`${baseURL}/api/config`);
  const currentVersion = configResponse.ok()
    ? ((await configResponse.json()) as { version?: string }).version
    : undefined;
  if (currentVersion) {
    const markSeen = await request.post(`${baseURL}/api/v1/users/user/settings/update`, {
      headers: { Authorization: `Bearer ${token}` },
      data: { ui: { version: currentVersion } },
    });
    console.log(
      `[auth.setup] ${tenantName}: version ${currentVersion} marked as seen (${markSeen.status()})`,
    );
  }

  // Navigate to login page
  await page.goto('/auth');

  // Fill login form
  await page.locator(AUTH.emailInput).fill(tenant.email);
  await page.locator(AUTH.passwordInput).fill(tenant.password);
  await page.locator(AUTH.submitButton).click();

  // Wait for redirect from /auth to main page after successful login
  await page.waitForURL('**/', { timeout: 30_000 });
  // Wait for the chat interface to fully load
  await page.waitForLoadState('networkidle', { timeout: 15_000 });

  // Fallback dismissal: the API call above should make this modal impossible,
  // but the button is kept for tenants where the setting could not be written.
  // closeModal persists the seen version in localStorage + server-side user
  // settings, whereas Escape only hides it for the current page load.
  const whatsNewDialog = page.getByRole('dialog').first();
  if (await whatsNewDialog.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await whatsNewDialog
      .getByRole('button', { name: /^(Fermer|Close)$/ })
      .first()
      .click();
    await whatsNewDialog.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => {});
  }

  // Fail loudly if a modal is still up: a lingering dialog silently breaks
  // every downstream test (the pointer events are swallowed), which cost a
  // 13/16-red run on epf on 2026-09-01. Better a red setup with the reason
  // than a red suite with no reason.
  if (await whatsNewDialog.isVisible({ timeout: 2_000 }).catch(() => false)) {
    throw new Error(
      `[auth.setup] ${tenantName}: a modal dialog is still visible after login — ` +
        `it will intercept clicks for the whole run (changelog "What's New"?). ` +
        `Check that the "mark version as seen" API call above returned 200.`,
    );
  }

  // Save authenticated state
  await page.context().storageState({ path: authFile });
});
