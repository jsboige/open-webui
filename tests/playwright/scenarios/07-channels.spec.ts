import { test, expect } from '@playwright/test';
import { MODEL } from '../helpers/selectors';

test.describe('07 — Channels', () => {
  test('navigate to channels section', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator(MODEL.selectorButton).first()).toBeVisible({ timeout: 15_000 });

    // Try to find Channels link in navigation
    const channelsLink = page.getByRole('link', { name: /channels|canaux/i }).first();
    if (await channelsLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
      await channelsLink.click();
      await expect(page).toHaveURL(/channel/i, { timeout: 10_000 });
    } else {
      // Try direct navigation
      await page.goto('/channels');
      await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });
    }
  });

  test('post a message in a channel', async ({ page }) => {
    // Navigate to channels
    await page.goto('/channels');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    // Look for an existing channel and click it
    const channelItem = page.locator('a[href*="/channels/"]').first();
    const hasChannels = await channelItem.isVisible({ timeout: 5_000 }).catch(() => false);
    test.skip(!hasChannels, 'No channels available to test');

    await channelItem.click();
    await page.waitForTimeout(1000);

    // Find the message input in the channel (TipTap editor or textarea)
    const messageInput = page.locator('#chat-input, [contenteditable="true"]').last();
    await messageInput.click();

    const testMessage = `Playwright test — ${new Date().toISOString()}`;
    await page.keyboard.type(testMessage, { delay: 10 });
    await page.keyboard.press('Enter');

    // Verify the message appears
    await expect(page.getByText(testMessage).first()).toBeVisible({ timeout: 10_000 });
  });
});
