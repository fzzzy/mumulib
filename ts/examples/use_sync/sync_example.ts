// sync.bind: a path in the state bound to a URL, shown as it changes. The
// server here is the test's own -- src/sync.spec.ts answers /docs/a.json and
// /mumulib/changes.sse -- as mumulib's Python server would.
import { state, sync } from 'mumulib'

const shown = document.querySelector<HTMLPreElement>('#doc')!
const errors = document.querySelector<HTMLParagraphElement>('#errors')!

await state.onstate(async (current) => {
  if (current.doc !== undefined) shown.textContent = JSON.stringify(current.doc)
})

// What bind refuses, said on the page for the test to read
const refused = async (bound: Promise<void>) => {
  try {
    await bound
  } catch (error) {
    errors.textContent += `${(error as Error).message}; `
  }
}

await refused(sync.bind('', '/docs/a'))
await refused(sync.bind('index', '/docs/'))
await refused(sync.bind('missing', '/docs/missing'))
await sync.bind('doc', '/docs/a.json')
document.body.dataset.bound = 'true'
