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

  test.describe('forms of every kind', () => {
    const outputs = (page: import('@playwright/test').Page) =>
      page.$$eval('div[class="output"]', (divs) =>
        divs.map((div) => div.textContent)
      )

    test.beforeEach(async ({ page }) => {
      await page.goto('examples/use_dialog_forms/')
      await expect(page.locator('body')).toHaveAttribute(
        'data-person',
        /"name":"Ada"/
      )
    })

    test('a method is given lists, empty ones, names given twice, and text, but no files', async ({
      page,
    }) => {
      await page.click('#open-lists')
      await page.getByRole('button', { name: 'Done' }).click()
      await expect
        .poll(() => outputs(page))
        .toEqual([
          'record ' +
            JSON.stringify({
              tags: ['red', 'blue'],
              one: ['only'],
              color: ['cyan', 'magenta'],
              notes: 'written',
              // Nothing checked or chosen; and nothing for the disabled
              unchecked: [],
              unchosen: [],
            }),
        ])
    })

    test('a button names another form to save, and an async method is waited for', async ({
      page,
    }) => {
      await page.click('#open-named')
      await page.getByRole('button', { name: 'Final' }).click()
      await expect
        .poll(() => outputs(page))
        .toEqual([
          'record_later {"name":"final"} while this.recorder is selected',
        ])
      await expect(page.locator('body')).toHaveAttribute('data-selected', '')
    })

    test('a form with no button is submitted by Enter', async ({ page }) => {
      await page.click('#open-implicit')
      await page.locator('#implicit input[name="name"]').fill('entered')
      await page.keyboard.press('Enter')
      await expect(page.locator('#implicit')).toBeHidden()
      await expect
        .poll(() => outputs(page))
        .toEqual(['record {"name":"entered"}'])
    })

    test('with no method, the selected controls are set in the selected object', async ({
      page,
    }) => {
      await page.click('#open-selected')
      await expect(page.locator('body')).toHaveAttribute(
        'data-selected',
        'this.person'
      )
      await page.locator('input[name="selected.name"]').fill('Grace')
      await page.locator('input[name="selected.age"]').fill('45')
      // A radio button not the last, a checkbox unchecked, the controls that
      // are no input, and a list of checkboxes left with none checked
      await page.locator('input[value="medium"]').check()
      await page.locator('input[name="selected.agreed"]').uncheck()
      await page.locator('textarea[name="selected.bio"]').fill('Admiral')
      await page.locator('select[name="selected.city"]').selectOption('Rome')
      await page.locator('input[name="selected.tags[]"][value="red"]').uncheck()
      await page
        .locator('select[name="selected.languages[]"]')
        .selectOption(['fr'])
      await page.getByRole('button', { name: 'Save' }).click()
      await expect
        .poll(async () =>
          JSON.parse(
            (await page.locator('body').getAttribute('data-person')) ?? ''
          )
        )
        .toEqual({
          name: 'Grace',
          age: '45',
          size: 'medium',
          agreed: false,
          bio: 'Admiral',
          city: 'Rome',
          tags: [],
          languages: ['fr'],
        })
      await expect(page.locator('body')).toHaveAttribute('data-selected', '')
      expect(await outputs(page)).toEqual([])
    })

    test('a dialog that is not there, or is no dialog, is said', async ({
      page,
    }) => {
      const errors: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'error') errors.push(message.text())
      })
      await page.click('#open-missing')
      await expect
        .poll(() => errors)
        .toEqual([
          'Dialog missing not found.',
          'Dialog not_a_dialog not found.',
        ])
    })

    test('the selected controls open as a draft of the selected object', async ({
      page,
    }) => {
      const errors: string[] = []
      page.on('pageerror', (error) => errors.push(error.message))
      const control = (name: string) =>
        page.locator(`#selected [name="selected.${name}"]`)
      const person = () => page.locator('body').getAttribute('data-person')

      await page.click('#open-selected')
      await expect(control('name')).toHaveValue('Ada')
      await expect(control('age')).toHaveValue('36')
      await expect(page.locator('#selected input[value="small"]')).toBeChecked()
      await expect(
        page.locator('#selected input[value="medium"]')
      ).not.toBeChecked()
      await expect(control('agreed')).toBeChecked()
      await expect(page.locator('#selected input[value="red"]')).toBeChecked()
      await expect(
        page.locator('#selected input[value="green"]')
      ).not.toBeChecked()
      await expect(control('city')).toHaveValue('Paris')
      await expect(control('languages[]')).toHaveValues(['en', 'de'])

      // Leaving a field gives nothing to the state, and a change of state
      // meanwhile does not write over the draft
      const before = await person()
      await control('name').fill('Grace')
      await control('age').focus()
      await control('age').fill('45')
      await control('bio').focus()
      await page.click('#elsewhere-inside')
      await expect(control('name')).toHaveValue('Grace')
      await expect(control('age')).toHaveValue('45')
      expect(await person()).toBe(before)

      // Cancelled, the object is as it was, and opened again so is the draft
      await page.getByRole('button', { name: 'Cancel' }).click()
      await expect(page.locator('#selected')).toBeHidden()
      expect(await person()).toBe(before)
      await page.click('#open-selected')
      await expect(control('name')).toHaveValue('Ada')
      expect(errors).toEqual([])
    })

    test('a dialog logs nothing unless in debug', async ({ page }) => {
      const logged: string[] = []
      page.on('console', (message) => {
        if (message.type() === 'log') logged.push(message.text())
      })
      await page.click('#open-lists')
      await page.getByRole('button', { name: 'Done' }).click()
      await expect.poll(() => outputs(page)).toHaveLength(1)
      await page.click('#open-selected')
      await page.getByRole('button', { name: 'Save' }).click()
      await expect(page.locator('#selected')).toBeHidden()
      await page.click('#open-selected')
      await page.getByRole('button', { name: 'Cancel' }).click()
      await expect(page.locator('#selected')).toBeHidden()
      expect(logged.filter((text) => !text.startsWith('[vite]'))).toEqual([])
    })
  })
})
