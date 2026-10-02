import { test, expect, type Page } from './coverage.fixture'

// The editors example, py/examples/editors.py: pages built in Python, forms
// posted as forms. The tests have a server of their own (playwright.config).
// Chromium and WebKit run at once against it, so each edits objects of its
// own, and sets every value it then looks for.
const EDITORS = `http://127.0.0.1:${process.env.PLAYWRIGHT_EDITORS_PORT || '8124'}`
const INDEX = `${EDITORS}/editors/`
const OWN: { [project: string]: { c: string; p: string; d: string } } = {
  chromium: { c: 'c1', p: 'p1', d: 'd1' },
  webkit: { c: 'c2', p: 'p2', d: 'd2' },
}

test.describe.configure({ mode: 'serial' })

function editLink(page: Page, kind: string, id: string) {
  return page.locator(`a[href="/editors/${kind}/${id}.html"]`)
}

// An edit link goes to the object's edit page; Save posts its form, and the
// page that answers is the index again
async function edit(page: Page, kind: string, id: string) {
  await editLink(page, kind, id).click()
  await page.waitForURL(`${EDITORS}/editors/${kind}/${id}.html`)
  return page.locator('form')
}

async function save(page: Page) {
  await page.getByRole('button', { name: 'Save' }).click()
  await page.waitForURL(INDEX)
}

