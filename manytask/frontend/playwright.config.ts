import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  outputDir: '../.tmp/playwright-results',
  workers: 1,
  timeout: 45_000,
  expect: {timeout: 10_000},
  reporter: [['list'], ['html', {outputFolder: '../.tmp/playwright-report', open: 'never'}]],
  use: {baseURL: process.env.MANYTASK_UI_BASE_URL || 'http://127.0.0.1:8082',
    viewport: {width: 1440, height: 1000}, trace: 'retain-on-failure', screenshot: 'only-on-failure'},
});
