// The notes page: a Vite page, served by mumulib's Python server as Vite
// made it -- py/examples/notes.py. Past the HTML it is all TypeScript.
//
// Two things are bound into the state with sync.bind, and fetched again
// whenever a write to them, anyone's, is announced: the notes, a Persist at
// /notes, each by its id, with its text and its order; and who is here, the
// Presence at /presence. The page never changes either itself. A write is a
// request, and its own change comes back as anyone's does.
//
//   PUT    /notes/<id>.json         a note added
//   PUT    /notes/<id>/text.json    its text edited
//   PUT    /notes/<id>/order.json   moved: its order, between its new
//                                   neighbours', and no other note touched
//   DELETE /notes/<id>.json         removed: dragged to the trash
//   PUT    /presence/<me>.json      here, and where: as the focus moves, and
//                                   every thirty seconds, with this tab's key
//   DELETE /presence/<me>.json      gone, as the tab closes
//
// A note is a row that can be focused, dragged -- by mouse, finger, pen or
// Voice Control alike: pointer events are all of them -- or driven from the
// keyboard: ↑ ↓ move the focus, ⌥↑ ⌥↓ move the note, Enter edits it and
// commits, Escape cancels, Delete removes it. Each player is shown by a
// thin outline in its colour on the row it is at, and named in the key.
//
// A note changed by someone else while it is being edited here is a
// conflict: the field is locked, shaken and buzzed, and Mine or Theirs
// says which text it keeps.
import { state, sync } from 'mumulib'
import { placed, sorted } from './order'
import { heraldic, randomId } from './names'
import './style.css'

type Note = { text: string; order: string }
type Player = {
  name: string
  color: string
  focus: string | null
  seen: number
}
type Notes = Record<string, Note>
type Players = Record<string, Player>

const list = document.querySelector<HTMLUListElement>('#notes')!
const form = document.querySelector<HTMLFormElement>('#add')!
const trash = document.querySelector<HTMLButtonElement>('#trash')!
const key = document.querySelector<HTMLUListElement>('#players')!

// What the server last said
let notes: Notes = {}
let players: Players = {}

const json = { 'content-type': 'application/json' }

// --- Who this tab is ------------------------------------------------------

// Kept for the tab's life, so that reloading it is the same player
type Me = { id: string; key: string; name: string; color: string }

function remembered(): Me {
  try {
    const kept = sessionStorage.getItem('notes-player')
    if (kept) return JSON.parse(kept) as Me
  } catch {
    // No storage: a new player each load
  }
  return newPlayer()
}

function newPlayer(): Me {
  const made = { id: randomId(), key: randomId(24), ...heraldic() }
  try {
    sessionStorage.setItem('notes-player', JSON.stringify(made))
  } catch {
    // Kept in memory alone, then
  }
  return made
}

let me = remembered()
document.body.style.setProperty('--me', me.color)

function playerUrl(): string {
  return `/presence/${me.id}.json`
}

function authorization(): Record<string, string> {
  return { authorization: `Bearer ${me.key}` }
}

// The note focused here, said to everyone
function focused(): string | null {
  const row = document.activeElement?.closest<HTMLLIElement>('li.note')
  return row?.dataset.id ?? null
}

let heartbeatQueued = false
// Closing: no heartbeat now -- the blur as a page closes would queue one,
// and it could land after the page's goodbye, putting the player back
let leaving = false

/** Say where this player is: once, however often asked in one task. */
function heartbeat(): void {
  if (heartbeatQueued || leaving) return
  heartbeatQueued = true
  queueMicrotask(async () => {
    heartbeatQueued = false
    if (leaving) return
    const body = JSON.stringify({
      name: me.name,
      color: me.color,
      focus: focused(),
    })
    const put = () =>
      fetch(playerUrl(), {
        method: 'PUT',
        headers: { ...json, ...authorization() },
        body,
      })
    let response = await put()
    // The id is another page's: this one becomes someone new
    if (response.status === 403) {
      me = newPlayer()
      document.body.style.setProperty('--me', me.color)
      response = await put()
    }
  })
}

setInterval(heartbeat, 30_000)
list.addEventListener('focusin', heartbeat)
list.addEventListener('focusout', () => setTimeout(heartbeat))
// Gone as the tab closes: a request that outlives the page
addEventListener('pagehide', () => {
  leaving = true
  void fetch(playerUrl(), {
    method: 'DELETE',
    headers: authorization(),
    keepalive: true,
  })
})
// And back, if the browser kept the page and shows it again
addEventListener('pageshow', (event) => {
  leaving = false
  if (event.persisted) heartbeat()
})

