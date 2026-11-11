import { test, expect } from './coverage.fixture'

// examples/use_app_rows is an app drawn into its page's own markup, and
// use_app_field one with a component bound to its state; small.spec.ts has
// the small examples. The other tests make apps of their own on the Mumu
// example's page, which has none.

test.describe('Mumulib apps', () => {
  test("an app draws into the page's own markup", async ({ page }) => {
    await page.goto('examples/use_app_rows/')
    // The sample row, and the sample count, are replaced by the first render.
    await expect(page.locator('body li span')).toHaveText([
      'one',
      'two',
      'three',
    ])
    await expect(page.locator('body .count')).toHaveText('3 things, 0 done')
    // In the page, not in a shadow root: the page's own selectors reach it.
    expect(await page.evaluate(() => document.body.shadowRoot)).toBeNull()
  })

  test("a row's controls are bound to its item, and its events are the app's", async ({
    page,
  }) => {
    await page.goto('examples/use_app_rows/')
    const row = (text: string) => page.locator('body li', { hasText: text })
    // Up: a row's checkbox is its item's done.
    await row('three').getByRole('checkbox').check()
    await expect(page.locator('body .count')).toHaveText('3 things, 1 done')
    // A click in a row, which came from a template, to the app's method.
    await row('one').locator('.remove').click()
    await expect(page.locator('body li span')).toHaveText(['two', 'three'])
    // Its place in the list is worked out as it changes, not as it was drawn.
    await row('two').getByRole('checkbox').check()
    await expect(page.locator('body .count')).toHaveText('2 things, 2 done')
    await row('three').getByRole('checkbox').uncheck()
    await expect(page.locator('body .count')).toHaveText('2 things, 1 done')
    // Down: each row still shows its own item's done.
    await expect(row('two').getByRole('checkbox')).toBeChecked()
    await expect(row('three').getByRole('checkbox')).not.toBeChecked()
  })

  test("a component's bound control changes the state it was given", async ({
    page,
  }) => {
    await page.goto('examples/use_app_field/')
    const field = page.locator('my-field input')
    // Down, through data-prop, into the component's own control.
    await expect(field).toHaveValue('Things to do')
    // Up: the component's text is the app's title, which data-prop gave it.
    await field.fill('Chores')
    await expect(page.locator('body h1')).toHaveText('Chores')
  })

  test('a bound control shows a change of the state, though it has the focus', async ({
    page,
  }) => {
    await page.goto('examples/use_mumu/')
    await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      root.innerHTML =
        '<input id="draft" name="this.draft"><button data-on="click=clear">Clear</button>'
      document.body.append(root)
      class Draft extends App<{ draft: string }> {
        static state = { draft: '' }
        clear(): void {
          this.update({ draft: '' })
        }
      }
      mountApp(Draft, root)
    })
    const input = page.locator('#draft')
    await input.fill('Water the plants')
    // Cleared from code -- a click from a script, which leaves the focus be
    await page.evaluate(() => document.querySelector('button')!.click())
    await expect(input).toHaveValue('')
    await expect(input).toBeFocused()
  })

  test("a click inside a component is not the page's own element's", async ({
    page,
  }) => {
    await page.goto('examples/use_mumu/')
    const heard = await page.evaluate(async () => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      // A click handler on the page's own button, and a component whose
      // own button is clicked: the page's handler is not called for it
      root.innerHTML =
        '<my-opener data-on="toggle=toggle"></my-opener>' +
        '<button data-on="click=pressed">Mine</button>'
      document.body.append(root)
      const calls: string[] = []
      class Page extends App<object> {
        toggle(): void {
          calls.push('toggle')
        }
        pressed(): void {
          calls.push('pressed')
        }
      }
      mountApp(Page, root)
      await new Promise((r) => setTimeout(r, 50))
      root
        .querySelector('my-opener')!
        .shadowRoot!.querySelector('button')!
        .click()
      root.querySelector<HTMLButtonElement>('button[data-on]')!.click()
      return calls
    })
    expect(heard).toEqual(['toggle', 'pressed'])
  })

  test('a dialog closed by Escape calls nothing', async ({ page }) => {
    // small.spec.ts has its Save and its Cancel
    await page.goto('examples/small_dialog/')
    const dialog = page.locator('dialog')
    await page.getByRole('button', { name: 'Rename' }).click()
    await dialog.locator('input[name="name"]').fill('Escaped')
    await page.keyboard.press('Escape')
    await expect(dialog).toHaveCount(0)
    await expect(page.locator('[data-slot="name"]')).toHaveText('world')
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
    await page.goto('examples/use_mumu/')
    const refused = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { App, mountApp } = (window as unknown as { mumu: Api }).mumu
      const mount = () => {
        const root = document.createElement('div')
        document.body.append(root)
        mountApp(class extends App<object> {}, root)
      }
      mount()
      try {
        mount()
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
