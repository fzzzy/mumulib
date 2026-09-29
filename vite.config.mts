import { defineConfig } from 'vite'
import istanbul from 'vite-plugin-istanbul'
import { resolve } from 'node:path'

const root = import.meta.dirname
const entry = resolve(root, 'src/index.ts')

// A DOM for Node, where the templating and dialog code have none of their own.
// The browser build needs no such thing.
const dominoEsm = "import domino from 'domino';\nif (typeof document === 'undefined') globalThis.document = domino.createWindow('').document;"
const dominoCjs = "if (typeof document === 'undefined') globalThis.document = require('domino').createWindow('').document;"

// `vite` serves the examples from source, with `mumulib` resolving to src/.
// `vite build` writes the browser bundle; `vite build --mode node` writes the
// two Node bundles. The paths are the ones package.json exports.
export default defineConfig(({ mode }) => ({
  plugins: [
    // Counters in src/ for the Playwright tests to collect, when the dev
    // server is started with VITE_COVERAGE=true -- as the tests start it.
    // The fork is the one s2smde, ltui and agent_daedalus use.
    istanbul({
      include: 'src/**',
      extension: ['.ts'],
      requireEnv: true,
    }),
  ],
  resolve: {
    alias: { mumulib: entry },
  },
  server: {
    host: '127.0.0.1',
    port: Number(process.env.PORT || 8000),
    strictPort: true,
    // The page's console in the server's output, and so in var/log: every
    // level, and uncaught errors. Vite turns this on by itself only when it
    // thinks an AI agent started it, and then for warnings and errors only.
    forwardConsole: {
      unhandledErrors: true,
      logLevels: ['error', 'warn', 'info', 'log', 'debug'],
    },
  },
  build:
    mode === 'node'
      ? {
          outDir: 'dist',
          emptyOutDir: false,
          sourcemap: true,
          minify: false,
          target: 'node20',
          lib: { entry, formats: ['es', 'cjs'] },
          rolldownOptions: {
            external: ['domino'],
            output: [
              { format: 'es', entryFileNames: 'esm/index.mjs', banner: dominoEsm },
              { format: 'cjs', entryFileNames: 'cjs/index.cjs', banner: dominoCjs, exports: 'named' },
            ],
          },
        }
      : {
          outDir: 'dist/browser/src',
          emptyOutDir: false,
          sourcemap: true,
          target: 'es2020',
          lib: { entry, formats: ['es'], fileName: () => 'index.mjs' },
        },
}))
