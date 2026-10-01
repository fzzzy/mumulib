import { spawnSync } from 'node:child_process'
import * as path from 'node:path'
import { test, expect } from '@playwright/test'

const ROOT = path.join(__dirname, '..', '..')
const FIXTURES = path.join(__dirname, 'test_fixtures')

// The checker as a project's Makefile would run it
function check(...paths: string[]) {
  const run = spawnSync('node', ['src/vite/sfc-check.mjs', ...paths], {
    cwd: ROOT,
    encoding: 'utf-8',
  })
  const errors = [...run.stdout.matchAll(/:(\d+):(\d+) - error TS(\d+):/g)].map(
    ([, line, column, code]) => ({
      line: Number(line),
      column: Number(column),
      code: Number(code),
    })
  )
  return { status: run.status, stdout: run.stdout, errors }
}

// Node alone; no page, so no browser and no coverage to keep
test.describe('Mumulib single-file component type checking', () => {
  test('the examples have no type errors', () => {
    const run = check('examples')
    expect(run.stdout).toContain('3 components, no type errors.')
    expect(run.status).toBe(0)
  })

  test('errors are reported at their place in the .sfc.html', () => {
    const run = check(path.join(FIXTURES, 'broken.sfc.html'))
    expect(run.errors).toEqual([
      // const count: number = 'not a number'
      { line: 8, column: 11, code: 2322 },
      // this.missingMethod(count)
      { line: 9, column: 10, code: 2339 },
    ])
    expect(run.stdout).toContain('src/vite/test_fixtures/broken.sfc.html:8:11')
    expect(run.status).toBe(1)
  })

  test('an error on the <script> line has its column there', () => {
    const run = check(path.join(FIXTURES, 'inline.sfc.html'))
    // <script>const label: string = 42
    expect(run.errors).toEqual([{ line: 2, column: 15, code: 2322 }])
  })
})
