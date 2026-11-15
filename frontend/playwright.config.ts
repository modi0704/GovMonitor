import { defineConfig, devices } from '@playwright/test';

/**
 * Smoke and accessibility tests (P12.5, P12.7) against a running server with the demo data
 * (`make seed-demo-local`, then the backend serving the built frontend). SMOKE_BASE_URL points at
 * it; PW_CHROMIUM may name a preinstalled Chromium.
 */
const executablePath = process.env.PW_CHROMIUM || undefined;

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.SMOKE_BASE_URL ?? 'http://127.0.0.1:8000',
    trace: 'off',
    launchOptions: { executablePath },
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
    },
    {
      name: 'phone',
      use: { ...devices['Pixel 5'], viewport: { width: 360, height: 760 } },
    },
  ],
});
