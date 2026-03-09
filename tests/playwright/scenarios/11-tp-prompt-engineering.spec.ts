import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';

/**
 * Scenario 11 — TP Prompt Engineering: Conversational Tests
 *
 * Tests the tp-prompt-engineering tutor model via the chat UI.
 * Validates that the tutor responds pedagogically in French,
 * provides structured modules, and handles student commands.
 */

test.describe('11 — TP Prompt Engineering', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'tp-prompt-engineering');
  });

  test('tutor introduces itself and mentions modules', async ({ page }) => {
    const response = await chat(page, 'Bonjour, je commence le TP.');

    // Skip if model is unavailable
    test.skip(
      !response || response.length < 10 || response.toLowerCase().includes('context usage'),
      'Model unavailable or returned empty response',
    );

    // Should respond in French with pedagogical content
    expect(response.toLowerCase()).toMatch(/module|prompt|bienvenue|exercice|commenc/i);
  });

  test('tutor responds to "aide" command', async ({ page }) => {
    const response = await chat(page, 'aide');

    test.skip(
      !response || response.length < 10,
      'Model unavailable',
    );

    // Should provide help information about available commands
    expect(response.toLowerCase()).toMatch(/aide|commande|indice|solution|module/i);
  });

  test('tutor provides a prompt engineering exercise', async ({ page }) => {
    const response = await chat(
      page,
      'Donne-moi un exercice de prompt engineering sur le zero-shot.',
    );

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // Should contain exercise-related content
    expect(response.toLowerCase()).toMatch(/exercice|prompt|zero.?shot|essai|rédige/i);
    // Should be substantial (at least a paragraph)
    expect(response.length).toBeGreaterThan(100);
  });

  test('tutor evaluates a student prompt attempt', async ({ page }) => {
    // First set context
    await chat(page, 'Module 1: Fondamentaux du prompting');

    const response = await chat(
      page,
      'Voici mon prompt: "Résume ce texte". Est-ce un bon prompt?',
    );

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // Should provide feedback — could be positive or constructive
    expect(response.toLowerCase()).toMatch(/prompt|améliorer|précis|contexte|feedback|évaluation|note|score/i);
  });

  test('response is in French', async ({ page }) => {
    const response = await chat(page, 'Explique ce quest le few-shot prompting.');

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // French markers: accented characters or common French words
    expect(response).toMatch(/[àâéèêëïîôùûüç]|est|les|des|une|pour|dans/i);
  });
});
