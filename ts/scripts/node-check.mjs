// mumulib as a Node user gets it: the package packed as it would be
// published, installed into an empty project, and used through require and
// import, where domino is the only DOM. The package is ES modules alone:
// require loads them as Node has since 22.12, and is tested here as such. Nothing else runs the library
// outside a browser, which is how patslot came to throw in Node unnoticed.
import { execFileSync } from 'node:child_process'
import * as fs from 'node:fs'
import * as os from 'node:os'
import * as path from 'node:path'

// Each is run as its own program, and prints its results as JSON
const USES = {
  'use.cjs': `
const { state, patslot } = require('mumulib/node')
${'__BODY__'}`,
  'use.mjs': `
import { state, patslot } from 'mumulib/node'
${'__BODY__'}`,
}

// Plain mumulib sets no globals: with no DOM it cannot load, and says why;
// and mumulib/node leaves a DOM already there -- jsdom's, say -- as it is
const GLOBALS = ['document', 'Node', 'HTMLElement', 'HTMLDialogElement']
const BARE = {
  'bare.cjs': `
let threw = null
try { require('mumulib') } catch (e) { threw = e.message }
process.stdout.write(JSON.stringify({
  threw, set: ${JSON.stringify(GLOBALS)}.filter((name) => name in globalThis),
}))`,
  'bare.mjs': `
let threw = null
try { await import('mumulib') } catch (e) { threw = e.message }
process.stdout.write(JSON.stringify({
  threw, set: ${JSON.stringify(GLOBALS)}.filter((name) => name in globalThis),
}))`,
  'own-dom.mjs': `
import domino from 'domino'
const own = domino.createWindow('').document
globalThis.document = own
const { patslot } = await import('mumulib/node')
process.stdout.write(JSON.stringify({
  kept: globalThis.document === own, filled: typeof patslot.fill_slots,
}))`,
}
const BARE_EXPECTED = {
  'bare.cjs': { threw: 'document is not defined', set: [] },
  'bare.mjs': { threw: 'document is not defined', set: [] },
  'own-dom.mjs': { kept: true, filled: 'function' },
}

// What every use checks: each patslot fill path that touches data-*
// attributes, and state, with its debug mode, which writes one
const BODY = `
const run = async () => {
  const el = document.createElement('div')
  el.innerHTML =
    '<p data-attr="title=who"><span data-slot="who">nobody</span></p>' +
    '<i data-slot="a">a</i><b data-slot="b">b</b>'
  await patslot.fill_slots(el, 'who', 'Node')
  await patslot.fill(el, { a: 'one', b: 'two' })
  const replacement = document.createElement('em')
  replacement.textContent = 'element'
  await patslot.fill_slots(el, 'a', replacement)
  state.debug(true)
  const log = console.log
  console.log = () => {}
  await state.set_state({ who: 'node' })
  state.debug(false)
  console.log = log
  // A handler that sets state again, which state runs on the next frame --
  // or, in Node, the next turn
  let counted = null
  await state.onstate(async (s) => {
    if (s.count === undefined) await state.set_path('count', 1)
    else counted = s.count
  })
  await state.set_state({ go: true })
  await new Promise((resolve) => setTimeout(resolve, 20))
  process.stdout.write(JSON.stringify({
    who: el.querySelector('span').textContent,
    title: el.querySelector('p').getAttribute('title'),
    b: el.querySelector('[data-slot=b]').textContent,
    replaced: el.querySelector('em[data-slot=a]')?.textContent ?? null,
    body: document.body.getAttribute('data-state'),
    counted,
  }))
}
run().catch((e) => { process.stdout.write(JSON.stringify({ error: String(e) })); process.exitCode = 1 })
`

const EXPECTED = {
  who: 'Node',
  title: 'Node',
  b: 'two',
  replaced: 'element',
  // written in debug mode only, which was on for the first state alone
  body: '{"who":"node"}',
  counted: 1,
}

