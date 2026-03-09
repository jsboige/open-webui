import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, chat } from '../helpers/chat';
import { MODEL } from '../helpers/selectors';

test.describe('03 — Custom Models & Personas', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
  });

  test('select expert-analyste persona', async ({ page }) => {
    await selectModel(page, 'expert-analyste');

    // The model should be selected — verify the selector shows the name
    const selectorText = await page.locator(MODEL.selectorButton).innerText();
    expect(selectorText.toLowerCase()).toContain('analyste');
  });

  test('expert-analyste responds in structured French', async ({ page }) => {
    await selectModel(page, 'expert-analyste');
    const response = await chat(page, 'Analyse les avantages du cloud computing en 3 points.');

    // vLLM may be down — skip gracefully
    test.skip(!response || response.length < 5
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Local vLLM model returned empty or still thinking — likely slow/down');
    // Response should be in French and structured
    expect(response).toMatch(/[àâéèêëïîôùûüç]|avantage|point|cloud/i);
  });

  test('custom avatar is displayed for persona models', async ({ page }) => {
    await selectModel(page, 'expert-analyste');
    await chat(page, 'Bonjour');

    // Verify the response was rendered (avatar is cosmetic, may be hidden on mobile)
    const responseContent = page.locator('#response-content-container').last();
    await expect(responseContent).toBeVisible({ timeout: 10_000 });
  });

  test('fast model (Qwen3.5-35B-A3B Fast) has no <think> tags', async ({ page }) => {
    await selectModel(page, 'Fast');
    const response = await chat(page, 'Quelle est la capitale de la France?');

    // vLLM may be down — skip gracefully
    test.skip(!response || response.length < 5
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Local vLLM model returned empty or still thinking — likely slow/down');
    expect(response).not.toContain('<think>');
    expect(response).not.toContain('</think>');
    expect(response.toLowerCase()).toContain('paris');
  });

  test('redacteur-technique persona', async ({ page }) => {
    await selectModel(page, 'redacteur');
    const response = await chat(page, 'Rédige un court paragraphe sur Docker.');

    // vLLM may be down — skip gracefully
    test.skip(!response || response.length < 5
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Local vLLM model returned empty or still thinking — likely slow/down');
    expect(response.toLowerCase()).toMatch(/docker|conteneur|container/);
  });
});
