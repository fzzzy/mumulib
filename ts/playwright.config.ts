import { defineConfig, devices } from '@playwright/test'

/**
 * Read environment variables from file.
 * https://github.com/motdotla/dotenv
 */
// import dotenv from 'dotenv';
// import path from 'path';
// dotenv.config({ path: path.resolve(__dirname, '.env') });

/**
 * See https://playwright.dev/docs/test-configuration.
 */
// The Python editors example, py/examples/editors.py, for its browser tests:
// a server of their own, not whatever make run is serving on 8001
const EDITORS_PORT = process.env.PLAYWRIGHT_EDITORS_PORT || '8124'

export default defineConfig({
  // Each spec sits beside the module it tests
  testDir: './src',
  /* Run tests in files in parallel */
  fullyParallel: true,
  workers: process.env.CI ? 1 : undefined,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: 'html',
  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in actions like `await page.goto('/')`. */
    baseURL: `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT || '8123'}`,

    /* Collect trace when retrying the failed test. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },

    // No firefox. Playwright 1.63.0 ships Firefox 155 as revision 1543,
    // and that build cannot start on macOS 26: every launch dies with
    // "Could not find profile folder." before any test runs. It is the
    // build, not the install -- a forced re-download reproduces it, so
    // does launching the binary by hand outside Playwright, and no
    // profile path or MOZ_* variable makes any difference. Revision 1538,
    // which Playwright 1.62.1 ships, starts fine on the same machine with
    // the same arguments.
    //
    // Linux is very likely unaffected, so CI was probably getting this
    // coverage. It is dropped anyway rather than left red locally, where
    // 12 permanent failures train you to ignore the result. Put the block
    // back when a Playwright release ships a Firefox newer than 1543.
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Test against mobile viewports. */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },

    /* Test against branded browsers. */
    // {
    //   name: 'Microsoft Edge',
    //   use: { ...devices['Desktop Edge'], channel: 'msedge' },
    // },
    // {
    //   name: 'Google Chrome',
    //   use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    // },
  ],

  webServer: [
    {
      command: 'npx vite',
      url: `http://127.0.0.1:${process.env.PLAYWRIGHT_PORT || '8123'}`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        PORT: process.env.PLAYWRIGHT_PORT || '8123',
        VITE_COVERAGE: 'true',
      },
    },
    {
      // In a directory of its own, emptied first: the example keeps its
      // objects in var/data there, and each run starts from none
      command: `rm -rf ../var/e2e/editors && mkdir -p ../var/e2e/editors && cd ../var/e2e/editors && uv run --project ../../../py --extra dev --locked uvicorn --app-dir ../../../py examples.editors:app --host 127.0.0.1 --port ${EDITORS_PORT}`,
      url: `http://127.0.0.1:${EDITORS_PORT}/editors/characters.json`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
  ],
})
