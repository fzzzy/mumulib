import { test, expect, type Locator, type Page } from './coverage.fixture'

// The notes example, py/fixtures/notes.py: a Vite page, ts/pages/notes,
// served by Python as Vite made it. Once in development, its TypeScript from
// the pages' Vite dev server, and once in production, built and served by
// Python under /mumulib-vite/ (playwright.config). Chromium and WebKit run at once
// against each, so each adds, moves and removes notes of its own. The page
// binds the notes and who is here with sync.bind, so every page open shows
// each change, and each player.
const MODES = {
  development: 'http://127.0.0.1:5762',
  production: 'http://127.0.0.1:5763',
}
const VITE = 'http://127.0.0.1:5757'

type Note = { text: string; order: string }

// One test at a time in each browser: every page open holds a change
// stream, and a browser lets six connections at most reach one server --
// WebKit, across all of Playwright's pages -- so more pages than that wait
// on each other's streams for good. Chromium and WebKit still run at once,
// against the same servers, so each is another player to the other
test.describe.configure({ mode: 'default' })

async function add(page: Page, text: string) {
  await page.getByRole('textbox', { name: 'A note' }).fill(text)
  await page.getByRole('button', { name: 'Add' }).click()
  await expect(page.locator('#notes')).toContainText(text)
}

// A row focused, as the keyboard is about to act on it: directly, rather
// than clicked -- the other tests move and remove rows in the same list, and
// a click can land on whichever row has just moved under it
async function focus(page: Page, text: string) {
  await row(page, text).focus()
  await expect(row(page, text)).toBeFocused()
}

function row(page: Page, text: string) {
  return page.locator('#notes note-row', { hasText: text })
}

// The notes, as the server has them, by text
async function kept(page: Page, server: string): Promise<Record<string, Note>> {
  const notes = (await (
    await page.request.get(`${server}/notes.json`)
  ).json()) as Record<string, Note>
  return Object.fromEntries(
    Object.values(notes).map((note) => [note.text, note]),
  )
}

// The texts shown, in order, of those named
async function shown(page: Page, texts: string[]): Promise<string[]> {
  const all = await page.locator('#notes note-row .text').allTextContents()
  return all.filter((text) => texts.includes(text))
}

// Drag one element onto another, as a mouse would: pressed, moved in steps,
// let go. The other tests move rows in the same list, and one can move
// under the pointer as it is pressed: a row grabbed that is not the one
// meant is put back where it was -- let go where it started, it goes
// nowhere, and nothing is written -- and the drag tried again
async function dragTo(page: Page, from: Locator, to: Locator, above = false) {
  for (let attempt = 0; attempt < 5; attempt++) {
    await from.scrollIntoViewIfNeeded()
    await to.scrollIntoViewIfNeeded()
    const start = (await from.boundingBox())!
    const x = start.x + start.width / 2
    const y = start.y + start.height / 2
    const under = await from.evaluate(
      (element, [px, py]) =>
        element.contains(document.elementFromPoint(px!, py!)),
      [x, y],
    )
    if (!under) continue
    await page.mouse.move(x, y)
    await page.mouse.down()
    await page.mouse.move(x, y + 6)
    if (
      !(await from.evaluate((element) =>
        element.classList.contains('dragging'),
      ))
    ) {
      await page.mouse.move(x, y)
      await page.mouse.up()
      continue
    }
    const end = (await to.boundingBox())!
    const toY = above ? end.y + 2 : end.y + end.height / 2
    await page.mouse.move(end.x + end.width / 2, toY, { steps: 8 })
    await page.mouse.up()
    return
  }
  throw new Error('never grabbed the row meant')
}

