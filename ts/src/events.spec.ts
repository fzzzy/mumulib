import { test, expect } from './coverage.fixture'

// events.source against a hub of the test's own: /mumulib/events.sse
// answers each topic's events, labelled, as mumulib's Python server would.
test.describe('Mumulib events', () => {
  test('several streams are heard over one, each as its own', async ({
    page,
  }) => {
    const asked: string[] = []
    await page.route('**/mumulib/events.sse?*', async (route) => {
      asked.push(new URL(route.request().url()).search)
      await route.fulfill({
        headers: { 'content-type': 'text/event-stream' },
        // retry: a long wait before reconnecting, once these are read
        body:
          'retry: 600000\n\n' +
          'event: news.sse open\ndata: \n\n' +
          'event: news.sse message\ndata: "first"\n\n' +
          'event: examples/use_events/weather.sse forecast\ndata: rain\n\n' +
          'event: missing.sse error\ndata: 404\n\n' +
          // After its topic's error: heard by no one
          'event: missing.sse message\ndata: late\n\n' +
          // Another topic's, which no source here listens to
          'event: other.sse message\ndata: unheard\n\n',
      })
    })
    await page.goto('examples/use_events/')
    await expect(page.locator('body[data-listening]')).toBeAttached()
    await expect(page.locator('#heard')).toHaveText(
      'news open 1\n' +
        'news "first"\n' +
        'weather forecast rain\n' +
        'missing error 2\n'
    )
    // One stream for the three, each a topic, relative to the app
    expect(asked).toEqual([
      '?topic=news.sse&topic=examples%2Fuse_events%2Fweather.sse&topic=missing.sse',
    ])

    // One closed: the stream opened again with what is left, not the
    // closed one, nor the one that was no stream
    await page.evaluate(() =>
      (window as unknown as { closeWeather: () => void }).closeWeather()
    )
    await expect.poll(() => asked.length).toBe(2)
    expect(asked[1]).toBe('?topic=news.sse')
  })

  for (const [at, said] of [
    ['/examples', 'without its slash'],
    ['/examples/', 'with its slash'],
  ]) {
    test(`below a prefix, said ${said}, the hub is too, and a topic outside it is named in full`, async ({
      page,
    }) => {
      const asked: string[] = []
      await page.route('**/mumulib/events.sse?*', async (route) => {
        const url = new URL(route.request().url())
        asked.push(url.pathname + url.search)
        await route.fulfill({
          headers: { 'content-type': 'text/event-stream' },
          body:
            'retry: 600000\n\n' +
            'event: use_events_at/own.sse message\ndata: mine\n\n' +
            `event: ${url.origin}/outside.sse message\ndata: theirs\n\n` +
            'event: https://feeds.example/remote.sse message\ndata: far\n\n',
        })
      })
      await page.goto(`examples/use_events_at/?at=${at}`)
      await expect(page.locator('body[data-listening]')).toBeAttached()
      await expect(page.locator('#heard')).toHaveText(
        'own mine\noutside theirs\nremote far\n'
      )
      const origin = new URL(page.url()).origin
      expect(asked).toEqual([
        '/examples/mumulib/events.sse?' +
          [
            'use_events_at/own.sse',
            `${origin}/outside.sse`,
            'https://feeds.example/remote.sse',
          ]
            .map((topic) => `topic=${encodeURIComponent(topic)}`)
            .join('&'),
      ])

      // Every one closed, one twice: the stream is not opened again
      await page.evaluate(() =>
        (window as unknown as { closeAll: () => void }).closeAll()
      )
      await page.waitForTimeout(200)
      expect(asked).toHaveLength(1)
    })
  }

  test('the hub of a Python server, heard by a browser', async ({ page }) => {
    // The editors example, py/examples/editors.py: a mumulib app, so the hub
    // is its, and its change stream a topic like any other
    const editors = `http://127.0.0.1:${process.env.PLAYWRIGHT_EDITORS_PORT || '8124'}`
    await page.goto(`${editors}/editors/`)
    const heard = await page.evaluate(
      () =>
        new Promise<string[]>((resolve) => {
          const said: string[] = []
          const hub = new EventSource(
            '/mumulib/events.sse?topic=mumulib/changes.sse&topic=nothing.sse'
          )
          const labels = [
            'mumulib/changes.sse open',
            'mumulib/changes.sse ping',
            'nothing.sse error',
          ]
          for (const label of labels) {
            hub.addEventListener(label, (event) => {
              said.push(`${label}: ${(event as MessageEvent<string>).data}`)
              if (said.length === labels.length) {
                hub.close()
                resolve(said)
              }
            })
          }
        })
    )
    expect(heard.sort()).toEqual([
      'mumulib/changes.sse open: ',
      'mumulib/changes.sse ping: {}',
      'nothing.sse error: 404',
    ])
  })
})
