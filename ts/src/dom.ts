/**
 * A DOM for Node, from domino: what mumulib/node imports before the library,
 * which reads document as it loads. It sets document, and the element
 * classes the library checks with instanceof, on globalThis -- each only if
 * it is missing, so a DOM already there, jsdom in someone's tests, is left
 * alone. mumulib itself sets nothing: only importing mumulib/node does.
 */

import domino from 'domino'

// What the library uses: document, and the classes its instanceof checks name
const CLASSES = [
  'Node',
  'Element',
  'HTMLElement',
  'HTMLInputElement',
  'HTMLSelectElement',
  'HTMLTextAreaElement',
  'HTMLFormElement',
  'HTMLDialogElement',
] as const

if (typeof document === 'undefined') {
  const window = domino.createWindow('')
  const global = globalThis as Record<string, unknown>
  global.document = window.document
  for (const name of CLASSES) {
    global[name] ??= window[name]
  }
}

// A module, though it exports nothing: without this the bundler takes it for
// CommonJS, and runs it lazily -- after the library it must come before
export {}