for (const [mode, server] of Object.entries(MODES)) {
  test.describe(`The notes example, in ${mode}`, () => {
    test('the page shows the notes, and adds one, kept', async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      await expect(page.locator('#notes')).toContainText(
        'Run it built, in production',
      )
      const text = `Added in ${info.project.name} at ${Date.now()}`
      await add(page, text)
      // Kept: the Persist's file has it
      expect((await kept(page, server))[text]).toBeDefined()
      // A click focuses a note -- the first, which no test moves
      await row(page, 'Write the Vite example').click()
      await expect(row(page, 'Write the Vite example')).toBeFocused()
    })

    test('a note is edited from the keyboard, and Escape keeps it', async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      const text = `Edited in ${info.project.name} at ${Date.now()}`
      await add(page, text)
      await focus(page, text)
      await page.keyboard.press('Enter')
      await page.keyboard.type(' -- changed', { delay: 0 })
      await page.keyboard.press('Escape')
      await expect(row(page, text).locator('.text')).toHaveText(text)
      await page.keyboard.press('Enter')
      await page.locator('note-row .edit:visible').fill(`${text}!`)
      await page.keyboard.press('Enter')
      await expect(row(page, `${text}!`)).toBeFocused()
      expect((await kept(page, server))[`${text}!`]).toBeDefined()
    })

    test('a note is moved from the keyboard, its order alone written', async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      const [a, b] = ['A', 'B'].map(
        (n) => `${n} moved in ${info.project.name} at ${Date.now()}`,
      ) as [string, string]
      await add(page, a)
      await add(page, b)
      const before = await kept(page, server)
      // Up past A: other tests add notes at the end as this one runs, and
      // one may be between them
      await focus(page, b)
      await expect
        .poll(async () => {
          if ((await shown(page, [a, b]))[0] !== b) {
            await page.keyboard.press('Alt+ArrowUp')
          }
          return shown(page, [a, b])
        })
        .toEqual([b, a])
      // Still focused, and only b's order changed
      await expect(row(page, b)).toBeFocused()
      const after = await kept(page, server)
      expect(after[a]).toEqual(before[a])
      expect(after[b]!.order < after[a]!.order).toBe(true)
      // ↓ moves the focus to the note below: A, or another test's note
      // moved between them a moment ago
      await page.keyboard.press('ArrowDown')
      await expect(row(page, b)).not.toBeFocused()
      await expect(page.locator('note-row:focus')).toHaveCount(1)
      // And Delete removes what it is on
      await focus(page, a)
      await page.keyboard.press('Delete')
      await expect(row(page, a)).toHaveCount(0)
      // The focus on the note after it: another test's, as like as not
      await expect(page.locator('note-row:focus')).toHaveCount(1)
    })

    test('a note is dragged into place, and to the trash', async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      const [a, b] = ['A', 'B'].map(
        (n) => `${n} dragged in ${info.project.name} at ${Date.now()}`,
      ) as [string, string]
      await add(page, a)
      await add(page, b)
      await dragTo(page, row(page, b), row(page, a), true)
      await expect.poll(() => shown(page, [a, b])).toEqual([b, a])
      await dragTo(
        page,
        row(page, a),
        page.getByRole('button', { name: 'Trash' }),
      )
      await expect(row(page, a)).toHaveCount(0)
      expect((await kept(page, server))[a]).toBeUndefined()
    })

    test('another page shows each change and each player, never reloaded', async ({
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
      await expect(watcher.locator('#notes')).toContainText(text)
      // The writer is in the watcher's key, by the name it gave itself
      const name = (await writer
        .locator('#players .you')
        .textContent())!.replace(' (you)', '')
      await expect(watcher.locator('#players')).toContainText(name)
      // At the note it focuses: outlined there, on the watcher's page
      await focus(writer, text)
      await expect(row(watcher, text)).toHaveAttribute('style', /box-shadow/)
      // Removed from the watcher, the writer sees it go
      await focus(watcher, text)
      await watcher.keyboard.press('Delete')
      await expect(writer.locator('#notes')).not.toContainText(text)
      const kept = await watcher.evaluate(
        () => (window as Window & { kept?: boolean }).kept,
      )
      expect(kept, 'the watcher never reloaded').toBe(true)
      // And gone elsewhere, the writer is gone from the key: its page said
      // so as it went. (Closing it would too, in a browser, but Playwright's
      // Chromium does not send a closing page's keepalive requests.)
      await writer.goto('about:blank')
      await expect(watcher.locator('#players')).not.toContainText(name)
      await writer.close()
      await watcher.close()
    })

    test("someone else's change of what is edited is a conflict, decided", async ({
      page,
    }, info) => {
      await page.goto(`${server}/`)
      const text = `Clashed in ${info.project.name} at ${Date.now()}`
      await add(page, text)
      const id = Object.entries(
        (await (
          await page.request.get(`${server}/notes.json`)
        ).json()) as Record<string, Note>,
      ).find(([, note]) => note.text === text)![0]
      const theirs = (value: string) =>
        page.request.put(`${server}/notes/${id}/text.json`, {
          data: JSON.stringify(value),
          headers: { 'content-type': 'application/json' },
        })

      // Theirs: the field locked, shaken, and theirs kept
      await focus(page, text)
      await page.keyboard.press('Enter')
      await page.locator('note-row .edit:visible').fill('mine, 1')
      await theirs(`theirs 1 ${text}`)
      const field = page.locator('note-row .edit:visible')
      await expect(field).toHaveAttribute('readonly', '')
      await expect(field).toHaveClass(/shake/)
      await page.getByRole('button', { name: 'Theirs' }).click()
      await expect(row(page, `theirs 1 ${text}`).locator('.text')).toHaveText(
        `theirs 1 ${text}`,
      )

      // Mine: what was typed, kept over theirs
      await focus(page, `theirs 1 ${text}`)
      await page.keyboard.press('Enter')
      await page.locator('note-row .edit:visible').fill(`mine ${text}`)
      await theirs(`theirs 2 ${text}`)
      await page.getByRole('button', { name: 'Mine' }).click()
      await expect(row(page, `mine ${text}`)).toHaveCount(1)
      expect((await kept(page, server))[`mine ${text}`]).toBeDefined()
    })
  })
}

