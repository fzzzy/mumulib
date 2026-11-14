import { test, expect } from './coverage.fixture'

// The docs' small examples, each a fixture page of its own: a component in an
// app, binding, and a dialog that calls a method.

test.describe('The small fixtures', () => {
  test('an app hands a component its state, and hears what it asks', async ({
    page,
  }) => {
    await page.goto('fixtures/small_app/')
    const count = page.locator('my-counter span')
    const lot = page.getByText("That's a lot.")
    await expect(count).toHaveText('0')
    await expect(lot).toBeHidden()
    const add = page.getByRole('button', { name: 'Add one' })
    for (let i = 0; i < 3; i++) await add.click()
    await expect(count).toHaveText('3')
    await expect(lot).toBeVisible()
  })

  test('a bound input and checkbox are the state', async ({ page }) => {
    await page.goto('fixtures/small_binding/')
    const greeting = page.locator('[data-slot="greeting"]')
    await expect(greeting).toHaveText('world')
    await page.getByPlaceholder('Your name').fill('Ada')
    await expect(greeting).toHaveText('Ada')
    await page.getByLabel('Loud').check()
    await expect(greeting).toHaveText('ADA!')
  })

  test("a dialog's form calls its method", async ({ page }) => {
    await page.goto('fixtures/small_dialog/')
    const name = page.locator('[data-slot="name"]')
    const dialog = page.locator('dialog')
    const rename = page.getByRole('button', { name: 'Rename' })

    await rename.click()
    await expect(dialog).toBeVisible()
    await expect(dialog.locator('input[name="name"]')).toHaveValue('world')
    await dialog.locator('input[name="name"]').fill('Bob')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(name).toHaveText('world')

    await rename.click()
    await dialog.locator('input[name="name"]').fill('Ada')
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(name).toHaveText('Ada')
  })
})
