import { test, expect } from './coverage.fixture'

// The components are examples/use_mumu's. Each test makes its own elements
// on that page, sets their state as an owner would, and reads what shows.

test.describe('Mumulib Mumu components', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('examples/use_mumu/')
  })

  test('a component renders its state, and asks for changes', async ({
    page,
  }) => {
    const button = page.locator('my-opener button')
    const panel = page.locator('my-opener .panel')
    await expect(button).toHaveText('Open')
    await expect(panel).toBeHidden()

    await button.click()
    await expect(button).toHaveText('Close')
    await expect(button).toHaveClass('open')
    // A boolean adds or removes the attribute it fills.
    await expect(panel).toBeVisible()

    await button.click()
    await expect(button).toHaveText('Open')
    await expect(panel).toBeHidden()
  })

  test('a component hands state to the components inside it', async ({
    page,
  }) => {
    // data-prop, on one element and on each row of a list.
    await expect(page.locator('my-lights .main .light')).toHaveText('○')
    await expect(
      page.locator('my-lights [data-pat="foreach"] .light')
    ).toHaveText(['●', '○', '●'])
    // The opener's toggle turns the main light on, through the page's state.
    await page.locator('my-opener button').click()
    await expect(page.locator('my-lights .main .light')).toHaveText('●')
  })

  test('a method named for an event, in any case, handles it', async ({
    page,
  }) => {
    const heard = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { Mumu, mumuElement } = (window as unknown as { mumu: Api }).mumu
      const template = document.createElement('template')
      template.innerHTML = '<input />'
      const heard: string[] = []
      customElements.define(
        'my-hearing',
        mumuElement(
          class Hearing extends Mumu<object> {
            static template = template
            // focus does not bubble: heard all the same.
            onFocus(): void {
              heard.push('focus')
            }
            onKeydown(event: KeyboardEvent): void {
              heard.push(`keydown ${event.key}`)
            }
            onPointerCancel(): void {
              heard.push('pointercancel')
            }
          }
        )
      )
      const el = document.createElement('my-hearing')
      document.body.append(el)
      const input = el.shadowRoot!.querySelector('input')!
      input.focus()
      input.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'a', bubbles: true })
      )
      input.dispatchEvent(new PointerEvent('pointercancel', { bubbles: true }))
      return heard
    })
    expect(heard).toEqual(['focus', 'keydown a', 'pointercancel'])
  })

  test('a view draws a component into markup already in the page', async ({
    page,
  }) => {
    const seen = await page.evaluate(async () => {
      const settle = () => new Promise((r) => setTimeout(r, 50))
      type Api = typeof import('./index')
      const { Mumu, mumuView } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      root.innerHTML =
        '<p data-slot="label">sample</p>' +
        '<ul data-slot="rows"><li data-pat="foreach" data-slot="text">row</li></ul>' +
        '<button data-attr="disabled=done">Go</button>'
      document.body.append(root)
      let renders = 0
      class Counter extends Mumu<{ count: number }> {
        static state = { count: 0 }
        get label(): string {
          renders++
          return `Count ${this.state.count}`
        }
        get rows(): { text: string }[] {
          return Array.from({ length: this.state.count }, (_, i) => ({
            text: `row ${i}`,
          }))
        }
        get done(): boolean {
          return this.state.count >= 2
        }
        onClick(): void {
          this.emit('go', this.state.count)
        }
      }
      const asked: unknown[] = []
      root.addEventListener('go', (e) => asked.push((e as CustomEvent).detail))
      const view = mumuView<{ count: number }>(Counter, root)
      await settle()
      const first = root.querySelector('p')!.textContent
      root.querySelector('button')!.click()
      view.set({ count: 2 })
      const once = renders
      view.set({ count: 2 })
      await settle()
      return {
        first,
        label: root.querySelector('p')!.textContent,
        rows: [...root.querySelectorAll('li')].map((li) => li.textContent),
        disabled: root.querySelector('button')!.disabled,
        sameRendersNothing: renders === once,
        asked,
      }
    })
    expect(seen).toEqual({
      first: 'Count 0',
      label: 'Count 2',
      rows: ['row 0', 'row 1'],
      disabled: true,
      sameRendersNothing: true,
      asked: [0],
    })
  })

  test('a row in a template is inert until it is copied in', async ({
    page,
  }) => {
    const seen = await page.evaluate(async () => {
      const settle = () => new Promise((r) => setTimeout(r, 50))
      type Api = typeof import('./index')
      const { Mumu, mumuView } = (window as unknown as { mumu: Api }).mumu
      const root = document.createElement('div')
      root.innerHTML =
        '<div data-slot="row"><template data-pat="foreach">' +
        '<my-light data-prop="connected=on"></my-light>' +
        '</template><p>Loading</p></div>' +
        // A data-prop of the component's own, beside the rows: setting it
        // passes the rows' by.
        '<my-light class="own" data-prop="connected=lit"></my-light>'
      document.body.append(root)
      const before = root.querySelectorAll('[data-slot] my-light').length
      class Lit extends Mumu<{ on: boolean[] }> {
        static state = { on: [true, false] }
        get row(): { on: boolean }[] {
          return this.state.on.map((on) => ({ on }))
        }
        get lit(): boolean {
          return false
        }
      }
      mumuView(Lit, root)
      await settle()
      const lights = [...root.querySelectorAll('[data-slot] my-light')]
      const own = root.querySelector('my-light.own')!
      return {
        before,
        own: own.shadowRoot!.querySelector('.light')!.textContent,
        faces: lights.map(
          (l) => l.shadowRoot!.querySelector('.light')!.textContent
        ),
        // The template, and the sample content beside it, are replaced.
        left: root.querySelectorAll('template, p').length,
      }
    })
    expect(seen).toEqual({
      before: 0,
      own: '○',
      faces: ['●', '○'],
      left: 0,
    })
  })

  test('rows are kept from one list to the next', async ({ page }) => {
    const kept = await page.evaluate(async () => {
      const settle = () => new Promise((r) => setTimeout(r, 50))
      type Props = HTMLElement & Record<string, unknown>
      const rows = (el: Element, sel: string) => [
        ...el.shadowRoot!.querySelectorAll(sel),
      ]

      // By position: lines that only grow.
      const lines = document.createElement('my-lines') as Props
      document.body.append(lines)
      lines.lines = ['one', 'two']
      await settle()
      const [one, two] = rows(lines, '.line')
      lines.lines = ['one', 'two', 'three']
      await settle()
      const grown = rows(lines, '.line')
      const grownTexts = grown.map((r) => r.textContent!.trim())
      lines.lines = ['one', 'TWO', 'three']
      await settle()
      const changed = rows(lines, '.line')

      // By key: the oldest message leaves from the top.
      const chat = document.createElement('my-messages') as Props
      document.body.append(chat)
      chat.messages = [
        { id: 1, text: 'a' },
        { id: 2, text: 'b' },
        { id: 3, text: 'c' },
      ]
      await settle()
      const [, b, c] = rows(chat, '.message')
      chat.messages = [
        { id: 2, text: 'b' },
        { id: 3, text: 'c' },
      ]
      await settle()
      const left = rows(chat, '.message')
      return {
        grownKept: grown[0] === one && grown[1] === two,
        grownTexts,
        changedSameRow: changed[1] === two,
        changedText: changed[1].textContent!.trim(),
        chatKept: left[0] === b && left[1] === c,
        chatTexts: left.map((r) => r.textContent!.trim()),
      }
    })
    expect(kept).toEqual({
      grownKept: true,
      grownTexts: ['one', 'two', 'three'],
      changedSameRow: true,
      changedText: 'TWO',
      chatKept: true,
      chatTexts: ['b', 'c'],
    })
  })

  test('a row moved keeps the focus it had', async ({ page }) => {
    // Another's change reorders the list while the reader is on a row: the
    // row moves, and the reader is still on it, where they were typing
    const kept = await page.evaluate(async () => {
      const settle = () => new Promise((r) => setTimeout(r, 50))
      const chat = document.createElement('my-messages') as HTMLElement &
        Record<string, unknown>
      document.body.append(chat)
      chat.messages = [
        { id: 1, text: 'a' },
        { id: 2, text: 'b' },
        { id: 3, text: 'c' },
      ]
      await settle()
      const root = chat.shadowRoot!
      const c = root.querySelectorAll<HTMLElement>('.message')[2]
      c.tabIndex = -1
      c.focus()
      const before = root.activeElement === c
      // c to the top: it has to move
      chat.messages = [
        { id: 3, text: 'c' },
        { id: 1, text: 'a' },
        { id: 2, text: 'b' },
      ]
      await settle()
      return {
        before,
        moved: root.querySelectorAll('.message')[0] === c,
        focused: root.activeElement === c,
      }
    })
    expect(kept).toEqual({ before: true, moved: true, focused: true })
  })

  test('a render writes only what changed', async ({ page }) => {
    const written = await page.evaluate(async () => {
      const settle = () => new Promise((r) => setTimeout(r, 50))
      const light = document.createElement('my-light') as HTMLElement &
        Record<string, unknown>
      document.body.append(light)
      light.connected = true
      await settle()
      const changes: string[] = []
      const watch = new MutationObserver((records) => {
        for (const r of records) {
          changes.push(r.type === 'attributes' ? r.attributeName! : r.type)
        }
      })
      watch.observe(light.shadowRoot!, {
        subtree: true,
        childList: true,
        characterData: true,
        attributes: true,
      })
      light.holder = 'wizard'
      await settle()
      watch.disconnect()
      return [...new Set(changes)]
    })
    // The tooltip, and not the face, which did not change.
    expect(written).toEqual(['title'])
  })

  test('setting the same value renders nothing', async ({ page }) => {
    const renders = await page.evaluate(() => {
      const light = document.createElement('my-light') as HTMLElement &
        Record<string, unknown>
      document.body.append(light)
      // Count renders by the getter each one reads.
      let count = 0
      const delegate = light.delegate as object
      const face = Object.getOwnPropertyDescriptor(
        Object.getPrototypeOf(delegate),
        'face'
      )!.get!
      Object.defineProperty(delegate, 'face', {
        get() {
          count++
          return face.call(this)
        },
      })
      light.connected = true
      const once = count
      light.connected = true
      return [once, count]
    })
    expect(renders).toEqual([1, 1])
  })

  test('properties set together all show', async ({ page }) => {
    // The first render's fill, still under way, does not land over the
    // second's.
    const shown = await page.evaluate(async () => {
      const room = document.createElement('my-room') as HTMLElement &
        Record<string, unknown>
      document.body.append(room)
      room.number = '1 1'
      room.person = { name: 'Coolio' }
      await new Promise((r) => setTimeout(r, 50))
      const div = room.shadowRoot!.querySelector('div')!
      return [div.className, div.textContent!.replace(/\s+/g, ' ').trim()]
    })
    expect(shown).toEqual(['room occupied', '101 Coolio'])
  })

  test('a component that is defined, or given a list, wrongly is refused', async ({
    page,
  }) => {
    const refused = await page.evaluate(() => {
      type Api = typeof import('./index')
      const { Mumu, mumuElement } = (window as unknown as { mumu: Api }).mumu
      const template = document.createElement('template')
      const error = (make: () => unknown) => {
        try {
          make()
          return ''
        } catch (e) {
          return (e as Error).message
        }
      }
      return [
        error(() =>
          mumuElement(
            class Setter extends Mumu<{ open: boolean }> {
              static template = template
              static state = { open: false }
              set open(_: boolean) {}
            }
          )
        ),
        error(() =>
          mumuElement(
            class Titled extends Mumu<{ title: string }> {
              static template = template
              static state = { title: '' }
            }
          )
        ),
        error(() => {
          const two = document.createElement('template')
          two.innerHTML =
            '<ul data-slot="rows"><li data-pat="foreach"></li><li data-pat="foreach"></li></ul>'
          mumuElement(
            class Two extends Mumu<{ rows: object[] }> {
              static template = two
              static state = { rows: [] }
            }
          )
        }),
        error(() => {
          const two = document.createElement('template')
          two.innerHTML =
            '<ul data-slot="rows"><template data-pat="foreach"><li></li><li></li></template></ul>'
          mumuElement(
            class TwoInOne extends Mumu<{ rows: object[] }> {
              static template = two
              static state = { rows: [] }
            }
          )
        }),
        error(() => {
          const none = document.createElement('template')
          none.innerHTML = '<ul data-slot="rows"></ul>'
          customElements.define(
            'my-rowless',
            mumuElement(
              class Rowless extends Mumu<{ rows: object[] }> {
                static template = none
                static state = { rows: [] }
              }
            )
          )
          const el = document.createElement('my-rowless') as HTMLElement &
            Record<string, unknown>
          document.body.append(el)
          el.rows = [{ name: 'Ada' }]
        }),
        error(() =>
          mumuElement(
            class Typo extends Mumu<object> {
              static template = template
              onClik(): void {}
            }
          )
        ),
        // Not a component: an element class already, given back as it is.
        error(() => {
          if (mumuElement(HTMLElement) !== HTMLElement)
            throw new Error('changed')
        }),
      ]
    })
    expect(refused[0]).toContain('Setter defines a setter for open')
    expect(refused[1]).toContain('already a property of every element')
    expect(refused[2]).toContain(
      'Two\'s slot rows has 2 data-pat="foreach" rows'
    )
    expect(refused[3]).toContain(
      'TwoInOne\'s slot rows has a data-pat="foreach" template with 2 elements in it; a row is one'
    )
    expect(refused[4]).toContain(
      'Rowless\'s rows is a list of objects, but its slot has no data-pat="foreach" row'
    )
    expect(refused[5]).toContain(
      'Typo.onClik is named for no event: "clik" is not one an element has'
    )
    expect(refused[6]).toBe('')
  })
})