test("in development the TypeScript, and hot reloading, are Vite's, through Python", async ({
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
  // Vite's modules, asked of the page's own server, which passes them on:
  // one origin, and Vite reached by nothing else
  const own = `${MODES.development}/mumulib-vite/`
  expect(scripts).toContain(`${own}notes/main.ts`)
  expect(scripts.every((url) => url.startsWith(own))).toBe(true)
  expect(scripts.some((url) => url.startsWith(VITE))).toBe(false)
  // And hot reloading, its websocket too, which Vite answers through it
  await expect
    .poll(() => sockets)
    .toContainEqual(
      expect.stringMatching(/^ws:\/\/127\.0\.0\.1:5762\/mumulib-vite\//),
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
  // The page's own script, built; and the library, which the build left
  // out, from the server's own copy of it, named by the page's import map
  const own = scripts.filter((url) =>
    /^http:\/\/127\.0\.0\.1:5763\/mumulib-vite\/assets\/.+\.js$/.test(url),
  )
  expect(own).toHaveLength(1)
  const library = `${MODES.production}/mumulib/browser/`
  expect(scripts).toContain(`${library}mumulib.mjs`)
  for (const url of scripts.filter((url) => !own.includes(url))) {
    expect(url.startsWith(library), url).toBe(true)
  }
  expect(sockets).toEqual([])
  // Each cached by its file: asked again, only whether it changed
  for (const url of [own[0], `${library}mumulib.mjs`]) {
    const first = await page.request.get(url)
    const etag = first.headers()['etag']
    expect(first.headers()['cache-control']).toBe('no-cache')
    const again = await page.request.get(url, {
      headers: { 'if-none-match': etag },
    })
    expect(again.status(), url).toBe(304)
  }
})