// Each part of the library by its own path, `mumulib/mumu`, through import
// and require: what it exports is the very thing the whole library does --
// a class the same class whichever way it was imported. Each name a part is
// missing, or has as something else, is listed.
const PARTS = {
  state: ['set_state', 'onstate', 'set_path'],
  patslot: ['fill', 'clone_pat'],
  dialog: ['do_dialog'],
  events: ['source', 'at'],
  sync: ['bind'],
  mumu: ['Mumu', 'mumuElement', 'mumuView'],
  app: ['App', 'mountApp'],
}
// The whole library has the older parts as namespaces, `state.set_state`, and
// the components' names as its own
const IN_WHOLE = {
  state: 'state',
  patslot: 'patslot',
  dialog: 'dialog',
  events: 'events',
  sync: 'sync',
}
function partsUse(head, load) {
  const lines = Object.entries(PARTS).flatMap(([part, names]) => {
    const whole = IN_WHOLE[part] ? `all.${IN_WHOLE[part]}` : 'all'
    return [
      `const ${part} = ${load(part)}`,
      `got.${part} = ${JSON.stringify(names)}.filter((name) => ` +
        `typeof ${whole}[name] !== 'function' || ${part}[name] !== ${whole}[name])`,
    ]
  })
  return [
    head,
    'const got = {}',
    ...lines,
    'process.stdout.write(JSON.stringify(got))',
    '',
  ].join('\n')
}
const PARTS_USES = {
  'parts.mjs': partsUse(
    "import * as all from 'mumulib/node'",
    (part) => `(await import('mumulib/${part}'))`,
  ),
  'parts.cjs': partsUse(
    "const all = require('mumulib/node')",
    (part) => `require('mumulib/${part}')`,
  ),
}

// The parts that keep no state of their own, and so load none: Mumu alone
// does not bring the page's state module, which listens as the page loads
const STATELESS = ['mumu', 'patslot']

// Every file of the package a module loads, following its relative imports
// of the package's modules -- not an example in a comment, which the
// unminified Node build keeps
function loads(start, seen = new Set()) {
  if (seen.has(start)) return [...seen]
  seen.add(start)
  const text = fs.readFileSync(start, 'utf-8')
  for (const [, rel] of text.matchAll(
    /(?:from|import|require\()\s*["'](\.[^"']+\.c?m?js)["']/g,
  )) {
    loads(path.resolve(path.dirname(start), rel), seen)
  }
  return [...seen]
}

const root = path.dirname(import.meta.dirname)
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'mumulib-node-check-'))
let failed = false

