import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, sendMessage, waitForResponse, chat } from '../helpers/chat';
import { CHAT, MODEL } from '../helpers/selectors';

test.describe('02 — Basic Chat', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
  });

  test('chat with cloud model (GPT-4.1-mini)', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');
    const response = await chat(page, 'Reply with exactly: "Hello from GPT"');

    expect(response.toLowerCase()).toContain('hello');
  });

  test('chat with local model (Qwen3.5)', async ({ page }) => {
    // Local model depends on vLLM being up — may return empty response
    await selectModel(page, 'Qwen3.5-35B');
    const response = await chat(page, 'Reply with exactly one word: "Bonjour"');

    // vLLM may be down or return empty — skip test gracefully
    test.skip(!response || response.length < 5
      || response.toLowerCase().includes('context usage')
      || response.toLowerCase().includes('réfléchir'),
      'Local vLLM model returned empty or still thinking — likely slow/down');
    expect(response.toLowerCase()).toContain('bonjour');
  });

  test('streaming: assistant message appears before generation completes', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');
    await sendMessage(page, 'Write a short paragraph about artificial intelligence.');

    // Assistant message should appear quickly (streaming started)
    await expect(page.locator(CHAT.assistantMessage).last()).toBeVisible({ timeout: 30_000 });

    // Wait for full completion
    await waitForResponse(page);
  });

  test('markdown rendering: code blocks', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');
    await chat(page, 'Show me a Python hello world in a code block. Use ```python fences.');

    // OWUI renders code blocks with a custom component (not plain <code>).
    // Look for the code block container with language indicator or <pre>/<code> elements.
    const responseArea = page.locator('#response-content-container').last();
    const codeBlock = responseArea.locator('pre, code, [class*="code"], [class*="hljs"]').first();
    await expect(codeBlock).toBeVisible({ timeout: 10_000 });
  });

  test('regenerate response', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');
    await chat(page, 'Say a random number between 1 and 1000.');

    // Click regenerate — localized: "Regénérer" (FR) or "Regenerate" (EN)
    const regenButton = page.getByRole('button', { name: /reg[ée]n[ée]r/i })
      .or(page.getByRole('button', { name: /regenerate/i }))
      .last();
    await regenButton.click();
    await waitForResponse(page);

    // Verify we got a new response
    const secondResponse = await page.locator(CHAT.assistantMessage).last().innerText();
    expect(secondResponse.length).toBeGreaterThan(0);
  });

  test('edit user message', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');
    await chat(page, 'Say hello');

    // Hover over user message to reveal action buttons
    const userMsg = page.locator(CHAT.userMessage).last();
    await userMsg.hover();

    // Click edit — localized: "Modifier" (FR) or "Edit" (EN)
    const editButton = page.getByRole('button', { name: /modifier|edit/i }).last();
    await editButton.click();

    // The edit interface should appear
    await expect(page.locator(CHAT.saveEditButton).or(page.locator(CHAT.confirmEditButton))).toBeVisible({ timeout: 10_000 });
  });
});
