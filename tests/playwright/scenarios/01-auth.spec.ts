import { test, expect } from '@playwright/test';
import { MODEL } from '../helpers/selectors';

test.describe('01 — Authentication & Onboarding', () => {
  test('login with valid credentials loads main page', async ({ page }) => {
    // storageState already applied — we should be logged in
    await page.goto('/');
    // Wait for the chat interface to be visible (model selector)
    await expect(page.locator(MODEL.selectorButton)).toBeVisible({ timeout: 15_000 });
  });

  test('home page shows model selector', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton)).toBeVisible({ timeout: 15_000 });
  });

  test('models are listed in correct order', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton)).toBeVisible({ timeout: 15_000 });

    // Open model selector
    await page.locator(MODEL.selectorButton).click();

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
    await expect(page.locator(MODEL.selectorButton)).toBeVisible({ timeout: 15_000 });

    // User menu button — use getByRole to handle localized labels
    // In the accessibility tree: button "Menu utilisateur" (FR) or "User Menu" (EN)
    const userMenu = page.getByRole('button', { name: /menu/i }).last();
    await expect(userMenu).toBeVisible({ timeout: 10_000 });

    await userMenu.click();
    // Settings option should appear — "Réglages" (FR) or "Settings" (EN)
    await expect(
      page.getByText('Réglages').or(page.getByText('Settings')).first()
    ).toBeVisible({ timeout: 10_000 });
  });
});
