import { test, expect } from '@playwright/test';

test.describe('08 — Admin Panel', () => {
  test('access admin panel shows users', async ({ page }) => {
    // /admin loads the users page directly (no "Dashboard" in v0.8.7)
    await page.goto('/admin');
    // Admin nav shows "Utilisateurs" (FR) or "Users" (EN)
    await expect(
      page.getByText('Utilisateurs').or(page.getByText('Users')).first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test('users table shows admin user', async ({ page }) => {
    await page.goto('/admin');
    // The users table should show the admin user
    await expect(page.locator('table')).toBeVisible({ timeout: 15_000 });
    // Look for admin user name in the table
    await expect(
      page.getByText('Jean-Sylvain').or(page.getByText('jsboige')).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('admin settings page loads', async ({ page }) => {
    await page.goto('/admin/settings');
    // v0.11 moved admin settings into the settings window: they are no longer a
    // "Réglages" nav link but tabs. /admin/settings also redirects back to "/"
    // once the window opens — and on the way it briefly renders a legacy
    // <a href="/admin/settings">Réglages</a> for ~3 s. Asserting on that link
    // is a race (measured 2026-08-07: appears t=7.5s, gone t=10.7s), so wait
    // for the settled state instead.
    await page
      .waitForURL((url) => !url.pathname.startsWith('/admin/settings'), { timeout: 30_000 })
      .catch(() => {});
    // "Général" exists in BOTH the user and admin tab groups (2 matches →
    // strict-mode violation). "Authentification" is admin-only, so it also
    // proves we landed on the admin section and not just any settings tab.
    await expect(
      page.getByRole('tab', { name: /authentification|authentication/i })
    ).toBeVisible({ timeout: 15_000 });
  });

  test('view models in workspace', async ({ page }) => {
    await page.goto('/workspace/models');
    // Should see model list page with "Modèles" heading
    await expect(
      page.getByText('Modèles').or(page.getByText('Models')).first()
    ).toBeVisible({ timeout: 15_000 });
  });
});
