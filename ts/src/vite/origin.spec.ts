import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import {
  LIBRARY_PARTS,
  isLibrary,
  libraryImportMap,
  relativeLoads,
  withOrigin,
} from './origin.mjs'

const BASE = '/mumulib-vite/'
const ORIGIN = 'http://127.0.0.1:5757'

test.describe('The origin plugin', () => {
  test('each quoted URL under the base names the dev server in full', () => {
    const html = `<script type="module" src="${BASE}@vite/client"></script>
<link rel="stylesheet" href='${BASE}notes/style.css'>
<p>A sentence about /vite/ and ${BASE}, unquoted, is left as it is.</p>`
    expect(withOrigin(html, BASE, ORIGIN)).toBe(
      `<script type="module" src="${ORIGIN}${BASE}@vite/client"></script>
<link rel="stylesheet" href='${ORIGIN}${BASE}notes/style.css'>
<p>A sentence about /vite/ and ${BASE}, unquoted, is left as it is.</p>`,
    )
  })

  test('a relative src, or link href, is what it finds', () => {
    const html = `<script src="./main.ts"></script>
<script src="/notes/main.ts"></script>
<link rel="stylesheet" href="style.css">
<link rel="icon" href="data:,">
<img src=photo.png>
<img src="https://example.com/a.png">
<a href="other.html">another page</a>`
    expect(relativeLoads(html)).toEqual(['./main.ts', 'style.css', 'photo.png'])
  })

  test('an entry loading by a relative URL fails to build', () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'origin-'))
    fs.mkdirSync(path.join(root, 'bad'))
    fs.writeFileSync(
      path.join(root, 'bad', 'index.html'),
      '<!doctype html><script type="module" src="./main.ts"></script>',
    )
    fs.writeFileSync(path.join(root, 'bad', 'main.ts'), 'console.log(1)\n')
    const config = path.join(root, 'vite.config.mjs')
    fs.writeFileSync(
      config,
      `import { originPlugin } from ${JSON.stringify(path.resolve('src/vite/origin.mjs'))}
export default { root: ${JSON.stringify(root)}, base: '${BASE}', plugins: [originPlugin()],
  build: { outDir: ${JSON.stringify(path.join(root, 'out'))},
    rolldownOptions: { input: ${JSON.stringify(path.join(root, 'bad', 'index.html'))} } } }`,
    )
    const run = spawnSync('npx', ['vite', 'build', '--config', config], {
      encoding: 'utf8',
    })
    fs.rmSync(root, { recursive: true, force: true })
    expect(run.status).not.toBe(0)
    expect(run.stdout + run.stderr).toContain(
      'loads ./main.ts by a relative URL',
    )
  })

  test("the dev server will not start under Vite's default base", () => {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'origin-'))
    const config = path.join(root, 'vite.config.mjs')
    fs.writeFileSync(
      config,
      `import { originPlugin } from ${JSON.stringify(path.resolve('src/vite/origin.mjs'))}
export default { root: ${JSON.stringify(root)}, plugins: [originPlugin()],
  server: { port: 0 } }`,
    )
    const run = spawnSync('npx', ['vite', '--config', config], {
      encoding: 'utf8',
      timeout: 30000,
    })
    fs.rmSync(root, { recursive: true, force: true })
    expect(run.signal).toBeNull()
    expect(run.status).not.toBe(0)
    expect(run.stdout + run.stderr).toContain(
      'originPlugin needs a base of its own',
    )
  })
})

test.describe('The server library plugin', () => {
  test("the import map names each of mumulib's modules where Python serves it", () => {
    const { imports } = libraryImportMap()
    expect(imports['mumulib']).toBe('/mumulib/browser/mumulib.mjs')
    expect(imports['mumulib/app']).toBe('/mumulib/browser/app.mjs')
    expect(Object.keys(imports)).toHaveLength(8)
  })

  test("package.json exports each part, and the build's list is the same", () => {
    const { exports } = JSON.parse(
      fs.readFileSync(
        path.join(__dirname, '..', '..', 'package.json'),
        'utf-8',
      ),
    )
    const parts = Object.keys(exports)
      .map((name) => name.slice(2))
      .filter((name) => LIBRARY_PARTS.includes(name))
    expect(parts).toEqual(LIBRARY_PARTS)
    for (const part of LIBRARY_PARTS) {
      expect(exports[`./${part}`].browser, part).toBe(
        `./dist/browser/src/${part}.mjs`,
      )
    }
  })

  test('only mumulib, and its parts, are left out of a build', () => {
    expect(isLibrary('mumulib')).toBe(true)
    expect(isLibrary('mumulib/sync')).toBe(true)
    expect(isLibrary('mumulib/vite-plugin-sfc')).toBe(false)
    expect(isLibrary('mumulibrary')).toBe(false)
    expect(isLibrary('./mumulib')).toBe(false)
  })
})
