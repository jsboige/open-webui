import { defineConfig, devices } from '@playwright/test';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Load .env from repo root (contains MYIA_URL, MYIA_EMAIL, etc.)
dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const MYIA_URL = process.env.MYIA_URL || 'https://open-webui.myia.io';
const EPF_URL = process.env.EPF_URL || 'https://epf.open-webui.myia.io';

export default defineConfig({
  testDir: './scenarios',
  fullyParallel: false, // Sequential — LLM responses are slow
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Single worker — avoid concurrent LLM load
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
  ],

  use: {
    screenshot: 'only-on-failure',
    video: 'on-first-retry',
    trace: 'on-first-retry',
    ignoreHTTPSErrors: true, // Self-signed certs on LAN
    locale: 'fr-FR',
  },

  // Global timeout: 2 min per test (LLM responses can be slow)
  timeout: 120_000,
  expect: { timeout: 10_000 },

  projects: [
    // --- Setup: authenticate once, reuse session ---
    {
      name: 'myia-setup',
      testDir: './fixtures',
      testMatch: /auth\.setup\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: MYIA_URL,
      },
    },
    {
      name: 'epf-setup',
      testDir: './fixtures',
      testMatch: /auth\.setup\.ts/,
      use: {
        ...devices['Desktop Chrome'],
        baseURL: EPF_URL,
      },
    },

    // --- Main test projects ---
    {
      name: 'myia',
      dependencies: ['myia-setup'],
      use: {
        ...devices['Desktop Chrome'],
        baseURL: MYIA_URL,
        storageState: path.resolve(__dirname, '.auth/myia.json'),
      },
    },
    {
      name: 'epf',
      dependencies: ['epf-setup'],
      use: {
        ...devices['Desktop Chrome'],
        baseURL: EPF_URL,
        storageState: path.resolve(__dirname, '.auth/epf.json'),
      },
    },
  ],
});
