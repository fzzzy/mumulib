import { test, expect, type Page } from './coverage.fixture'

// The editors example: py/examples/editors.py's data in tables, each object
// edited in a dialog. Chromium and WebKit run at once against one server, so
// each edits objects of its own, and sets every value it then looks for.
const OWN: { [project: string]: { c: string; p: string; d: string } } = {
  chromium: { c: 'c1', p: 'p1', d: 'd1' },
  webkit: { c: 'c2', p: 'p2', d: 'd2' },
}

test.describe.configure({ mode: 'serial' })

async function open(page: Page) {
  await page.goto('examples/editors/')
  // The data has arrived when a real row has replaced the sample one
  await expect(page.locator('#deploys tbody tr').first()).not.toHaveText(
    /A deploy/
  )
}

function editLink(page: Page, kind: string, id: string) {
  return page.locator(`[data-edit="this.${kind}.${id}"]`)
}

test.describe('The editors example', () => {
  test('the tables are the server data, names and all', async ({ page }) => {
    await open(page)
    await expect(page.locator('#characters tbody tr')).toHaveCount(3)
    await expect(page.locator('#parties tbody tr')).toHaveCount(2)
    // A party's members and a deploy's party are ids, shown by name
    await expect(page.locator('#deploys tbody')).toContainText(
      /Reviewers|Operators/
    )
  })

  test('a character is edited in its dialog', async ({ page }, info) => {
    const { c } = OWN[info.project.name]
    await open(page)
    await editLink(page, 'characters', c).click()
    const dialog = page.locator('#character_dialog')
    await expect(dialog).toBeVisible()
    // The dialog shows the character as it is
    const name = await editLink(page, 'characters', c).textContent()
    await expect(dialog.locator('input[name="name"]')).toHaveValue(
      (name ?? '').trim()
    )
    const prompt = `A prompt from ${info.project.name} at ${Date.now()}`
    await dialog.locator('textarea[name="prompt"]').fill(prompt)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.locator('#characters')).toContainText(prompt)
    const saved = await (
      await page.request.get(`/editors/characters/${c}.json`)
    ).json()
    expect(saved.prompt).toBe(prompt)
  })

  test("a party's members are chosen in a component", async ({
    page,
  }, info) => {
    const { p } = OWN[info.project.name]
    await open(page)
    await editLink(page, 'parties', p).click()
    const dialog = page.locator('#party_dialog')
    // The member-select's own <select>, inside its shadow root
    await dialog.locator('member-select select').selectOption(['c1', 'c3'])
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
    // The dialog closes at once, and the save follows: the row says when
    const row = page.locator('#parties tr', {
      has: editLink(page, 'parties', p),
    })
    await expect(row).toContainText('Code Reviewer, Shell Helper')
    const saved = await (
      await page.request.get(`/editors/parties/${p}.json`)
    ).json()
    expect(saved.members).toEqual(['c1', 'c3'])
    // And none at all is an empty list, not a missing one
    await editLink(page, 'parties', p).click()
    await dialog.locator('member-select select').selectOption([])
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
    await expect(row.locator('td').nth(1)).toHaveText('')
    const emptied = await (
      await page.request.get(`/editors/parties/${p}.json`)
    ).json()
    expect(emptied.members).toEqual([])
  })

  test("a deploy's party is chosen, and its status stays", async ({
    page,
  }, info) => {
    const { d } = OWN[info.project.name]
    const before = await (
      await page.request.get(`/editors/deploys/${d}.json`)
    ).json()
    await open(page)
    await editLink(page, 'deploys', d).click()
    const dialog = page.locator('#deploy_dialog')
    // The choices are the parties, from the party_option pattern
    await expect(dialog.locator('select[name="party"] option')).toHaveCount(2)
    await expect(dialog).toContainText(`Status: ${before.status}`)
    const party = before.party === 'p1' ? 'p2' : 'p1'
    await dialog.locator('select[name="party"]').selectOption(party)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toBeHidden()
    const row = page.locator('#deploys tr', {
      has: editLink(page, 'deploys', d),
    })
    await expect(row).toContainText(party === 'p1' ? 'Reviewers' : 'Operators')
    const saved = await (
      await page.request.get(`/editors/deploys/${d}.json`)
    ).json()
    expect(saved).toEqual({ ...before, party })
  })

  test('cancel saves nothing, and the next save still saves', async ({
    page,
  }, info) => {
    const { c } = OWN[info.project.name]
    await open(page)
    const dialog = page.locator('#character_dialog')
    await editLink(page, 'characters', c).click()
    await dialog.locator('input[name="agent_args"]').fill('--cancelled')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    const kept = await (
      await page.request.get(`/editors/characters/${c}.json`)
    ).json()
    expect(kept.agent_args).not.toBe('--cancelled')
    // Opened again: the cancelled edit is gone, and Save is a save
    await editLink(page, 'characters', c).click()
    await expect(dialog.locator('input[name="agent_args"]')).toHaveValue(
      kept.agent_args
    )
    const args = `--saved-${info.project.name}`
    await dialog.locator('input[name="agent_args"]').fill(args)
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('#characters')).toContainText(args)
  })

  test('another page open sees the change, from the server', async ({
    browser,
  }, info) => {
    const { c } = OWN[info.project.name]
    const watcher = await browser.newPage({ baseURL: info.project.use.baseURL })
    await open(watcher)
    const page = await browser.newPage({ baseURL: info.project.use.baseURL })
    await open(page)
    const prompt = `Seen elsewhere, ${info.project.name} ${Date.now()}`
    await editLink(page, 'characters', c).click()
    await page.locator('#character_dialog textarea[name="prompt"]').fill(prompt)
    await page
      .locator('#character_dialog')
      .getByRole('button', { name: 'Save' })
      .click()
    await expect(watcher.locator('#characters')).toContainText(prompt)
    await watcher.close()
    await page.close()
  })
})
