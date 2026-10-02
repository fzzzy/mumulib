// The notes page: a Vite page, served by mumulib's Python server as Vite
// made it -- py/examples/notes.py. Past the HTML it is all TypeScript,
// talking to the published tree: GET /notes.json, a Persist's file; PUT
// /notes/last.json adds one; DELETE /notes/<index>.json removes one.
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
    await load()
  })
  li.append(' ', remove)
  return li
}

async function load(): Promise<void> {
  const response = await fetch('/notes.json')
  const notes = (await response.json()) as Note[]
  list.replaceChildren(
    ...notes.flatMap((text, index) =>
      text === null ? [] : [item(text, index)]
    )
  )
  document.body.dataset.loaded = 'true'
}

form.addEventListener('submit', async (event) => {
  event.preventDefault()
  const text = new FormData(form).get('text')
  await fetch('/notes/last.json', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(text),
  })
  form.reset()
  await load()
})

await load()
