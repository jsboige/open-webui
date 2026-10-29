import { test, expect } from '@playwright/test';

test.describe('09 — Workspace', () => {
  test('list knowledge bases', async ({ page }) => {
    await page.goto('/workspace/knowledge');
    // Should see at least "Bibliographie IA" KB
    await expect(
      page.getByText('Bibliographie').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test('list installed functions', async ({ page }) => {
    // v0.8.7: functions are under /workspace/skills or /admin/functions
    await page.goto('/admin/functions');
    // Should see function list (Fonctions header or function names)
    await expect(
      page.getByText('Fonctions').or(page.getByText('Functions')).first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test('list saved prompts', async ({ page }) => {
    await page.goto('/workspace/prompts');
    // Should see at least one prompt (7 prompts installed on myia)
    await expect(
      page.getByText('Prompts').first()
    ).toBeVisible({ timeout: 15_000 });
  });

  test('list custom models', async ({ page }) => {
    await page.goto('/workspace/models');
    // Should see custom models like expert-analyste, redacteur-technique
    await expect(
      page.getByText('analyste').or(page.getByText('rédacteur')).or(page.getByText('redacteur')).first()
    ).toBeVisible({ timeout: 15_000 });
  });
});
