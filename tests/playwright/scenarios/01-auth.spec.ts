import { test, expect } from '@playwright/test';
import { ACCOUNT, MODEL } from '../helpers/selectors';

test.describe('01 — Authentication & Onboarding', () => {
  test('login with valid credentials loads main page', async ({ page }) => {
    // storageState already applied — we should be logged in
    await page.goto('/');
    // Wait for the chat interface to be visible (model selector)
    await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });
  });

  test('home page shows model selector', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });
  });

  test('models are listed in correct order', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });

    // Open model selector
    await page.locator(MODEL.selectorButton).first().click();

    // Wait for the listbox with model options to appear
    await expect(page.locator(MODEL.modelListbox)).toBeVisible({ timeout: 10_000 });

    // Count model options
    const modelOptions = page.locator(MODEL.modelOption);
    await expect(modelOptions.first()).toBeVisible({ timeout: 10_000 });

    const count = await modelOptions.count();
    expect(count).toBeGreaterThan(5); // We have 90+ models deployed
  });

  test('user menu is accessible', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });

    // Avatar button carries the localized aria-label "Menu utilisateur" (fr)
    // or "User menu" (en) — v0.10 dropped the /menu/i-matchable role name.
    const userMenu = page.locator(ACCOUNT.menuButton).first();
    await expect(userMenu).toBeVisible({ timeout: 10_000 });

    await userMenu.click();
    // Settings entry — "Réglages" in v0.10.2 fr (not "Paramètres")
    await expect(
      page.getByRole('button', { name: ACCOUNT.settingsEntry }).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
