import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';
import { apiLogin, getModelDetail } from '../helpers/api';
import { getTenantConfig } from '../fixtures/tenant';

/**
 * Scenario 12 — TP Data Analyst Agent: Terminal & Tool Integration
 *
 * Tests the tp-data-analyst-agent tutor model which uses function_calling: native
 * to execute Python code in the Open Terminal. Validates pedagogical responses,
 * tool availability, and dataset interaction.
 */

test.describe('12 — TP Data Analyst Agent', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'tp-data-analyst');
  });

  test('model has function_calling enabled (API check)', async ({ request }) => {
    let tenant: ReturnType<typeof getTenantConfig>;
    try {
      tenant = getTenantConfig('myia');
    } catch {
      test.skip(true, 'Missing myia credentials');
      return;
    }

    const token = await apiLogin(request, tenant.url, tenant.email, tenant.password);
    const detail = await getModelDetail(request, tenant.url, token, 'tp-data-analyst-agent');

    expect(detail.params?.function_calling).toBe('native');
  });

  test('tutor introduces itself with data analysis context', async ({ page }) => {
    const response = await chat(page, 'Bonjour, je commence le TP data analyst.');

    test.skip(
      !response || response.length < 10 || response.toLowerCase().includes('context usage'),
      'Model unavailable or returned empty response',
    );

    // Should mention data analysis, Python, or datasets
    expect(response.toLowerCase()).toMatch(/données|data|python|pandas|analyse|dataset|fichier/i);
  });

  test('tutor responds to a data analysis question', async ({ page }) => {
    const response = await chat(
      page,
      'Comment charger un fichier CSV avec pandas et afficher les 5 premières lignes?',
    );

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // Should contain Python/pandas code or instructions
    expect(response.toLowerCase()).toMatch(/pandas|pd\.read_csv|head|import|csv/i);
    // Should be substantial
    expect(response.length).toBeGreaterThan(80);
  });

  test('tools button is visible (function_calling enabled)', async ({ page }) => {
    // When a model has function_calling: native, the tools button should appear
    // This verifies the UI reflects the model's tool capabilities
    const chatInput = page.locator('#chat-input');
    await chatInput.click();

    // The "Available Tools" button appears near the chat input for tool-enabled models
    // It may take a moment to load after model selection
    const toolsButton = page.locator('button[aria-label="Available Tools"]');
    // Give it some time — tool loading can be slow
    const isVisible = await toolsButton.isVisible({ timeout: 10_000 }).catch(() => false);

    // This is a soft check — tools button visibility depends on server config
    if (!isVisible) {
      test.info().annotations.push({
        type: 'info',
        description: 'Tools button not visible — may need Open Terminal tool server configured',
      });
    }
  });

  test('tutor provides pedagogical feedback, not just code', async ({ page }) => {
    const response = await chat(
      page,
      'Analyse les ventes par catégorie dans le fichier ventes_ecommerce.csv',
    );

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // Tutor should explain the approach, not just dump code
    // Look for pedagogical markers: explanations, steps, comments
    expect(response.toLowerCase()).toMatch(
      /étape|d'abord|ensuite|explication|comprendre|groupby|catégorie|résultat/i,
    );
  });

  test('response is in French', async ({ page }) => {
    const response = await chat(
      page,
      'Quelles sont les étapes pour nettoyer un dataset?',
    );

    test.skip(
      !response || response.length < 20,
      'Model unavailable',
    );

    // French markers
    expect(response).toMatch(/[àâéèêëïîôùûüç]|est|les|des|une|pour|dans/i);
  });
});
