import { test, expect } from './coverage.fixture'

test.describe('Mumulib Dialog Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure we have a clean state before each test
    await page.goto('about:blank')
  })

  test('should handle dialog interactions', async ({ page }) => {
    await page.goto('examples/use_dialog/')

    await page.waitForSelector('dialog[id="my_dialog"]')
    await page.fill('input[name="name"]', 'askdjhfajks')
    await page.fill('input[name="age"]', '123')
    await page.click('button')

    await page.waitForSelector('div[class="output"]')
    const output = await page.$eval(
      'div[class="output"]',
      (el) => el.textContent
    )

    expect(output).toBe('my_method was called askdjhfajks 123')
  })

  test('Cancel and Escape save nothing; Save after them does', async ({
    page,
  }) => {
    await page.goto('examples/use_dialog_cancel/')
    const dialog = page.locator('#my_dialog')
    const name = page.locator('input[name="name"]')
    const outputs = () =>
      page.$$eval('div[class="output"]', (divs) =>
        divs.map((div) => div.textContent)
      )

    await page.click('#open')
    await expect(dialog).toBeVisible()
    await name.fill('cancelled')
    await page.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toBeHidden()
    await expect(page.locator('body')).toHaveAttribute('data-selected', '')

    await page.click('#open')
    await expect(dialog).toBeVisible()
    await name.fill('escaped')
    await page.keyboard.press('Escape')
    await expect(dialog).toBeHidden()
    await expect(page.locator('body')).toHaveAttribute('data-selected', '')

    await page.click('#open')
    await expect(page.locator('body')).toHaveAttribute(
      'data-selected',
      'this.my_object'
    )
    await name.fill('kept')
    await page.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(dialog).toBeHidden()
    await expect.poll(outputs).toEqual(['saved kept'])
    await expect(page.locator('body')).toHaveAttribute('data-selected', '')
  })

  test('a returnValue that is no selector still saves', async ({ page }) => {
    await page.goto('examples/use_dialog_cancel/')
    await page.click('#open')
    await page.locator('input[name="name"]').fill('dotted')
    await page.getByRole('button', { name: 'Save as' }).click()
    await expect
      .poll(() =>
        page.$$eval('div[class="output"]', (divs) =>
          divs.map((div) => div.textContent)
        )
      )
      .toEqual(['saved dotted'])
  })
})
