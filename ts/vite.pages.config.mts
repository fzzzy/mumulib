import { defineConfig } from 'vite'
import { resolve } from 'node:path'
import { rootRelativePlugin } from './src/vite/origin.mjs'
import { sfcPlugin } from './src/vite/sfc.mjs'
import { pageEntries } from './scripts/page-entries.mjs'

// The pages mumulib's Python server serves: each index.html under pages/,
// at any depth, is an entry, a Page("notes/index.html") or
// Page("notes/settings/index.html") in Python. Everything is under
// /mumulib-vite/, Vite's base, which Python keeps for it.
//
// `vite --config vite.pages.config.mts` is the dev server, always on 5757,
// on this machine alone: with MUMULIB_DEVELOPMENT=1, Python asks it for each
// page and passes everything under /mumulib-vite/ on to it -- modules, and
// the hot reloading websocket -- so a page has one origin, Python's, and
// reaches Vite over whatever Python speaks: HTTP/2, over TLS.
// `vite build --config vite.pages.config.mts` bundles and code-splits them
// into build/pages, which Python serves under /mumulib-vite/ in production.
//
// The library's own fixtures, and its build, are vite.config.mts's.
const root = resolve(import.meta.dirname, 'pages')
const PORT = 5757

const entries = pageEntries(root)

export default defineConfig({
  root,
  base: '/mumulib-vite/',
  appType: 'mpa',
  // A cache of its own: sharing node_modules/.vite with vite.config.mts's
  // server, each would re-optimize the other's dependencies out from under it
  cacheDir: resolve(import.meta.dirname, 'node_modules/.vite-pages'),
  plugins: [sfcPlugin(), rootRelativePlugin()],
  resolve: {
    // mumulib, and each of its parts, `mumulib/mumu`, from source
    alias: [
      {
        find: /^mumulib$/,
        replacement: resolve(import.meta.dirname, 'src/index.ts'),
      },
      {
        find: /^mumulib\/(state|patslot|dialog|events|sync|mumu|app)$/,
        replacement: resolve(import.meta.dirname, 'src/$1.ts'),
      },
    ],
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
