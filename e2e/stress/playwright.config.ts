import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.BASE_URL || 'http://localhost';
const storageState = path.resolve(__dirname, '../playwright/.auth/state.json');

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  globalSetup: require.resolve('../playwright/global-setup'),
  outputDir: 'test-results',
  use: {
    baseURL,
    storageState,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name: 'stress-chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
});
