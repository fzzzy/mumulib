import { test, expect } from './coverage.fixture'

// examples/use_app is an app drawn into its page's own markup. The other
// tests make apps of their own on the Mumu example's page, which has none.

test.describe('Mumulib apps', () => {
  test("an app draws into the page's own markup", async ({ page }) => {
    await page.goto('examples/use_app/')
    // The sample row, and the sample count, are replaced by the first render.
    await expect(page.locator('body li')).toHaveCount(0)
    await expect(page.locator('body .count')).toHaveText('0 things, 0 done')
    // In the page, not in a shadow root: the page's own selectors reach it.
    expect(await page.evaluate(() => document.body.shadowRoot)).toBeNull()
  })

  test("data-on takes the page's events to the app's methods", async ({
    page,
  }) => {
    await page.goto('examples/use_app/')
    const input = page.getByPlaceholder('Something to do')
    const add = page.getByRole('button', { name: 'Add' })

    await input.fill('Water the plants')
    await add.click()
    await input.fill('Feed the cat')
    await add.click()
    await expect(page.locator('body li span')).toHaveText([
      'Water the plants',
      'Feed the cat',
    ])

    // A click in a row, which came from a template.
    await page
      .locator('body li', { hasText: 'Water' })
      .locator('.remove')
      .click()
    await expect(page.locator('body li span')).toHaveText(['Feed the cat'])
    await expect(page.locator('body .count')).toHaveText('1 thing, 0 done')

    // A component's own event, which it emits from inside its shadow root.
    const opener = page.locator('my-opener button')
    await opener.click()
    await expect(opener).toHaveText('Close')
    await opener.click()
    await expect(opener).toHaveText('Open')
  })

  test('a this.* control is bound to the state, both ways', async ({
    page,
  }) => {
    await page.goto('examples/use_app/')
    const input = page.getByPlaceholder('Something to do')
    const add = page.getByRole('button', { name: 'Add' })
    await expect(add).toBeDisabled()
    // Up: what is typed is the state's, as it is typed.
    await input.fill('Water the plants')
    await expect(add).toBeEnabled()
    // Down: adding clears the draft, and the input still focused shows it.
    await add.click()
    await expect(input).toHaveValue('')
    await expect(add).toBeDisabled()
  })

  test("a row's controls are bound to its item in the state's list", async ({
    page,
  }) => {
    await page.goto('examples/use_app/')
    const input = page.getByPlaceholder('Something to do')
    const add = page.getByRole('button', { name: 'Add' })
    for (const text of ['one', 'two', 'three']) {
      await input.fill(text)
      await add.click()
    }
    const row = (text: string) => page.locator('body li', { hasText: text })
    await row('three').getByRole('checkbox').check()
    await expect(page.locator('body .count')).toHaveText('3 things, 1 done')
    // Its place in the list is worked out as it changes, not as it was drawn.
    await row('one').locator('.remove').click()
    await row('two').getByRole('checkbox').check()
    await expect(page.locator('body .count')).toHaveText('2 things, 2 done')
    await row('three').getByRole('checkbox').uncheck()
    await expect(page.locator('body .count')).toHaveText('2 things, 1 done')
    await expect(row('two').getByRole('checkbox')).toBeChecked()
    await expect(row('three').getByRole('checkbox')).not.toBeChecked()
  })

  test("a component's bound control changes the state it was given", async ({
    page,
  }) => {
    await page.goto('examples/use_app/')
    const field = page.locator('my-field input')
    // Down, through data-prop, into the component's own control.
    await expect(field).toHaveValue('Things to do')
    // Up: the component's text is the app's title, which data-prop gave it.
    await field.fill('Chores')
    await expect(page.locator('body h1')).toHaveText('Chores')
  })

  test("a dialog's form calls its method, as it is saved", async ({ page }) => {
    await page.goto('examples/use_app/')
    await page.getByPlaceholder('Something to do').fill('Water the plants')
    await page.getByRole('button', { name: 'Add' }).click()
    const dialog = page.locator('dialog.editor')
    const text = dialog.locator('input[name="text"]')
    const edit = page.locator('body li .edit')

    // Opened as it appears, its field drawn from the state: a draft.
    await edit.click()
    await expect(dialog).toBeVisible()
    await expect(text).toHaveValue('Water the plants')
    await text.fill('Cancelled')
    await dialog.getByRole('button', { name: 'Cancel' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.locator('body li span')).toHaveText(['Water the plants'])

    await edit.click()
    await expect(text).toHaveValue('Water the plants')
    await text.fill('Escaped')
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.locator('body li span')).toHaveText(['Water the plants'])

    await edit.click()
    await text.fill('Water the garden')
    await dialog.getByRole('button', { name: 'Save' }).click()
    await expect(dialog).toHaveCount(0)
    await expect(page.locator('body li span')).toHaveText(['Water the garden'])
  })

  test("an app's state is frozen", async ({ page }) => {
    await page.goto('examples/use_mumu/')
    const thrown = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      root.innerHTML = '<button data-on="click=push">Push</button>'
      document.body.append(root)
      let error = ''
      class Pusher extends App<{ items: string[] }> {
        static state = { items: ['one'] }
        push(): void {
          try {
            // A change made in place, which would show nothing.
            ;(this.state.items as string[]).push('two')
          } catch (e) {
            error = (e as Error).constructor.name
          }
        }
      }
      mountApp(Pusher, root)
      root.querySelector('button')!.click()
      return error
    })
    expect(thrown).toBe('TypeError')
  })

  test('there is one app on a page', async ({ page }) => {
    await page.goto('examples/use_app/')
    const refused = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      document.body.append(root)
      try {
        mountApp(class Second extends App<object> {}, root)
        return ''
      } catch (e) {
        return (e as Error).message
      }
    })
    expect(refused).toContain('There is one app on a page')
  })

  test('a data-on naming no method is refused', async ({ page }) => {
    await page.goto('examples/use_mumu/')
    const refused = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      // In a row's template too: its events are listened for from the start.
      root.innerHTML =
        '<ul data-slot="rows"><template data-pat="foreach">' +
        '<li data-on="click=pick"></li></template></ul>'
      document.body.append(root)
      try {
        mountApp(class Picker extends App<object> {}, root)
        return ''
      } catch (e) {
        return (e as Error).message
      }
    })
    expect(refused).toBe(
      'Picker has no method pick, which data-on="click=pick" calls'
    )
  })

  test('what cannot bind, or names no method, is refused', async ({ page }) => {
    await page.goto('examples/use_mumu/')
    const refused = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const tries: string[] = []
      for (const markup of [
        // A getter only presents the state.
        '<input name="this.shown">',
        // Nor rows drawn from one.
        '<ul data-slot="rows"><template data-pat="foreach">' +
          '<li><input name="this.done"></li></template></ul>',
        // A dialog is a draft, given to its method.
        '<dialog><form><input name="this.items"></form></dialog>',
        '<dialog><form><input type="hidden" name="method" value="keep">' +
          '</form></dialog>',
      ]) {
        const root = document.createElement('div')
        root.innerHTML = markup
        document.body.append(root)
        try {
          mountApp(
            class Lister extends App<{ items: string[] }> {
              static state = { items: [] }
              get shown(): string {
                return ''
              }
              get rows(): object[] {
                return []
              }
            },
            root
          )
          tries.push('')
        } catch (e) {
          tries.push((e as Error).message)
        }
        root.remove()
      }
      return tries
    })
    expect(refused).toEqual([
      'Lister binds this.shown, but shown is not in its state: ' +
        'a getter only presents the state, and cannot be written to',
      "Lister's rows rows bind this.done, but rows is not in its state: " +
        'a getter only presents the state, and cannot be written to',
      "Lister binds this.items in a dialog: a dialog's form is a draft, " +
        'given to its method as it is submitted',
      "Lister has no method keep, which its dialog's form calls",
    ])
  })
})
