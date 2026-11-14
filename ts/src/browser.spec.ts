import { test, expect } from './coverage.fixture'

// The library's browser build as the Python server serves it, at
// /mumulib/browser/, imported by a page of the browser fixture,
// py/fixtures/browser.py: make dist copies the build into the package, as
// the wheel ships it. It is the built library, not src/, so it adds nothing
// to the coverage of src/ -- the test is that the build works where it ships.
const SITE = 'http://127.0.0.1:5765'

test('a page served by Python imports the library from it', async ({
  page,
}) => {
  const modules: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'script') modules.push(request.url())
  })
  await page.goto(`${SITE}/`)
  await page.getByPlaceholder('Your name').fill('Ada')
  await expect(page.locator('[data-slot="greeting"]')).toHaveText('Ada')
  // Every module came from the server's own /mumulib/browser/
  expect(modules).toContain(`${SITE}/mumulib/browser/mumulib.mjs`)
  for (const url of modules) {
    expect(url.startsWith(`${SITE}/mumulib/browser/`), url).toBe(true)
  }
})
