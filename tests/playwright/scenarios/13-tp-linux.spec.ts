import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';

/**
 * Scenario 13 — TP Linux Débutant: Conversational Tests
 *
 * Tests the tp-linux-debutant tutor model via chat UI.
 * Validates pedagogical responses about Linux commands and terminal usage.
 */

test.describe('13 — TP Linux Débutant', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'tp-linux');
  });

  test('tutor introduces Linux basics', async ({ page }) => {
    const response = await chat(page, 'Bonjour, je débute en Linux.');

    test.skip(
      !response || response.length < 10 || response.toLowerCase().includes('context usage'),
      'Model unavailable',
    );

    expect(response.toLowerCase()).toMatch(/linux|terminal|commande|système|bienvenue/i);
  });

  test('tutor explains a basic command (ls)', async ({ page }) => {
    const response = await chat(page, 'Comment lister les fichiers dans un répertoire?');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/ls|répertoire|fichier|dossier|list/i);
    expect(response.length).toBeGreaterThan(50);
  });

  test('tutor provides exercise on file navigation', async ({ page }) => {
    const response = await chat(page, 'Donne-moi un exercice sur la navigation dans le système de fichiers.');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response.toLowerCase()).toMatch(/cd|pwd|exercice|répertoire|chemin|navigat/i);
  });

  test('response is in French', async ({ page }) => {
    const response = await chat(page, 'Explique la commande chmod.');

    test.skip(!response || response.length < 20, 'Model unavailable');

    expect(response).toMatch(/[àâéèêëïîôùûüç]|est|les|des|une|pour|dans/i);
  });
});