test.describe('The editors example', () => {
  test('the index is a table of each kind', async ({ page }) => {
    await page.goto(INDEX)
    await expect(page.locator('#characters tbody tr')).toHaveCount(3)
    await expect(page.locator('#parties tbody tr')).toHaveCount(2)
    await expect(page.locator('#deploys tbody tr')).toHaveCount(2)
  })

  test('a character is edited on its page, and posted', async ({
    page,
  }, info) => {
    const { c } = OWN[info.project.name]
    await page.goto(INDEX)
    const name = (await editLink(page, 'characters', c).textContent())?.trim()
    const form = await edit(page, 'characters', c)
    // The form is filled from the character's state
    await expect(form.locator('input[name="name"]')).toHaveValue(name ?? '')
    const prompt = `A prompt from ${info.project.name} at ${Date.now()}`
    await form.locator('textarea[name="prompt"]').fill(prompt)
    await save(page)
    await expect(page.locator('#characters')).toContainText(prompt)
  })

  test('an edit page is a page of its own, with no script', async ({
    browser,
  }, info) => {
    const { c } = OWN[info.project.name]
    const context = await browser.newContext({ javaScriptEnabled: false })
    const page = await context.newPage()
    await page.goto(`${EDITORS}/editors/characters/${c}.html`)
    const args = `--plain-${info.project.name}`
    await page.locator('input[name="agent_args"]').fill(args)
    await page.getByRole('button', { name: 'Save' }).click()
    await page.waitForURL(INDEX)
    await expect(page.locator('#characters')).toContainText(args)
    await context.close()
  })

  test("a party's members are chosen, or none", async ({ page }, info) => {
    const { c, p } = OWN[info.project.name]
    await page.goto(INDEX)
    const row = page.locator('#parties tr', {
      has: editLink(page, 'parties', p),
    })
    let form = await edit(page, 'parties', p)
    // This browser's own character, which only its own tests rename, and c3,
    // which no test does: the other browser renames its own meanwhile
    await form.locator('select[name="members[]"]').selectOption([c, 'c3'])
    await save(page)
    const names = await Promise.all(
      [c, 'c3'].map(async (id) => {
        const r = await page.request.get(
          `${EDITORS}/editors/characters/${id}/state.json`
        )
        return (await r.json()).name as string
      })
    )
    await expect(row).toContainText(names.join(', '))
    form = await edit(page, 'parties', p)
    await form.locator('select[name="members[]"]').selectOption([])
    await save(page)
    await expect(row.locator('td').nth(1)).toHaveText('')
  })

  test("a deploy's party is chosen, and its status stays", async ({
    page,
  }, info) => {
    const { d } = OWN[info.project.name]
    const before = await (
      await page.request.get(`${EDITORS}/editors/deploys/${d}/state.json`)
    ).json()
    await page.goto(INDEX)
    const form = await edit(page, 'deploys', d)
    await expect(form.locator('select[name="party"] option')).toHaveCount(2)
    await expect(form).toContainText(`Status: ${before.status}`)
    const party = before.party === 'p1' ? 'p2' : 'p1'
    await form.locator('select[name="party"]').selectOption(party)
    await save(page)
    const row = page.locator('#deploys tr', {
      has: editLink(page, 'deploys', d),
    })
    await expect(row).toContainText(party === 'p1' ? 'Reviewers' : 'Operators')
    const after = await (
      await page.request.get(`${EDITORS}/editors/deploys/${d}/state.json`)
    ).json()
    expect(after).toEqual({ ...before, party })
  })

  test('cancel goes back and saves nothing', async ({ page }, info) => {
    const { c } = OWN[info.project.name]
    await page.goto(INDEX)
    const form = await edit(page, 'characters', c)
    await form.locator('input[name="agent_args"]').fill('--cancelled')
    await page.getByRole('link', { name: 'Cancel' }).click()
    await page.waitForURL(INDEX)
    const kept = await (
      await page.request.get(`${EDITORS}/editors/characters/${c}/state.json`)
    ).json()
    expect(kept.agent_args).not.toBe('--cancelled')
  })

  test('another page open shows the change, from the server', async ({
    browser,
  }, info) => {
    const { c } = OWN[info.project.name]
    const watcher = await browser.newPage()
    await watcher.goto(INDEX)
    const page = await browser.newPage()
    await page.goto(INDEX)
    const prompt = `Seen elsewhere, ${info.project.name} ${Date.now()}`
    const form = await edit(page, 'characters', c)
    await form.locator('textarea[name="prompt"]').fill(prompt)
    await save(page)
    // The watcher never reloaded: its tables were fetched and put in place
    await expect(watcher.locator('#characters')).toContainText(prompt)
    await watcher.close()
    await page.close()
  })

  test('a change replaces only the rows watching it', async ({
    browser,
  }, info) => {
    const { c, p, d } = OWN[info.project.name]
    const watcher = await browser.newPage()
    await watcher.goto(INDEX)
    // Every row marked, as a node: a row replaced is a new node, unmarked
    await watcher.evaluate(() => {
      for (const row of document.querySelectorAll('tr[data-live]')) {
        ;(row as HTMLElement & { marked?: boolean }).marked = true
      }
    })
    const prompt = `Only this row, ${info.project.name} ${Date.now()}`
    await watcher.request.post(`${EDITORS}/editors/characters/${c}.html`, {
      form: { name: `Character ${c}`, prompt, agent_args: '' },
    })
    await expect(watcher.locator(`#characters-${c}`)).toContainText(prompt)
    const marked = await watcher.evaluate(() =>
      Object.fromEntries(
        [...document.querySelectorAll('tr[data-live]')].map((row) => [
          row.id,
          (row as HTMLElement & { marked?: boolean }).marked === true,
        ])
      )
    )
    // This browser's own rows: the other browser changes its own meanwhile
    expect(marked[`characters-${c}`], 'the changed row').toBe(false)
    expect(marked[`parties-${p}`], 'its party').toBe(true)
    expect(marked[`deploys-${d}`], 'its deploy').toBe(true)
    await watcher.close()
  })

  test("a bare data-live watches the page's own URL, and nothing else fetches", async ({
    browser,
  }, info) => {
    const { c, d } = OWN[info.project.name]
    const page = await browser.newPage()
    const url = `${EDITORS}/editors/characters/${c}.html`
    await page.goto(url)
    let fetched = 0
    page.on('request', (request) => {
      if (request.url() === url) fetched += 1
    })
    // A change to a deploy: nothing on this page watches it
    const deploy = await (
      await page.request.get(`${EDITORS}/editors/deploys/${d}/state.json`)
    ).json()
    await page.request.post(`${EDITORS}/editors/deploys/${d}.html`, {
      form: { name: deploy.name, party: deploy.party },
    })
    // A change to this character: the heading, watching the page's URL
    const name = `Renamed ${info.project.name} ${Date.now()}`
    await page.request.post(url, {
      form: { name, prompt: 'p', agent_args: '' },
    })
    await expect(page.locator('#heading')).toHaveText(name)
    // One fetch, for the change it watches; none for the deploy's
    expect(fetched).toBe(1)
    // And the form, being typed in, was left as it was
    await expect(page.locator('input[name="name"]')).not.toHaveValue(name)
    await page.close()
  })
})
