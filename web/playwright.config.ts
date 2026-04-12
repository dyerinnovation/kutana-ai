import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for Kutana web E2E tests.
 *
 * Prerequisites (dev stack):
 *   - Frontend dev server:  cd web && pnpm dev        (http://localhost:5173)
 *   - API server:           uv run uvicorn ...         (http://localhost:8000)
 *   - Agent gateway WS:    (http://localhost:8003)
 *   - LiveKit OSS server:   (optional — see LIVEKIT_URL env)
 *
 * Set PLAYWRIGHT_BASE_URL to override the frontend base (e.g. for staging).
 */
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 40_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  // Serial: tests share meeting state; parallel would race on the same DB.
  workers: 1,
  reporter: process.env.CI ? 'github' : 'list',

  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:5173',
    // Use a fake audio device so getUserMedia doesn't fail in headless Chrome.
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        '--use-file-for-fake-audio-capture=/dev/zero',
      ],
    },
    permissions: ['microphone'],
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Reuse an existing dev server; spin one up if not already running.
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 30_000,
  },
});
