import { test, expect, type Page } from '@playwright/test';
import { startNewChat, selectModel, sendMessage, waitForResponse } from '../helpers/chat';
import { CHAT, INTEGRATIONS } from '../helpers/selectors';

/**
 * 06 — Workspace tools via the Integrations menu.
 *
 * v0.10 change: the "Available Tools" wrench button only renders when the
 * chat has selectedToolIds — i.e. AFTER the user enables a workspace tool
 * from the Integrations ("+") menu. Admin-level MCP tool servers (sk-agent)
 * do NOT populate it; they flow through native function calling invisibly.
 * The old test selected a bare model and looked for the button directly,
 * which now always skips.
 */

/** Open the Integrations menu, drill into Tools, toggle the first tool on. */
async function enableFirstWorkspaceTool(page: Page): Promise<boolean> {
  const menuButton = page.locator(INTEGRATIONS.menuButton).first();
  if (!(await menuButton.isVisible({ timeout: 5_000 }).catch(() => false))) {
    return false;
  }
  await menuButton.click();

  // Root menu entry "Tools N" — absent if no workspace tools are installed
  const toolsEntry = page.getByRole('button', { name: INTEGRATIONS.toolsEntry }).first();
  if (!(await toolsEntry.isVisible({ timeout: 5_000 }).catch(() => false))) {
    await page.keyboard.press('Escape');
    return false;
  }
  await toolsEntry.click();

  // Tools tab lives in the same dropdown container (.max-h-72): the back
  // button is the first button, tool rows (name + Switch) follow.
  const backAndTools = page.locator('[class*="max-h-72"] button');
  const count = await backAndTools.count();
  if (count < 2) {
    await page.keyboard.press('Escape');
    return false;
  }
  await backAndTools.nth(1).click(); // first tool row (0 = back button)
  await page.keyboard.press('Escape');
  return true;
}

test.describe('06 — Workspace Tools (Integrations menu)', () => {
  test.beforeEach(async ({ page }) => {
    await startNewChat(page);
    await selectModel(page, 'gpt-4.1-mini');
  });

  test('integrations menu lists workspace tools', async ({ page }) => {
    const menuButton = page.locator(INTEGRATIONS.menuButton).first();
    await expect(menuButton).toBeVisible({ timeout: 10_000 });
    await menuButton.click();

    // Workspace has 4 installed tools (Sub Agent, YouTube Transcript,
    // Visuals Toolkit, LLM Council) — the Tools entry must be present.
    const toolsEntry = page.getByRole('button', { name: INTEGRATIONS.toolsEntry }).first();
    await expect(toolsEntry).toBeVisible({ timeout: 10_000 });
    await page.keyboard.press('Escape');
  });

  test('enabling a tool reveals the Available Tools button', async ({ page }) => {
    const enabled = await enableFirstWorkspaceTool(page);
    test.skip(!enabled, 'No workspace tools available to enable');

    // The wrench button with the enabled-tool counter should now be visible
    await expect(page.locator(CHAT.availableTools)).toBeVisible({ timeout: 10_000 });
  });

  test('chat completes with a tool enabled', async ({ page }) => {
    const enabled = await enableFirstWorkspaceTool(page);
    test.skip(!enabled, 'No workspace tools available to enable');

    await sendMessage(page, 'Say hello in one short sentence. Do not use any tool.');
    const response = await waitForResponse(page);
    expect(response.length).toBeGreaterThan(5);
  });
});
