import { test, expect } from '@playwright/test'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'
import { pageEntries } from '../../scripts/page-entries.mjs'

test('every index.html under the pages, at any depth, is an entry', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'pages-'))
  const files = [
    'index.html',
    'notes/index.html',
    'notes/settings/index.html',
    'notes/about.html',
    'notes/counter.sfc.html',
    'notes/main.ts',
  ]
  for (const file of files) {
    fs.mkdirSync(path.dirname(path.join(root, file)), { recursive: true })
    fs.writeFileSync(path.join(root, file), '')
  }
  const entries = pageEntries(root)
  fs.rmSync(root, { recursive: true, force: true })
  expect(entries).toEqual({
    index: path.join(root, 'index.html'),
    notes: path.join(root, 'notes/index.html'),
    'notes/settings': path.join(root, 'notes/settings/index.html'),
  })
})
