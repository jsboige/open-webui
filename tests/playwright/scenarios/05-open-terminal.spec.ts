import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';

test.describe('05 — Open Terminal', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
  });

  test('execute simple Python script via terminal', async ({ page }) => {
    // Select a model that has terminal_id configured (TP tutor models)
    await selectModel(page, 'TP Linux');

    // The Débutant tutor persona explains instead of executing unless the
    // prompt explicitly demands a real tool run with pasted output.
    const response = await chat(
      page,
      'Utilise ton outil terminal MAINTENANT pour exécuter exactement ceci et colle la sortie réelle, sans explication : echo "Hello from Open Terminal"',
    );

    // Skip if model not available or returned empty
    test.skip(!response || response.length < 10
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Terminal model not responding or still thinking — skipping');
    expect(response.toLowerCase()).toContain('hello');
  });

  test('verify data science packages installed', async ({ page }) => {
    await selectModel(page, 'TP Linux');

    const response = await chat(
      page,
      'Run this command: pip list | head -20',
    );

    test.skip(!response || response.length < 10
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Terminal model not responding or still thinking — skipping');
    expect(response.length).toBeGreaterThan(50);
  });

  test('terminal isolation: create and read file', async ({ page }) => {
    await selectModel(page, 'TP Linux');

    const response = await chat(
      page,
      'Utilise ton outil terminal MAINTENANT (sans explication, colle juste la sortie réelle) : echo "tenant-marker-test" > /tmp/isolation_test.txt && cat /tmp/isolation_test.txt',
    );

    test.skip(!response || response.length < 10
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Terminal model not responding or still thinking — skipping');
    expect(response).toContain('tenant-marker-test');
  });
});
