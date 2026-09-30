import * as fs from 'node:fs'
import * as path from 'node:path'
import { createCoverageMap } from 'istanbul-lib-coverage'
import { createSourceMapStore } from 'istanbul-lib-source-maps'
import { test, expect } from '../coverage.fixture'

const COUNTER = path.join(
  __dirname,
  '..',
  '..',
  'examples',
  'use_sfc',
  'counter.sfc.html'
)

// The line in counter.sfc.html of a statement that runs only on a click
function lineOf(text: string): number {
  const lines = fs.readFileSync(COUNTER, 'utf-8').split('\n')
  return lines.findIndex((line) => line.includes(text)) + 1
}

test.describe('Mumulib single-file components', () => {
  test('a component with a script renders and runs it', async ({ page }) => {
    await page.goto('examples/use_sfc/')
    const count = page.locator('my-counter .count')
    await expect(count).toHaveText('0')
    await page
      .locator('my-counter')
      .getByRole('button', { name: 'Add one' })
      .click()
    await expect(count).toHaveText('1')
  })

  test('a component with only a template renders it', async ({ page }) => {
    await page.goto('examples/use_sfc/')
    await expect(page.locator('my-greeting p')).toHaveText(
      'Hello from a component with no script'
    )
  })

  test("a component's styles stay inside it", async ({ page }) => {
    await page.goto('examples/use_sfc/')
    const inside = page.locator('my-counter p')
    await expect(inside).toHaveCSS('color', 'rgb(0, 128, 0)')
    await expect(page.locator('p.outside')).not.toHaveCSS(
      'color',
      'rgb(0, 128, 0)'
    )
  })

  test("a component's script is counted, at its own lines", async ({
    page,
  }) => {
    await page.goto('examples/use_sfc/')
    await page
      .locator('my-counter')
      .getByRole('button', { name: 'Add one' })
      .click()
    await expect(page.locator('my-counter .count')).toHaveText('1')

    const raw = await page.evaluate(
      () => (window as unknown as { __coverage__?: object }).__coverage__
    )
    expect(raw, 'the tests serve the examples instrumented').toBeTruthy()
    // istanbul records positions in the generated code, with the source map
    // beside them; remapped, they are positions in the .sfc.html
    const remapped = await createSourceMapStore().transformCoverage(
      createCoverageMap(raw as never)
    )
    const file = remapped.files().find((f) => f.endsWith('counter.sfc.html'))
    expect(file, 'counter.sfc.html is instrumented').toBeTruthy()

    const coverage = remapped.fileCoverageFor(file as string)
    const clicked = lineOf('this.count += 1')
    const hits = Object.entries(coverage.statementMap)
      .filter(([, loc]) => loc.start.line === clicked)
      .map(([id]) => coverage.s[id])
    expect(hits.length, `a statement on line ${clicked}`).toBeGreaterThan(0)
    expect(Math.max(...hits)).toBe(1)
  })
})
