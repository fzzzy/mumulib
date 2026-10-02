import { test, expect, type Page } from './coverage.fixture'

// The notes example, py/examples/notes.py: a Vite page, ts/pages/notes,
// served by Python as Vite made it. Once in development, its TypeScript from
// the pages' Vite dev server, and once in production, built and served by
// Python under /mumulib-vite/ (playwright.config). Chromium and WebKit run at once
// against each, so each adds and removes notes of its own. The page binds
// the notes with sync.bind, so every page open shows each change.
const MODES = {
  development: 'http://127.0.0.1:8125',
  production: 'http://127.0.0.1:8126',
}
const VITE = 'http://127.0.0.1:5757'

async function add(page: Page, text: string) {
  await page.locator('input[name="text"]').fill(text)
  await page.getByRole('button', { name: 'Add' }).click()
  await expect(page.locator('#notes')).toContainText(text)
}

for (const [mode, server] of Object.entries(MODES)) {
  test.describe(`The notes example, in ${mode}`, () => {
    test('the page shows the notes, and adds one', async ({ page }, info) => {
      await page.goto(`${server}/`)
      await expect(page.locator('#notes')).toContainText(
        'Write the Vite example'
      )
      const text = `Added in ${info.project.name} at ${Date.now()}`
      await add(page, text)
      // Kept: the Persist's file has it
      const notes = await (
        await page.request.get(`${server}/notes.json`)
      ).json()
      expect(notes).toContain(text)
    })

    test('a note is removed, and the others keep their places', async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      const text = `Removed in ${info.project.name} at ${Date.now()}`
      await add(page, text)
      const item = page.locator('#notes li', { hasText: text })
      await item.getByRole('button', { name: 'Remove' }).click()
      await expect(page.locator('#notes')).not.toContainText(text)
      const notes = await (
        await page.request.get(`${server}/notes.json`)
      ).json()
      expect(notes[0]).toBe('Write the Vite example')
      expect(notes).toContain(null)
    })

    test('another page open shows each change, bound, never reloaded', async ({
      browser,
    }, info) => {
      const writer = await browser.newPage()
      const watcher = await browser.newPage()
      await watcher.goto(`${server}/`)
      await expect(watcher.locator('body[data-loaded]')).toBeAttached()
      await watcher.evaluate(() => {
        ;(window as Window & { kept?: boolean }).kept = true
      })
      await writer.goto(`${server}/`)
      const text = `Watched in ${info.project.name} at ${Date.now()}`
      await add(writer, text)
      // The watcher's state was fetched again, on the announcement
      await expect(watcher.locator('#notes')).toContainText(text)
      // And removed from the watcher, the writer sees it go
      const item = watcher.locator('#notes li', { hasText: text })
      await item.getByRole('button', { name: 'Remove' }).click()
      await expect(writer.locator('#notes')).not.toContainText(text)
      const kept = await watcher.evaluate(
        () => (window as Window & { kept?: boolean }).kept
      )
      expect(kept, 'the watcher never reloaded').toBe(true)
      await writer.close()
      await watcher.close()
    })
  })
}

test("in development the TypeScript, and hot reloading, are Vite's", async ({
  page,
}) => {
  const scripts: string[] = []
  const sockets: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'script') scripts.push(request.url())
  })
  page.on('websocket', (socket) => sockets.push(socket.url()))
  await page.goto(`${MODES.development}/`)
  await expect(page.locator('body[data-loaded]')).toBeAttached()
  expect(page.url()).toBe(`${MODES.development}/`)
  expect(scripts).toContain(`${VITE}/mumulib-vite/notes/main.ts`)
  expect(scripts.every((url) => url.startsWith(`${VITE}/mumulib-vite/`))).toBe(
    true
  )
  await expect
    .poll(() => sockets)
    .toContainEqual(
      expect.stringMatching(/^ws:\/\/127\.0\.0\.1:5757\/mumulib-vite\//)
    )
})

test("in production it is all Python's, built, and cached", async ({
  page,
}) => {
  const scripts: string[] = []
  const sockets: string[] = []
  page.on('request', (request) => {
    if (request.resourceType() === 'script') scripts.push(request.url())
  })
  page.on('websocket', (socket) => sockets.push(socket.url()))
  await page.goto(`${MODES.production}/`)
  await expect(page.locator('body[data-loaded]')).toBeAttached()
  expect(scripts).toHaveLength(1)
  expect(scripts[0]).toMatch(
    /^http:\/\/127\.0\.0\.1:8126\/mumulib-vite\/assets\/.+\.js$/
  )
  expect(sockets).toEqual([])
  const first = await page.request.get(scripts[0])
  const etag = first.headers()['etag']
  expect(first.headers()['cache-control']).toBe('no-cache')
  const again = await page.request.get(scripts[0], {
    headers: { 'if-none-match': etag },
  })
  expect(again.status()).toBe(304)
})
