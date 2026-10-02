import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as os from 'node:os'
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
  test('the examples have no type errs', () => {
    const run = check('--project', 'tsconfig.examples.json', 'examples')
    expect(run.stdout).toContain(
      "2 components and tsconfig.examples.json's files, no type errs."
    )
    expect(run.status).toBe(0)
  })

  test('errs are reported at their place in the .sfc.html', () => {
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

  test('an err on the <script> line has its column there', () => {
    const run = check(path.join(FIXTURES, 'inline.sfc.html'))
    // <script>const label: string = 42
    expect(run.errors).toEqual([{ line: 2, column: 15, code: 2322 }])
  })

  test("an importer sees a component's own class", () => {
    // tally.count = 'many', where count is the component's number
    const typed = path.join(FIXTURES, 'typed')
    const run = check('--project', path.join(typed, 'tsconfig.json'), typed)
    expect(run.errors).toEqual([{ line: 5, column: 1, code: 2322 }])
    expect(run.stdout).toContain('src/vite/test_fixtures/typed/use.ts:5:1')
    expect(run.status).toBe(1)
  })

  test('--declarations writes what tsc reads for a component', () => {
    // A copy of the fixture, the run's own: both browsers run this at once
    const typed = fs.mkdtempSync(path.join(os.tmpdir(), 'sfc-typed-'))
    for (const name of ['tally.sfc.html', 'use.ts']) {
      fs.copyFileSync(
        path.join(FIXTURES, 'typed', name),
        path.join(typed, name)
      )
    }
    const tsconfig = path.join(typed, 'tsconfig.json')
    const config = JSON.parse(
      fs.readFileSync(path.join(FIXTURES, 'typed', 'tsconfig.json'), 'utf-8')
    )
    config.include = ['*.ts', path.join(__dirname, 'sfc-client.d.ts')]
    fs.writeFileSync(tsconfig, JSON.stringify(config))
    try {
      const run = check('--project', tsconfig, '--declarations', typed)
      expect(run.stdout).toContain('Wrote 1 declaration')
      expect(
        fs.readFileSync(path.join(typed, 'tally.sfc.html.d.ts'), 'utf-8')
      ).toContain('export default class Tally extends HTMLElement')
      // And tsc alone, with no checker, now knows the component's class
      const tsc = spawnSync(
        'npx',
        ['tsc', '--pretty', 'false', '-p', tsconfig],
        { cwd: ROOT, encoding: 'utf-8' }
      )
      expect(tsc.stdout).toContain(
        "use.ts(5,1): error TS2322: Type 'string' is not assignable to type 'number'."
      )
    } finally {
      fs.rmSync(typed, { recursive: true, force: true })
    }
  })
})
