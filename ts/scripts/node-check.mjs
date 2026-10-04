// mumulib as a Node user gets it: the package packed as it would be
// published, installed into an empty project, and used through require and
// import, where domino is the only DOM. Nothing else runs the library
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

const root = path.dirname(import.meta.dirname)
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'mumulib-node-check-'))
let failed = false
try {
  const tarball = execFileSync(
    'npm',
    ['pack', '--silent', '--pack-destination', work],
    { cwd: root, encoding: 'utf-8' }
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
    { cwd: work, stdio: 'inherit' }
  )
  for (const [file, source] of Object.entries(USES)) {
    fs.writeFileSync(path.join(work, file), source.replace('__BODY__', BODY))
    let got
    try {
      got = JSON.parse(
        execFileSync('node', [file], { cwd: work, encoding: 'utf-8' })
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
              `${k}: expected ${JSON.stringify(v)}, got ${JSON.stringify(got[k])}`
          )
          .join('; ')
      )
    } else {
      console.log(`${file}: patslot and state work in Node`)
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
        `${file}: ${file.startsWith('bare') ? 'mumulib sets no globals' : 'mumulib/node keeps a DOM already there'}`
      )
    }
  }
} finally {
  fs.rmSync(work, { recursive: true, force: true })
}
process.exitCode = failed ? 1 : 0
