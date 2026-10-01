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
    const { p } = OWN[info.project.name]
    await page.goto(INDEX)
    const row = page.locator('#parties tr', {
      has: editLink(page, 'parties', p),
    })
    let form = await edit(page, 'parties', p)
    await form.locator('select[name="members[]"]').selectOption(['c1', 'c3'])
    await save(page)
    await expect(row).toContainText('Code Reviewer, Shell Helper')
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
})