// Each command the package names runnable as it is built, as a project that
// links mumulib's checkout -- file:, not the registry -- runs it: npm makes a
// published bin executable as it installs it, but not one in a linked dist
const { bin } = JSON.parse(fs.readFileSync('package.json', 'utf-8'))
for (const [name, file] of Object.entries(bin)) {
  try {
    fs.accessSync(file, fs.constants.X_OK)
    console.log(`${name}: executable`)
  } catch {
    failed = true
    console.log(`${name}: FAILED, ${file} is not executable`)
  }
}
try {
  const tarball = execFileSync(
    'npm',
    ['pack', '--silent', '--pack-destination', work],
    { cwd: root, encoding: 'utf-8' },
  ).trim()
  fs.writeFileSync(path.join(work, 'package.json'), '{"private":true}\n')
  execFileSync(
    'npm',
    [
      'install',
      '--silent',
      '--no-audit',
      '--no-fund',
      '--prefer-offline',
      `./${tarball}`,
    ],
    { cwd: work, stdio: 'inherit' },
  )
  for (const [file, source] of Object.entries(USES)) {
    fs.writeFileSync(path.join(work, file), source.replace('__BODY__', BODY))
    let got
    try {
      got = JSON.parse(
        execFileSync('node', [file], { cwd: work, encoding: 'utf-8' }),
      )
    } catch (e) {
      got = { error: String(e.stdout || e.message) }
    }
    const wrong = Object.entries(EXPECTED).filter(([k, v]) => got[k] !== v)
    if (got.error || wrong.length) {
      failed = true
      console.log(
        `${file}: FAILED`,
        got.error ?? '',
        wrong
          .map(
            ([k, v]) =>
              `${k}: expected ${JSON.stringify(v)}, got ${JSON.stringify(got[k])}`,
          )
          .join('; '),
      )
    } else {
      console.log(`${file}: patslot and state work in Node`)
    }
  }
  // The types, as a TypeScript project finds them through the exports: one
  // that resolves as Node does, and one that resolves as a bundler does --
  // Vite's. Each export names its declarations first, under types, for both
  fs.writeFileSync(
    path.join(work, 'typed.ts'),
    [
      '/// <reference types="mumulib/sfc-client" />',
      "import { App, state } from 'mumulib'",
      "import { mumuElement } from 'mumulib/mumu'",
      "import * as node from 'mumulib/node'",
      "import { sfcPlugin } from 'mumulib/vite-plugin-sfc'",
      'const app: typeof App = node.App',
      'export { app, state, mumuElement, sfcPlugin }',
      '',
    ].join('\n'),
  )
  const tsc = path.join(root, 'node_modules', '.bin', 'tsc')
  for (const [resolution, module] of [
    ['nodenext', 'nodenext'],
    ['bundler', 'esnext'],
  ]) {
    try {
      execFileSync(
        tsc,
        [
          ...['--noEmit', '--strict', '--skipLibCheck', '--target', 'es2022'],
          ...['--lib', 'es2022,dom', '--module', module],
          ...['--moduleResolution', resolution, 'typed.ts'],
        ],
        { cwd: work, encoding: 'utf-8' },
      )
      console.log(`types (${resolution}): found for each export`)
    } catch (e) {
      failed = true
      console.log(
        `types (${resolution}): FAILED`,
        String(e.stdout || e.message),
      )
    }
  }
  for (const [file, source] of Object.entries(BARE)) {
    fs.writeFileSync(path.join(work, file), source)
    let got
    try {
      got = execFileSync('node', [file], { cwd: work, encoding: 'utf-8' })
    } catch (e) {
      got = String(e.stdout || e.message)
    }
    const expected = JSON.stringify(BARE_EXPECTED[file])
    if (got !== expected) {
      failed = true
      console.log(`${file}: FAILED, expected ${expected}, got ${got}`)
    } else {
      console.log(
        `${file}: ${file.startsWith('bare') ? 'mumulib sets no globals' : 'mumulib/node keeps a DOM already there'}`,
      )
    }
  }
  for (const file of Object.keys(PARTS_USES)) {
    fs.writeFileSync(path.join(work, file), PARTS_USES[file])
    let got
    try {
      got = JSON.parse(
        execFileSync('node', [file], { cwd: work, encoding: 'utf-8' }),
      )
    } catch (e) {
      got = { error: String(e.stdout || e.message) }
    }
    const wrong = Object.entries(got).filter(
      ([, missing]) => !Array.isArray(missing) || missing.length,
    )
    if (wrong.length) {
      failed = true
      console.log(`${file}: FAILED`, JSON.stringify(Object.fromEntries(wrong)))
    } else {
      console.log(`${file}: each part imports alone, and is the whole's own`)
    }
  }
  const installed = path.join(work, 'node_modules', 'mumulib')
  const { exports } = JSON.parse(
    fs.readFileSync(path.join(installed, 'package.json'), 'utf-8'),
  )
  for (const part of STATELESS) {
    for (const condition of ['browser', 'node']) {
      const loaded = loads(
        path.join(installed, exports[`./${part}`][condition]),
      )
      const stateful = loaded.filter((file) =>
        fs.readFileSync(file, 'utf-8').includes('DOMContentLoaded'),
      )
      if (stateful.length) {
        failed = true
        console.log(
          `mumulib/${part} (${condition}): FAILED, it loads state: ` +
            stateful.map((file) => path.basename(file)).join(', '),
        )
      } else {
        console.log(`mumulib/${part} (${condition}): brings no state`)
      }
    }
  }
} finally {
  fs.rmSync(work, { recursive: true, force: true })
}
process.exitCode = failed ? 1 : 0
