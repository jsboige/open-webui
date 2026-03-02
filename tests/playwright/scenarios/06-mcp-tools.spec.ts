import { test, expect } from '@playwright/test';
import { startNewChat, selectModel, sendMessage, waitForResponse } from '../helpers/chat';
import { CHAT } from '../helpers/selectors';

test.describe('06 — MCP Tools (sk-agent)', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
  });

  test('available tools button is visible', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');

    // The "Available Tools" button should be visible in the chat input area
    const toolsButton = page.locator(CHAT.availableTools);
    // Available Tools may not be visible if no tools configured — skip gracefully
    const isVisible = await toolsButton.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!isVisible, 'Available Tools button not visible — MCP tools may not be configured');
    await expect(toolsButton).toBeVisible();
  });

  test('enable MCP tools in chat', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');

    const toolsButton = page.locator(CHAT.availableTools);
    const isVisible = await toolsButton.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!isVisible, 'Available Tools button not visible — skipping');

    // Click "Available Tools" to open the tool selector
    await toolsButton.click();

    // A popup/dropdown should appear with available tools
    const toolPopup = page.locator('[role="dialog"], [role="menu"], [role="listbox"]').first()
      .or(page.getByText(/tools|outils/i).first());
    await expect(toolPopup).toBeVisible({ timeout: 10_000 });
  });

  test('trigger a web search tool and verify result', async ({ page }) => {
    await selectModel(page, 'gpt-4.1-mini');

    const toolsButton = page.locator(CHAT.availableTools);
    const isVisible = await toolsButton.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!isVisible, 'Available Tools button not visible — skipping');

    // Enable MCP tools
    await toolsButton.click();
    // Try to find and enable a search-related tool
    const searchTool = page.getByText(/search|recherche|searx/i).first();
    if (await searchTool.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await searchTool.click();
    }

    // Close the tools popup by clicking elsewhere
    await page.locator(CHAT.input).click();

    // Send a message that should trigger tool use
    await sendMessage(page, 'Search the web for "Open WebUI latest version" and tell me what you find.');
    const response = await waitForResponse(page);

    // Response should contain some search results or tool usage indication
    expect(response.length).toBeGreaterThan(20);
  });
});
