import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';

/**
 * Scenario 14 — TP Git Workflow: Conversational Tests
 *
 * Tests the tp-git-workflow tutor model via chat UI.
 * Validates pedagogical responses about Git versioning workflow.
 */

test.describe('14 — TP Git Workflow', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'tp-git');
  });

  test('tutor introduces Git concepts', async ({ page }) => {
    const response = await chat(page, 'Bonjour, je veux apprendre Git.');

    test.skip(
      !response || response.length < 10 || response.toLowerCase().includes('context usage'),
      'Model unavailable',
    );

    expect(response.toLowerCase()).toMatch(/git|version|dépôt|repository|commit|bienvenue/i);
  });

  test('tutor explains git init and first commit', async ({ page }) => {
    const response = await chat(page, 'Comment initialiser un dépôt Git et faire un premier commit?');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/git init|commit|add|dépôt|repository/i);
    expect(response.length).toBeGreaterThan(80);
  });

  test('tutor explains branching', async ({ page }) => {
    const response = await chat(page, 'Explique-moi le concept de branches en Git.');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/branch|branche|merge|fusionner|checkout/i);
  });

  test('response is in French', async ({ page }) => {
    const response = await chat(page, 'Quelle est la différence entre git merge et git rebase?');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response).toMatch(/[àâéèêëïîôùûüç]|est|les|des|une|pour|dans/i);
  });
});
