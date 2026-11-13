import { test, expect, type Page } from './coverage.fixture'

// mumulib's live.js, py/mumulib/live.js, on the live example's page,
// py/examples/live.py: built in Python, and kept up to date by the change
// stream. Each browser has a server of its own (playwright.config), since a
// change to the one page is heard by every page open.
const PORTS: { [project: string]: string } = {
  chromium: '8124',
  webkit: '8127',
}

test.describe.configure({ mode: 'serial' })

type Marked = HTMLElement & { marked?: boolean }

// Every live element marked, as a node: one replaced is a new node, unmarked
async function mark(page: Page) {
  await page.evaluate(() => {
    for (const element of document.querySelectorAll('[data-live]')) {
      ;(element as Marked).marked = true
    }
  })
}

async function marked(page: Page) {
  return page.evaluate(() =>
    Object.fromEntries(
      [...document.querySelectorAll('[data-live]')].map((element) => [
        element.id,
        (element as Marked).marked === true,
      ])
    )
  )
}

test.describe('live.js', () => {
  let site = ''
  test.beforeEach(({}, info) => {
    site = `http://127.0.0.1:${PORTS[info.project.name]}`
  })

  test('another page open shows the change, from the server', async ({
    browser,
  }) => {
    const watcher = await browser.newPage()
    await watcher.goto(`${site}/`)
    const page = await browser.newPage()
    await page.goto(`${site}/`)
    const apples = page.locator('#apples output')
    const before = Number(await apples.textContent())
    await page.locator('#apples button').click()
    // Not changed here by the click: put in place when it was announced
    await expect(apples).toHaveText(String(before + 1))
    // The watcher never reloaded: its row was fetched and put in place
    await expect(watcher.locator('#apples output')).toHaveText(
      String(before + 1)
    )
    await watcher.close()
    await page.close()
  })

  test('a change replaces only the elements watching it', async ({ page }) => {
    await page.goto(`${site}/`)
    await mark(page)
    const count = Number(await page.locator('#pears output').textContent())
    await page.request.put(`${site}/counters/pears/count.json`, {
      data: count + 10,
    })
    await expect(page.locator('#pears output')).toHaveText(String(count + 10))
    expect(await marked(page)).toEqual({
      title: true,
      apples: true,
      pears: false,
      plums: true,
    })
  })

  test("a bare data-live watches the page's own URL, and nothing else fetches", async ({
    page,
  }) => {
    await page.goto(`${site}/`)
    let fetched = 0
    page.on('request', (request) => {
      if (request.url() === `${site}/`) fetched += 1
    })
    // Being typed in when the change arrives: outside every live element
    const field = page.locator('input[name="title"]')
    await field.fill('Half typed')
    await mark(page)
    // A change to the plums: the page fetched, for their row alone
    const plums = Number(await page.locator('#plums output').textContent())
    await page.request.put(`${site}/counters/plums/count.json`, {
      data: plums + 1,
    })
    await expect(page.locator('#plums output')).toHaveText(String(plums + 1))
    // A change to the title, announced as /: the heading, watching the page
    const title = `Renamed at ${Date.now()}`
    await page.request.put(`${site}/title.json`, {
      // A string as data is sent as it is: JSON, so it is a JSON string
      data: JSON.stringify(title),
      headers: { 'content-type': 'application/json' },
    })
    await expect(page.locator('#title')).toHaveText(title)
    // One fetch for each change, and only the elements watching it replaced
    expect(fetched).toBe(2)
    expect(await marked(page)).toEqual({
      title: false,
      apples: true,
      pears: true,
      plums: false,
    })
    // And the field, being typed in, was left as it was
    await expect(field).toHaveValue('Half typed')
  })

  test('the form renames the page, and the page shows it when announced', async ({
    page,
  }) => {
    await page.goto(`${site}/`)
    const title = `Fruit ${Date.now()}`
    await page.locator('input[name="title"]').fill(title)
    await page.getByRole('button', { name: 'Rename' }).click()
    await expect(page.locator('#title')).toHaveText(title)
    // Submitted by the script, not as a form: the page was not left
    expect(page.url()).toBe(`${site}/`)
  })
})
