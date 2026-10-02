import { defineConfig } from 'vite'
import * as fs from 'node:fs'
import { resolve } from 'node:path'
import { originPlugin } from './src/vite/origin.mjs'
import { sfcPlugin } from './src/vite/sfc.mjs'

// The pages mumulib's Python server serves: each pages/<name>/index.html is
// an entry, a Page("<name>/index.html") in Python. Everything is under
// /vite/, Vite's base, which Python keeps for it.
//
// `vite --config vite.pages.config.mts` is the dev server, always on 5757:
// a page served by Python, with MUMULIB_DEVELOPMENT=1, names it in full, and
// the browser fetches its modules and opens hot reloading from it directly.
// `vite build --config vite.pages.config.mts` bundles and code-splits them
// into build/pages, which Python serves under /vite/ in production.
//
// The library's own examples, and its build, are vite.config.mts's.
const root = resolve(import.meta.dirname, 'pages')
const PORT = 5757
const ORIGIN = `http://127.0.0.1:${PORT}`

const entries = Object.fromEntries(
  fs
    .readdirSync(root, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .filter((entry) => fs.existsSync(resolve(root, entry.name, 'index.html')))
    .map((entry) => [entry.name, resolve(root, entry.name, 'index.html')])
)

export default defineConfig({
  root,
  base: '/vite/',
  appType: 'mpa',
  // A cache of its own: sharing node_modules/.vite with vite.config.mts's
  // server, each would re-optimize the other's dependencies out from under it
  cacheDir: resolve(import.meta.dirname, 'node_modules/.vite-pages'),
  plugins: [sfcPlugin(), originPlugin(ORIGIN)],
  resolve: {
    alias: { mumulib: resolve(import.meta.dirname, 'src/index.ts') },
  },
  server: {
    host: '127.0.0.1',
    port: PORT,
    strictPort: true,
    // As vite.config.mts's: the page's console in the server's output
    forwardConsole: {
      unhandledErrors: true,
      logLevels: ['error', 'warn', 'info', 'log', 'debug'],
    },
  },
  build: {
    outDir: resolve(import.meta.dirname, 'build/pages'),
    emptyOutDir: true,
    rolldownOptions: { input: entries },
  },
})
