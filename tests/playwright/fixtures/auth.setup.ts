import { test as setup } from '@playwright/test';
import { getTenantConfig, getTenantFromProjectName } from './tenant';
import { AUTH, NAV } from '../helpers/selectors';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/**
 * Authentication setup — runs once per tenant project.
 * Logs in via the UI and saves the browser storageState for reuse by all tests.
 */
setup('authenticate', async ({ page, browser }, testInfo) => {
  const tenantName = getTenantFromProjectName(testInfo.project.name);
  const tenant = getTenantConfig(tenantName);
  const authFile = path.resolve(__dirname, `../.auth/${tenantName}.json`);

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

  // Save authenticated state
  await page.context().storageState({ path: authFile });
});
