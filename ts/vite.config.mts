import { defineConfig } from 'vite'
import istanbul from 'vite-plugin-istanbul'
import { resolve } from 'node:path'
import { sfcPlugin } from './src/vite/sfc.mjs'

const root = import.meta.dirname
const entry = resolve(root, 'src/index.ts')

// A DOM for Node, where the templating and dialog code have none of their own:
// domino's document, and the element classes the code checks with instanceof.
// Each is set only if missing, so a DOM already there -- jsdom in someone's
// tests -- is left alone. The browser build needs no such thing.
const DOM_CLASSES = [
  'Node',
  'Element',
  'HTMLElement',
  'HTMLInputElement',
  'HTMLSelectElement',
  'HTMLTextAreaElement',
  'HTMLFormElement',
  'HTMLDialogElement',
]
const domFromDomino = (domino: string) =>
  `if (typeof document === 'undefined') {
  const window = ${domino}.createWindow('');
  globalThis.document = window.document;
  for (const name of ${JSON.stringify(DOM_CLASSES)}) globalThis[name] ??= window[name];
}`
const dominoEsm = `import domino from 'domino';\n${domFromDomino('domino')}`
const dominoCjs = domFromDomino("require('domino')")

// `vite` serves the examples from source, with `mumulib` resolving to src/.
// `vite build` writes the browser bundle; `vite build --mode node` the two
// Node bundles. The paths are the ones package.json exports; the .sfc.html
// plugin is JavaScript already, and the build copies it as it is.
export default defineConfig(({ mode }) => ({
  plugins: [
    // The examples' own components go through the plugin as it ships
    sfcPlugin(),
    // Counters in src/ for the Playwright tests to collect, when the dev
    // server is started with VITE_COVERAGE=true -- as the tests start it.
    // vite-plugin-istanbul from npm: its synthetic map is for Vue alone, and
    // a .sfc.html takes the ordinary path. The sfc example is counted too, as
    // proof that a component's script can be.
    istanbul({
      include: ['src/**', 'examples/use_sfc/**'],
      extension: ['.ts', '.html'],
      requireEnv: true,
    }),
  ],
  resolve: {
    alias: { mumulib: entry },
  },
  // The pages, not every .html under the root: the sfc checker's fixtures
  // are components, and deliberately wrong ones
  optimizeDeps: {
    entries: ['index.html', 'examples/**/index.html'],
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
    // The editors example's data is the Python server's, py/examples/editors.py:
    // make run SERVER=editors runs it on 8001, and the tests on a port of
    // their own, named by EDITORS_API
    proxy: {
      '/editors': process.env.EDITORS_API || 'http://127.0.0.1:8001',
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
              {
                format: 'es',
                entryFileNames: 'esm/index.mjs',
                banner: dominoEsm,
              },
              {
                format: 'cjs',
                entryFileNames: 'cjs/index.cjs',
                banner: dominoCjs,
                exports: 'named',
              },
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