// --- Writes -----------------------------------------------------------------

async function put(url: string, value: unknown): Promise<void> {
  await fetch(url, {
    method: 'PUT',
    headers: json,
    body: JSON.stringify(value),
  })
}

async function remove(id: string): Promise<void> {
  await fetch(`/notes/${id}.json`, { method: 'DELETE' })
}

/** Move a note to the index'th place among the others. */
async function move(id: string, index: number): Promise<void> {
  const others = sorted(notes).filter((other) => other !== id)
  const before = others[index - 1]
  const after = others[index]
  const now = sorted(notes).indexOf(id)
  // Where it already is
  if (now === index || !(id in notes)) return
  const low = before === undefined ? null : notes[before]!.order
  const high = after === undefined ? null : notes[after]!.order
  // Two notes dropped into one gap at once share an order, and are sorted
  // by id: nothing is between them, so it goes after both
  const order =
    low !== null && high !== null && !(low < high)
      ? placed(low, null)
      : placed(low, high)
  await put(`/notes/${id}/order.json`, order)
}

form.addEventListener('submit', async (event) => {
  event.preventDefault()
  const text = String(new FormData(form).get('text') ?? '').trim()
  if (!text) return
  const last = sorted(notes).at(-1)
  const order = placed(last === undefined ? null : notes[last]!.order, null)
  form.reset()
  await put(`/notes/${randomId()}.json`, { text, order })
})

// --- Editing, and conflicts -----------------------------------------------

type Editing = {
  id: string
  input: HTMLInputElement
  // The text as it was when editing began: what a change by someone else
  // is told from
  baseline: string
  // Someone else's text, or null for the note removed, once they clash
  theirs?: string | null
}

let editing: Editing | null = null
// While the list is rearranged, a field that loses its focus has not been
// left by the reader
let rearranging = false

function edit(row: HTMLLIElement): void {
  const id = row.dataset.id!
  if (editing || !(id in notes)) return
  const text = notes[id]!.text
  const input = document.createElement('input')
  input.className = 'edit'
  input.value = text
  input.setAttribute('aria-label', 'Note text')
  row.querySelector('.text')!.replaceWith(input)
  editing = { id, input, baseline: text }
  input.focus()
  input.select()
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      void commit()
    } else if (event.key === 'Escape') {
      event.preventDefault()
      finish()
    }
  })
  input.addEventListener('blur', () => {
    if (
      !rearranging &&
      editing?.input === input &&
      editing.theirs === undefined
    ) {
      void commit()
    }
  })
}

/** Done editing: the row shows the note's text again, and keeps the focus. */
function finish(): void {
  if (!editing) return
  const { id, input } = editing
  editing = null
  const row = rows.get(id)
  const span = textSpan()
  input.replaceWith(span)
  row?.querySelector('.resolve')?.remove()
  row?.classList.remove('locked')
  render()
  rows.get(id)?.focus()
}

async function commit(): Promise<void> {
  if (!editing || editing.theirs !== undefined) return
  const { id, input, baseline } = editing
  const text = input.value.trim()
  finish()
  if (text && text !== baseline) await put(`/notes/${id}/text.json`, text)
}

/** Someone else changed what is being edited: lock it, and ask. */
function clash(theirs: string | null): void {
  if (!editing) return
  const first = editing.theirs === undefined
  editing.theirs = theirs
  if (!first) return
  const { id, input } = editing
  const row = rows.get(id)!
  input.readOnly = true
  row.classList.add('locked')
  shake(input)
  buzz()
  const resolve = document.createElement('span')
  resolve.className = 'resolve'
  resolve.setAttribute('role', 'group')
  resolve.setAttribute('aria-label', 'Changed by someone else: keep which?')
  const mine = button('Mine', async () => {
    const { input: field, theirs: gone } = editing!
    const text = field.value.trim() || editing!.baseline
    const order = notes[id]?.order ?? row.dataset.order!
    finish()
    // Theirs removed it: mine puts it back, where it was
    if (gone === null) await put(`/notes/${id}.json`, { text, order })
    else await put(`/notes/${id}/text.json`, text)
  })
  const keep = button('Theirs', () => finish())
  resolve.append(mine, keep)
  row.append(resolve)
  mine.focus()
}

function button(label: string, onclick: () => unknown): HTMLButtonElement {
  const made = document.createElement('button')
  made.type = 'button'
  made.textContent = label
  made.addEventListener('click', () => void onclick())
  return made
}

