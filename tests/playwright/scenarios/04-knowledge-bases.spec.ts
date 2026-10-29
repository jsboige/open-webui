import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, waitForResponse } from '../helpers/chat';
import { CHAT } from '../helpers/selectors';

test.describe('04 — Knowledge Bases (RAG)', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
  });

  test('attach a knowledge base via # shortcut', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');

    // Type # in the chat input to trigger KB selector
    // Must use keyboard.type() for TipTap editor (not fill())
    const chatInput = page.locator(CHAT.input);
    await chatInput.click();
    await page.keyboard.type('#');

    // A dropdown/popup with KB options should appear
    await expect(
      page.getByText('Bibliographie').or(page.getByText('Knowledge')).first()
    ).toBeVisible({ timeout: 10_000 });
  });

  test('chat with KB attached shows response', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');

    // Use # to attach "Bibliographie IA" knowledge base
    const chatInput = page.locator(CHAT.input);
    await chatInput.click();
    await page.keyboard.type('#');

    // Wait for KB list and select Bibliographie IA
    await page.getByText('Bibliographie').first().click({ timeout: 10_000 });

    // Re-focus the chat input after KB selection (focus may be lost)
    await chatInput.click();
    // Clear any remaining # text and type the question
    await page.keyboard.press('Backspace');
    await page.keyboard.type('Quels sont les principaux algorithmes de machine learning supervisé?', { delay: 10 });
    await page.keyboard.press('Enter');

    // Wait for user message
    await expect(page.locator(CHAT.userMessage).last()).toBeVisible({ timeout: 15_000 });

    // Wait for assistant response (RAG adds latency)
    const response = await waitForResponse(page);

    // The response should be non-trivial
    expect(response.length).toBeGreaterThan(50);
  });
});
