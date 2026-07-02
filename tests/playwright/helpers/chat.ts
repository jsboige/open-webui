import { type Page, expect } from '@playwright/test';
import { CHAT, MODEL, NAV } from './selectors';

/**
 * Start a new chat by navigating to / (more reliable than clicking sidebar button
 * which may not be visible when sidebar is collapsed).
 */
export async function startNewChat(page: Page): Promise<void> {
  await page.goto('/');
  await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });
}

/**
 * Select a model by searching for its name in the model selector dropdown.
 * The search input placeholder is localized — use role-based locator.
 */
export async function selectModel(page: Page, modelName: string): Promise<void> {
  await page.locator(MODEL.selectorButton).first().click();
  // Wait for the model listbox to appear
  await expect(page.locator(MODEL.modelListbox)).toBeVisible({ timeout: 10_000 });
  // Type in the search input (v0.10: stable #model-search-input, with fallbacks)
  const searchInput = page.locator(MODEL.searchInput).first();
  await searchInput.fill(modelName);
  // Click the first matching model option
  await page.locator(MODEL.modelOption).first().click({ timeout: 10_000 });
  // Ensure the dropdown is closed before proceeding
  await expect(page.locator(MODEL.modelListbox)).not.toBeVisible({ timeout: 5_000 });
}

/**
 * Send a message in the chat and wait for the user message to appear.
 * OWUI uses a TipTap/ProseMirror rich text editor (not a standard textarea).
 * Must use keyboard.type() instead of fill() to trigger proper events,
 * then Enter to submit (Shift+Enter for newlines in OWUI).
 */
export async function sendMessage(page: Page, message: string): Promise<void> {
  const chatInput = page.locator(CHAT.input);
  await chatInput.click();
  // Clear any existing text and type the message character by character
  // to properly trigger TipTap input events
  await page.keyboard.type(message, { delay: 10 });
  // Submit via Enter key (OWUI default: Enter sends, Shift+Enter for newline)
  await page.keyboard.press('Enter');
  // Wait for user message to appear
  await expect(page.locator(CHAT.userMessage).last()).toBeVisible({ timeout: 15_000 });
}

/**
 * Wait for the assistant's response to complete.
 * In v0.8.7, completion is detected by the "Toggle status history" button
 * which shows token usage stats (only appears after streaming ends).
 * Uses a long timeout since LLM responses can be slow.
 */
export async function waitForResponse(page: Page, timeoutMs = 120_000): Promise<string> {
  // Wait for the assistant message to start appearing
  await expect(page.locator(CHAT.assistantMessage).last()).toBeVisible({ timeout: 30_000 });

  // Wait for response to fully complete.
  // During thinking: status toggle shows "Token" but content container is empty.
  // After completion: #response-content-container has rendered markdown text.
  // Poll until the content container has meaningful text.
  await page.waitForFunction(
    () => {
      // Look for the LAST response-content-container (there may be multiple in history)
      const containers = document.querySelectorAll('#response-content-container');
      const last = containers[containers.length - 1];
      return last && last.textContent && last.textContent.trim().length > 2;
    },
    undefined,
    { timeout: timeoutMs, polling: 1000 },
  ).catch(() => {});

  // Small delay to let Svelte fully render after the last token
  await page.waitForTimeout(500);

  // Return content from the response container
  const contentContainer = page.locator(CHAT.assistantMessage).last()
    .locator('#response-content-container');
  const content = await contentContainer.innerText({ timeout: 5_000 }).catch(() => '');
  if (content.trim()) {
    return content.trim();
  }
  // Fallback: return the full assistant message text (includes model name + status)
  return await page.locator(CHAT.assistantMessage).last().innerText();
}

/**
 * Send a message and wait for the full response. Returns the assistant's text.
 */
export async function chat(page: Page, message: string, timeoutMs = 120_000): Promise<string> {
  await sendMessage(page, message);
  return await waitForResponse(page, timeoutMs);
}

/**
 * Check if a service is accessible by making a HEAD request.
 * Used for conditional skip of service-dependent tests.
 */
export async function isServiceAvailable(page: Page, url: string): Promise<boolean> {
  try {
    const response = await page.request.get(url, { timeout: 5_000 });
    return response.ok();
  } catch {
    return false;
  }
}