function shake(element: HTMLElement): void {
  element.classList.remove('shake')
  // Read, so the animation starts again
  void element.offsetWidth
  element.classList.add('shake')
}

let audio: AudioContext | undefined

/** A short low buzz: something needs a decision. */
function buzz(): void {
  try {
    audio ??= new AudioContext()
    const now = audio.currentTime
    const tone = audio.createOscillator()
    const volume = audio.createGain()
    tone.type = 'sawtooth'
    tone.frequency.value = 90
    volume.gain.setValueAtTime(0.0001, now)
    volume.gain.exponentialRampToValueAtTime(0.25, now + 0.02)
    volume.gain.exponentialRampToValueAtTime(0.0001, now + 0.35)
    tone.connect(volume).connect(audio.destination)
    tone.start(now)
    tone.stop(now + 0.4)
  } catch {
    // No sound: the shake says it
  }
}

// --- The rows -----------------------------------------------------------------

// Each note's row, by its id, kept from one drawing to the next: a row
// focused or being edited stays the same element
const rows = new Map<string, HTMLLIElement>()

function textSpan(): HTMLSpanElement {
  const span = document.createElement('span')
  span.className = 'text'
  return span
}

function row(id: string): HTMLLIElement {
  let made = rows.get(id)
  if (made) return made
  made = document.createElement('li')
  made.className = 'note'
  made.tabIndex = 0
  made.dataset.id = id
  made.append(textSpan())
  rows.set(id, made)
  return made
}

/** Draw the notes and who is where, as the server last said. */
function render(): void {
  const ids = sorted(notes)
  // The note being edited stays while it is decided, even removed
  if (editing && !(editing.id in notes)) {
    const at = ids.findIndex(
      (id) => notes[id]!.order > rows.get(editing!.id)!.dataset.order!
    )
    ids.splice(at === -1 ? ids.length : at, 0, editing.id)
  }
  // Who is at each note, but this player: its own focus shows itself
  const at = new Map<string, string[]>()
  for (const [id, player] of Object.entries(players)) {
    if (id === me.id || player.focus === null) continue
    at.set(player.focus, [...(at.get(player.focus) ?? []), player.color])
  }
  const active = document.activeElement
  const selection =
    active instanceof HTMLInputElement
      ? [active.selectionStart, active.selectionEnd]
      : null
  rearranging = true
  ids.forEach((id, index) => {
    const li = row(id)
    const note = notes[id]
    if (note) {
      li.dataset.order = note.order
      if (editing?.id !== id) li.querySelector('.text')!.textContent = note.text
    }
    const colors = at.get(id) ?? []
    li.style.boxShadow = colors
      .map((color, n) => `0 0 0 ${2 * (n + 1)}px ${color}`)
      .join(', ')
    li.title = colors.length ? `${colors.length} here` : ''
    if (list.children[index] !== li)
      list.insertBefore(li, list.children[index] ?? null)
  })
  for (const [id, li] of rows) {
    if (!ids.includes(id)) {
      li.remove()
      rows.delete(id)
    }
  }
  // Moving a focused row takes its focus: given back, where it was -- now,
  // and again once the browser has settled where it thinks the focus is,
  // which Chrome may do a moment after the move
  const giveBack = () => {
    if (
      active instanceof HTMLElement &&
      active.isConnected &&
      active !== document.activeElement &&
      (document.activeElement === document.body ||
        document.activeElement === null)
    ) {
      active.focus()
      if (selection && active instanceof HTMLInputElement) {
        active.setSelectionRange(selection[0], selection[1])
      }
    }
  }
  giveBack()
  setTimeout(giveBack)
  rearranging = false
  renderKey()
}

function renderKey(): void {
  const here = Object.entries(players).sort(([, a], [, b]) =>
    a.name.localeCompare(b.name)
  )
  key.replaceChildren(
    ...here.map(([id, player]) => {
      const li = document.createElement('li')
      li.style.setProperty('--color', player.color)
      li.textContent = player.name
      if (id === me.id) {
        li.className = 'you'
        li.append(' (you)')
      }
      return li
    })
  )
}

// --- The keyboard ---------------------------------------------------------

list.addEventListener('keydown', (event) => {
  const li = (event.target as Element).closest<HTMLLIElement>('li.note')
  if (!li || event.target !== li) return
  const ids = sorted(notes)
  const index = ids.indexOf(li.dataset.id!)
  const step = event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0
  if (step && event.altKey) {
    event.preventDefault()
    if (index + step >= 0 && index + step < ids.length)
      void move(li.dataset.id!, index + step)
  } else if (step) {
    event.preventDefault()
    rows.get(ids[index + step] ?? '')?.focus()
  } else if (event.key === 'Enter') {
    event.preventDefault()
    edit(li)
  } else if (event.key === 'Delete' || event.key === 'Backspace') {
    event.preventDefault()
    rows.get(ids[index + 1] ?? ids[index - 1] ?? '')?.focus()
    void remove(li.dataset.id!)
  }
})

