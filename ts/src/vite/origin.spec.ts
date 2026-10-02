import { test, expect } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import { relativeLoads, withOrigin } from './origin.mjs'

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
<p>A sentence about /vite/ and ${BASE}, unquoted, is left as it is.</p>`
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
      '<!doctype html><script type="module" src="./main.ts"></script>'
    )
    fs.writeFileSync(path.join(root, 'bad', 'main.ts'), 'console.log(1)\n')
    const config = path.join(root, 'vite.config.mjs')
    fs.writeFileSync(
      config,
      `import { originPlugin } from ${JSON.stringify(path.resolve('src/vite/origin.mjs'))}
export default { root: ${JSON.stringify(root)}, base: '${BASE}', plugins: [originPlugin()],
  build: { outDir: ${JSON.stringify(path.join(root, 'out'))},
    rolldownOptions: { input: ${JSON.stringify(path.join(root, 'bad', 'index.html'))} } } }`
    )
    const run = spawnSync('npx', ['vite', 'build', '--config', config], {
      encoding: 'utf8',
    })
    fs.rmSync(root, { recursive: true, force: true })
    expect(run.status).not.toBe(0)
    expect(run.stdout + run.stderr).toContain(
      'loads ./main.ts by a relative URL'
    )
  })
})
