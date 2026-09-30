import { test as base } from '@playwright/test'
import * as fs from 'node:fs'
import * as path from 'node:path'

// Where each test's page leaves what it ran, for nyc. The dev server the
// tests start instruments src/, so the pages carry istanbul's counters.
const COVERAGE_DIR = path.join(__dirname, '..', '.nyc_output')

// `test`, keeping each page's counters once the test is done with it
export const test = base.extend<{ saveCoverage: void }>({
  saveCoverage: [
    async ({ page }, use, testInfo) => {
      await use()
      const coverage: unknown = await page.evaluate(
        () =>
          (window as unknown as { __coverage__?: unknown }).__coverage__ ?? null
      )
      if (coverage) {
        fs.mkdirSync(COVERAGE_DIR, { recursive: true })
        const name =
          `${testInfo.project.name}-${testInfo.titlePath.join('-')}`.replace(
            /[^A-Za-z0-9_.-]+/g,
            '_'
          )
        fs.writeFileSync(
          path.join(COVERAGE_DIR, `${name}.json`),
          JSON.stringify(coverage)
        )
      }
    },
    { auto: true },
  ],
})

export { expect } from '@playwright/test'