list.addEventListener('dblclick', (event) => {
  const li = (event.target as Element).closest<HTMLLIElement>('li.note')
  if (li && !li.contains(editing?.input ?? null)) edit(li)
})

// The trash, pressed rather than dropped on: the note focused as it was --
// pointed at, before a press moves the focus, or tabbed to from the note
let lastNote: string | null = null
trash.addEventListener('pointerdown', () => (lastNote = focused()))
list.addEventListener('focusout', (event) => {
  if (event.relatedTarget === trash) lastNote = focused()
})
trash.addEventListener('click', () => {
  if (lastNote !== null) void remove(lastNote)
  lastNote = null
})

// --- Dragging -----------------------------------------------------------------

type Drag = {
  li: HTMLLIElement
  id: string
  x: number
  y: number
  moved: boolean
  // Where it would land: an index among the others, or the trash
  to: number | 'trash' | null
}

let drag: Drag | null = null

function inside(element: Element, event: PointerEvent): boolean {
  const box = element.getBoundingClientRect()
  return (
    event.clientX >= box.left &&
    event.clientX <= box.right &&
    event.clientY >= box.top &&
    event.clientY <= box.bottom
  )
}

list.addEventListener('pointerdown', (event) => {
  if (event.button !== 0 || editing) return
  const li = (event.target as Element).closest<HTMLLIElement>('li.note')
  if (!li) return
  // Not a text selection, nor a scroll on a touch screen: a drag, or a tap
  event.preventDefault()
  drag = {
    li,
    id: li.dataset.id!,
    x: event.clientX,
    y: event.clientY,
    moved: false,
    to: null,
  }
})

// Followed from the document, not the list or the row: other players'
// changes can move the row being dragged, and an element moved loses the
// pointer's capture, and with it the rest of the drag
document.addEventListener('pointermove', (event) => {
  if (!drag) return
  const dx = event.clientX - drag.x
  const dy = event.clientY - drag.y
  if (!drag.moved && Math.hypot(dx, dy) < 4) return
  drag.moved = true
  drag.li.classList.add('dragging')
  drag.li.style.transform = `translate(${dx}px, ${dy}px)`
  for (const other of rows.values())
    other.classList.remove('drop-before', 'drop-after')
  if (inside(trash, event)) {
    drag.to = 'trash'
    trash.classList.add('over')
    return
  }
  trash.classList.remove('over')
  // Among the others, the place the pointer is above the middle of
  const others = sorted(notes)
    .filter((id) => id !== drag!.id)
    .map((id) => rows.get(id)!)
  const index = others.findIndex((other) => {
    const box = other.getBoundingClientRect()
    return event.clientY < box.top + box.height / 2
  })
  drag.to = index === -1 ? others.length : index
  if (index === -1) others.at(-1)?.classList.add('drop-after')
  else others[index]!.classList.add('drop-before')
})

function endDrag(): Drag | null {
  const ended = drag
  drag = null
  if (!ended) return null
  ended.li.classList.remove('dragging')
  ended.li.style.transform = ''
  trash.classList.remove('over')
  for (const other of rows.values())
    other.classList.remove('drop-before', 'drop-after')
  return ended
}

document.addEventListener('pointerup', () => {
  const ended = endDrag()
  if (!ended) return
  // Not moved: a tap or a click, which focuses the note
  if (!ended.moved) ended.li.focus()
  else if (ended.to === 'trash') void remove(ended.id)
  else if (ended.to !== null) void move(ended.id, ended.to)
})
document.addEventListener('pointercancel', endDrag)

// --- Bound ----------------------------------------------------------------

await state.onstate(async (current) => {
  if (current.notes !== undefined) notes = current.notes as Notes
  if (current.presence !== undefined) players = current.presence as Players
  if (editing) {
    const now = notes[editing.id]
    // Someone else's change of what is being edited: its text, or it gone
    const theirs = now === undefined ? null : now.text
    if (theirs !== editing.baseline) clash(theirs)
  }
  render()
  if (current.notes !== undefined) document.body.dataset.loaded = 'true'
})

await sync.bind('notes', '/notes')
await sync.bind('presence', '/presence')
heartbeat()
