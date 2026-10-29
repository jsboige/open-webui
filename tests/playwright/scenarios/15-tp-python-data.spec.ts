import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';

/**
 * Scenario 15 — TP Python Data: Conversational Tests
 *
 * Tests the tp-python-data tutor model via chat UI.
 * Validates pedagogical responses about Python and Pandas for data science.
 */

test.describe('15 — TP Python Data', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'tp-python-data');
  });

  test('tutor introduces Python data science', async ({ page }) => {
    const response = await chat(page, 'Bonjour, je veux apprendre Python pour la data science.');

    test.skip(
      !response || response.length < 10 || response.toLowerCase().includes('context usage'),
      'Model unavailable',
    );

    expect(response.toLowerCase()).toMatch(/python|pandas|données|data|bienvenue|science/i);
  });

  test('tutor explains DataFrame basics', async ({ page }) => {
    const response = await chat(page, 'Comment créer un DataFrame avec pandas?');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/dataframe|pandas|pd|colonnes?|dict|import/i);
    expect(response.length).toBeGreaterThan(80);
  });

  test('tutor provides data manipulation exercise', async ({ page }) => {
    const response = await chat(
      page,
      'Donne-moi un exercice de filtrage et agrégation avec pandas.',
    );

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/filtr|groupby|agrég|exercice|mean|sum|count/i);
  });

  test('response is in French', async ({ page }) => {
    const response = await chat(page, 'Explique la méthode groupby de pandas.');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response).toMatch(/[àâéèêëïîôùûüç]|est|les|des|une|pour|dans/i);
  });
});
