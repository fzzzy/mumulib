import { test, expect } from './coverage.fixture'

// sync.bind against a server of the test's own: /docs/a.json answers each
// version in turn, and the change stream announces what the test says.
test.describe('Mumulib sync', () => {
  test('a bound path is fetched, and fetched again on its announcement', async ({
    page,
  }) => {
    let version = 1
    await page.route('**/docs/a.json', (route) =>
      route.fulfill({ json: { version } })
    )
    await page.route('**/docs/missing.json', (route) =>
      route.fulfill({ status: 404, body: 'not here' })
    )
    // The stream: held until the test says what it announces
    let announce: (urls: string[]) => void = () => {}
    const announced = new Promise<string[]>((resolve) => (announce = resolve))
    await page.route('**/mumulib/changes.sse', async (route) => {
      const urls = await announced
      await route.fulfill({
        headers: { 'content-type': 'text/event-stream' },
        // retry: a long wait before reconnecting, once these are read
        body:
          'retry: 600000\n\n' +
          urls.map((url) => `data: ${JSON.stringify(url)}\n\n`).join(''),
      })
    })
    await page.goto('examples/use_sync/')
    await expect(page.locator('body[data-bound]')).toBeAttached()
    await expect(page.locator('#doc')).toHaveText('{"version":1}')
    // A path is needed, a slash is not a resource, and a 404 is said
    await expect(page.locator('#errors')).toHaveText(
      'bind needs a path in the state tree; ' +
        '/docs/ is a slash: bind a resource or a persist; ' +
        '/docs/missing.json answered 404; '
    )
    version = 2
    // Another URL, and then its own, with an extension and without
    announce(['/docs/b', '/docs/a.json'])
    await expect(page.locator('#doc')).toHaveText('{"version":2}')
  })

  test('an announcement matches as a path, without extension, query or fragment', async ({
    page,
  }) => {
    // Each fetch of /docs/a.json counted, its count the version answered
    let fetches = 0
    await page.route('**/docs/a.json', (route) =>
      route.fulfill({ json: { version: ++fetches } })
    )
    await page.route('**/docs/missing.json', (route) =>
      route.fulfill({ status: 404, body: 'not here' })
    )
    await page.route('**/mumulib/changes.sse', (route) =>
      route.fulfill({
        headers: { 'content-type': 'text/event-stream' },
        body:
          'retry: 600000\n\n' +
          [
            // Not /docs/a: a slash is another URL, and so is a longer name,
            // and a relative URL is the page's directory's
            '/docs/a/',
            '/docs/ab',
            'a.json',
            // /docs/a, whatever it is asked as
            '/docs/a.html?x=1#y',
            '/docs/a',
          ]
            .map((url) => `data: ${JSON.stringify(url)}\n\n`)
            .join(''),
      })
    )
    await page.goto('examples/use_sync/')
    await expect(page.locator('body[data-bound]')).toBeAttached()
    // The first fetch, and one for each of the two that match
    await expect(page.locator('#doc')).toHaveText('{"version":3}')
    await page.waitForTimeout(300)
    expect(fetches).toBe(3)
  })
})
