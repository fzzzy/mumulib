// The notes page: a Vite page, served by mumulib's Python server as Vite
// made it -- py/examples/notes.py. Past the HTML it is all TypeScript. The
// notes, a Persist at /notes, are bound into the state with sync.bind:
// fetched, and fetched again whenever a write to them -- this page's or
// anyone's -- is announced. Writes are requests: PUT /notes/last.json adds
// one, DELETE /notes/<index>.json removes one.
import { state, sync } from 'mumulib'
import './style.css'

// A removed note leaves null in its place, so no other note's URL changes
type Note = string | null

const list = document.querySelector<HTMLUListElement>('#notes')!
const form = document.querySelector<HTMLFormElement>('#add')!

function item(text: string, index: number): HTMLLIElement {
  const li = document.createElement('li')
  li.textContent = text
  const remove = document.createElement('button')
  remove.textContent = 'Remove'
  remove.addEventListener('click', async () => {
    await fetch(`/notes/${index}.json`, { method: 'DELETE' })
  })
  li.append(' ', remove)
  return li
}

await state.onstate(async (current) => {
  const notes = (current.notes ?? []) as Note[]
  list.replaceChildren(
    ...notes.flatMap((text, index) =>
      text === null ? [] : [item(text, index)]
    )
  )
  if (current.notes !== undefined) document.body.dataset.loaded = 'true'
})

form.addEventListener('submit', async (event) => {
  event.preventDefault()
  const text = new FormData(form).get('text')
  await fetch('/notes/last.json', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(text),
  })
  form.reset()
})

await sync.bind('notes', '/notes')
