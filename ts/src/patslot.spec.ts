import { test, expect } from './coverage.fixture'

test.describe('Mumulib PatSlot Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure we have a clean state before each test
    await page.goto('about:blank')
  })

  test('should handle basic pattern slots', async ({ page }) => {
    await page.goto('examples/use_patslot/')

    await page.waitForSelector('dl[data-pat="person"]')

    // Check first person
    const firstPerson = await page.$eval(
      'dl[data-pat="person"]:first-child',
      (el) => ({
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
      })
    )

    expect(firstPerson.name).toBe('John Smith')
    expect(firstPerson.age).toBe('42')

    // Check second person
    const secondPerson = await page.$eval(
      'dl[data-pat="person"]:nth-child(2)',
      (el) => ({
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
        style: el.getAttribute('style'),
      })
    )

    expect(secondPerson.name).toBe('Jane Smith')
    expect(secondPerson.age).toBe('12')
    expect(secondPerson.style).toContain('color: blue')
  })

  test('should handle pattern slot filling', async ({ page }) => {
    await page.goto('examples/use_patslot_fill/')

    await page.waitForSelector('dl[data-attr="style=color"]')

    const personData = await page.$eval('dl', (el) => ({
      style: el.getAttribute('style'),
      name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
      age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
    }))

    expect(personData.name).toBe('Jane Smith')
    expect(personData.age).toBe('12')
    expect(personData.style).toContain('color: blue')

    await page.waitForTimeout(3000)

    const fillContent = await page.$eval(
      '#fill-element [data-slot="fill_me"]',
      (el) => el.textContent?.trim()
    )

    expect(fillContent).toBe('now been filled.')

    // fill: several slots of one element, by name
    await expect(page.locator('#fill-many [data-slot="first"]')).toHaveText(
      'one'
    )
    await expect(page.locator('#fill-many [data-slot="second"]')).toHaveText(
      'two'
    )
  })

  test('should handle pattern slot templates', async ({ page }) => {
    await page.goto('examples/use_patslot_template/')

    await page.waitForSelector('dl[data-pat="person"]')

    const personData: { [key: string]: string } = await page.$eval(
      'dl[data-pat="person"]',
      (el) => ({
        style: el.getAttribute('style')?.toString() || '',
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim() || '',
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim() || '',
        pattern: el.getAttribute('data-pat') || '',
        attrs: el.getAttribute('data-attr') || '',
      })
    )

    const expected = {
      style: 'color: blue',
      name: 'Jane Smith',
      age: '12',
      pattern: 'person',
      attrs: 'style=color',
    }

    for (const [key, value] of Object.entries(expected)) {
      expect(personData[key]).toBe(value)
    }
  })

  test('should handle nested pattern slots', async ({ page }) => {
    await page.goto('examples/use_patslot_nested/')

    await page.waitForSelector('ol[data-slot="towns"]')

    // Check first town
    const firstTown = await page.$eval(
      'li[data-pat="town"]:first-child',
      (el) => ({
        name: el.querySelector('[data-slot="town_name"]')?.textContent?.trim(),
        firstPerson: {
          name: el
            .querySelector(
              'dl[data-pat="person"]:first-child [data-slot="name"]'
            )
            ?.textContent?.trim(),
          age: el
            .querySelector(
              'dl[data-pat="person"]:first-child [data-slot="age"]'
            )
            ?.textContent?.trim(),
        },
      })
    )

    expect(firstTown.name).toBe('Los Angeles')
    expect(firstTown.firstPerson.name).toBe('Joe Smith')
    expect(firstTown.firstPerson.age).toBe('67')

    // Check footer
    const footer = await page.$eval('[data-slot="footer"]', (el) =>
      el.textContent?.trim()
    )
    expect(footer).toBe('This is the footer.')
  })

  test('should handle nodes that are both patterns and slots', async ({
    page,
  }) => {
    await page.goto('examples/use_patslot_pattern_and_slot_node/')

    await page.waitForTimeout(1000)

    // Check that we have two span elements with the expected text
    const spans = await page.$$eval('span[data-slot="hello"]', (elements) =>
      elements.map((el) => el.textContent?.trim())
    )

    expect(spans).toHaveLength(2)
    expect(spans[0]).toBe('Hello World')
    expect(spans[1]).toBe('Bonjour Monde')
  })

  test('any name is found, and filled content keeps its own slots', async ({
    page,
  }) => {
    await page.goto('examples/use_patslot_names/')
    await expect(page.locator('body')).toHaveAttribute('data-filled', 'yes')

    await expect(page.locator('h1')).toHaveText('Town')
    await expect(page.locator('p').first()).toHaveText('dotted')
    await expect(page.locator('p').nth(1)).toHaveText('spaced')
    await expect(page.locator('b')).toHaveAttribute('data-x', 'divided once')
    await expect(page.locator('b')).toHaveAttribute('data-y', 'plain')
    const people = await page.$$eval('li', (items) =>
      items.map((li) => [li.getAttribute('title'), li.textContent?.trim()])
    )
    expect(people).toEqual([
      ['Ada', 'Ada'],
      ['Grace', 'Grace'],
    ])
  })

  test('each shape of pattern fills a slot, appends to one, or sets an attribute', async ({
    page,
  }) => {
    await page.goto('examples/use_patslot_shapes/')
    await expect(page.locator('body')).toHaveAttribute('data-filled', 'yes')

    // One element: a clone in each slot of the name, named as the slot
    await expect(page.locator('#element > *')).toHaveCount(2)
    await expect(page.locator('#element span[data-slot="badge"]')).toHaveText([
      'new',
      'new',
    ])
    await expect(page.locator('#promised')).toHaveText('kept')

    // A generator, and an async one: what was in each slot is gone, both
    // slots of the name are filled, and each generator was run through once
    for (const [id, filled] of [
      ['#sync', ['onetwo', 'onetwo']],
      ['#async', ['threefour', 'threefour']],
    ] as const) {
      await expect(page.locator(`${id} ol`)).toHaveText(filled)
      await expect(page.locator(`${id} li[data-slot="label"]`)).toHaveCount(2)
    }
    await expect(page.locator('body')).toHaveAttribute('data-generated', '1 1')

    // Appended after what is there: an element, text, and an array's parts
    await expect(page.locator('#appended [data-slot="items"] li')).toHaveText([
      'first',
      'second',
    ])
    await expect(page.locator('#appended [data-slot="note"]')).toHaveText(
      'Hello, world'
    )
    await expect(page.locator('#appended [data-slot="more"]')).toHaveText(
      /^\s*first\s*secondthird$/
    )

    // An array, a generator and an async one, each as one attribute
    const attrs = page.locator('#attrs')
    await expect(attrs).toHaveAttribute('title', 'abc')
    await expect(attrs).toHaveAttribute('data-sync', 'xy')
    await expect(attrs).toHaveAttribute('data-async', 'pq')

    // An array of generators, one yielding an array with a promise in it
    await expect(page.locator('#nested')).toHaveText('abcde5')
    await expect(page.locator('#nested li[data-slot="label"]')).toHaveText('e')

    // One generator, whatever takes it: a slot and attributes, or several
    // attributes alone
    await expect(page.locator('#shared p')).toHaveText('redgreen')
    for (const selector of ['#shared p', '#shared b', '#attributes > *']) {
      for (const tagged of await page.locator(selector).all()) {
        await expect(tagged).toHaveAttribute('title', 'redgreen')
      }
    }
    for (const selector of ['#shared b', '#attributes b']) {
      await expect(page.locator(selector)).toHaveAttribute(
        'data-tags',
        'redgreen'
      )
    }

    // A pattern that is not there, and an element for an attribute, however
    // it comes: as itself, from a generator, or from an async one
    await expect(page.locator('#errors li')).toHaveText([
      'No pat named nowhere',
      "Can't set attr to Element",
      "Can't set attr to Element",
      "Can't set attr to Element",
    ])
  })
})
