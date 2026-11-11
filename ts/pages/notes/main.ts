// The notes page: an App, whose template is the page's body, and a
// component for each note, note-row.sfc.html. Served by mumulib's Python
// server -- py/examples/notes.py -- as Vite made it.
//
// Two things are bound into the app's state with sync.bind, and fetched
// again whenever a write to them, anyone's, is announced: the notes, a
// Persist at /notes, each by its id, with its text and its order; and who is
// here, the Presence at /presence. The app never changes either itself. A
// write is a request, and its own change comes back as anyone's does.
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
// A note can be focused, dragged -- by mouse, finger, pen or Voice Control
// alike: pointer events are all of them -- or driven from the keyboard: ↑ ↓
// move the focus, ⌥↑ ⌥↓ move the note, Enter edits it and commits, Escape
// cancels, Delete removes it. Each player is shown by a thin outline in its
// colour on the note it is at, and named in the key.
//
// A note someone else changes while it is being edited here is a conflict
// -- worked out, not kept: the text it had as editing began is not the
// server's now -- and its field is locked, shaken and buzzed, and Mine or
// Theirs says which text it keeps.
import { App, mountApp, mumuElement, sync } from 'mumulib'
import NoteRow from './note-row.sfc.html'
import { placed, sorted } from './order'
import { heraldic, randomId } from './names'
import './style.css'

// The page's component first: the app sets its properties as it draws
customElements.define('note-row', mumuElement(NoteRow))

type Note = { text: string; order: string }
type Player = {
  name: string
  color: string
  focus: string | null
  seen: number
}
// The note being edited: which, and its text and place as editing began
type Editing = { note: string; baseline: string; order: string }

type State = {
  notes: Record<string, Note>
  presence: Record<string, Player>
  draft: string
  editing: Editing | null
}

type NoteElement = HTMLElement & { note: string }

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
  document.documentElement.style.setProperty('--me', made.color)
  return made
}

let me = remembered()
document.documentElement.style.setProperty('--me', me.color)

const playerUrl = () => `/presence/${me.id}.json`
const authorization = () => ({ authorization: `Bearer ${me.key}` })

/** The note focused here: its row has the focus, or something in it. */
function focused(): string | null {
  const active = document.activeElement
  return active?.tagName === 'NOTE-ROW' ? (active as NoteElement).note : null
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
    // The id is another page's: this one becomes someone new
    if ((await put()).status === 403) {
      me = newPlayer()
      await put()
    }
  })
}

setInterval(heartbeat, 30_000)
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
async function move(
  notes: Record<string, Note>,
  id: string,
  index: number
): Promise<void> {
  const ids = sorted(notes)
  const others = ids.filter((other) => other !== id)
  if (ids.indexOf(id) === index || !(id in notes)) return
  const low = index > 0 ? notes[others[index - 1]!]!.order : null
  const high = index < others.length ? notes[others[index]!]!.order : null
  // Two notes dropped into one gap at once share an order, and are sorted
  // by id: nothing is between them, so it goes after both
  const order =
    low !== null && high !== null && !(low < high)
      ? placed(low, null)
      : placed(low, high)
  await put(`/notes/${id}/order.json`, order)
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

// --- Dragging ---------------------------------------------------------------

// The one part done to the page directly: where a note being dragged is,
// as the pointer moves, is the browser's to draw, not the state's
type Drag = {
  row: NoteElement
  x: number
  y: number
  moved: boolean
  // Where it would land: an index among the others, or the trash
  to: number | 'trash' | null
}

function inside(element: Element, event: PointerEvent): boolean {
  const box = element.getBoundingClientRect()
  return (
    event.clientX >= box.left &&
    event.clientX <= box.right &&
    event.clientY >= box.top &&
    event.clientY <= box.bottom
  )
}

/** The note an event happened in, and the element it began at inside it. */
function rowOf(event: Event): { row: NoteElement; inner: unknown } | null {
  const path = event.composedPath()
  const row = path.find(
    (el) => el instanceof HTMLElement && el.tagName === 'NOTE-ROW'
  )
  return row ? { row: row as NoteElement, inner: path[0] } : null
}

// --- The app ----------------------------------------------------------------

class Notes extends App<State> {
  static state: State = { notes: {}, presence: {}, draft: '', editing: null }

  #drag: Drag | null = null
  // The trash, pressed rather than dropped on: the note focused as it was
  #lastNote: string | null = null
  // Conflicts already buzzed for: once each
  #buzzed = new Set<string>()

  /** The notes in order -- and the one edited, while it is decided, even
   * removed -- each with how it stands and who is at it. */
  get rows() {
    const { notes, editing, presence } = this.state
    const ids = sorted(notes)
    if (editing && !(editing.note in notes)) {
      const at = ids.findIndex((id) => notes[id]!.order > editing.order)
      ids.splice(at === -1 ? ids.length : at, 0, editing.note)
    }
    // Who is at each note, but this player: its own focus shows itself
    const at = new Map<string, string[]>()
    for (const [id, player] of Object.entries(presence)) {
      if (id === me.id || player.focus === null) continue
      at.set(player.focus, [...(at.get(player.focus) ?? []), player.color])
    }
    return ids.map((id) => {
      const mine = editing?.note === id
      const now = notes[id]?.text ?? null
      const colors = at.get(id) ?? []
      return {
        key: id,
        text: now ?? editing!.baseline,
        editing: mine,
        clashed: mine && now !== editing!.baseline,
        outline: colors.length
          ? `box-shadow: ${colors.map((c, n) => `0 0 0 ${2 * (n + 1)}px ${c}`).join(', ')}`
          : '',
        here: colors.length ? `${colors.length} here` : '',
      }
    })
  }

  /** Who is here, by name, this player marked. */
  get players() {
    return Object.entries(this.state.presence)
      .sort(([, a], [, b]) => a.name.localeCompare(b.name))
      .map(([id, player]) => ({
        key: id,
        name: id === me.id ? `${player.name} (you)` : player.name,
        whose: id === me.id ? 'you' : '',
        swatch: `--color: ${player.color}`,
      }))
  }

  onRender(): void {
    // A conflict newly come about is buzzed for, once
    const clashed = new Set(
      this.rows.filter((r) => r.clashed).map((r) => r.key)
    )
    for (const id of clashed) if (!this.#buzzed.has(id)) buzz()
    this.#buzzed = clashed
  }

  // --- What the page asks for, by data-on

  add(event: SubmitEvent): void {
    event.preventDefault()
    const text = this.state.draft.trim()
    if (!text) return
    const last = sorted(this.state.notes).at(-1)
    const order = placed(
      last === undefined ? null : this.state.notes[last]!.order,
      null
    )
    this.update({ draft: '' })
    void put(`/notes/${randomId()}.json`, { text, order })
  }

  save(event: CustomEvent<{ note: string; text: string }>): void {
    const editing = this.state.editing
    if (editing?.note !== event.detail.note) return
    this.update({ editing: null })
    const text = event.detail.text.trim()
    if (text && text !== editing.baseline)
      void put(`/notes/${editing.note}/text.json`, text)
  }

  cancel(): void {
    this.update({ editing: null })
  }

  resolve(
    event: CustomEvent<{ note: string; keep: 'mine' | 'theirs'; text: string }>
  ): void {
    const editing = this.state.editing
    if (editing?.note !== event.detail.note) return
    this.update({ editing: null })
    if (event.detail.keep === 'theirs') return
    const text = event.detail.text.trim() || editing.baseline
    // Theirs removed it: mine puts it back, where it was
    if (editing.note in this.state.notes)
      void put(`/notes/${editing.note}/text.json`, text)
    else void put(`/notes/${editing.note}.json`, { text, order: editing.order })
  }

  trashFocused(): void {
    if (this.#lastNote !== null) void remove(this.#lastNote)
    this.#lastNote = null
  }

  // --- The keyboard: on a note's row, not in its field

  onKeyDown(event: KeyboardEvent): void {
    const at = rowOf(event)
    if (
      !at ||
      !(at.inner instanceof HTMLElement) ||
      !at.inner.classList.contains('note')
    ) {
      return
    }
    const id = at.row.note
    const ids = sorted(this.state.notes)
    const index = ids.indexOf(id)
    const step =
      event.key === 'ArrowUp' ? -1 : event.key === 'ArrowDown' ? 1 : 0
    if (step && event.altKey) {
      event.preventDefault()
      if (index + step >= 0 && index + step < ids.length) {
        void move(this.state.notes, id, index + step)
      }
    } else if (step) {
      event.preventDefault()
      this.#row(ids[index + step])?.focus()
    } else if (event.key === 'Enter') {
      event.preventDefault()
      this.#edit(id)
    } else if (event.key === 'Delete' || event.key === 'Backspace') {
      event.preventDefault()
      this.#row(ids[index + 1] ?? ids[index - 1])?.focus()
      void remove(id)
    }
  }

  onDblClick(event: MouseEvent): void {
    const at = rowOf(event)
    if (at && !this.state.editing) this.#edit(at.row.note)
  }

  // --- Where this player is, for everyone

  onFocusIn(): void {
    heartbeat()
  }

  onFocusOut(event: FocusEvent): void {
    // Tabbed from a note to the trash: that note is the trash's
    if (event.relatedTarget === this.refs.trash) this.#lastNote = focused()
    setTimeout(heartbeat)
  }

  // --- Dragging

  onPointerDown(event: PointerEvent): void {
    if (event.target === this.refs.trash) {
      // Pointed at, before a press moves the focus from the note
      this.#lastNote = focused()
      return
    }
    const at = rowOf(event)
    if (event.button !== 0 || this.state.editing || !at) return
    // A drag, or a tap: not a text selection, nor a scroll on a touch screen
    event.preventDefault()
    this.#drag = {
      row: at.row,
      x: event.clientX,
      y: event.clientY,
      moved: false,
      to: null,
    }
  }

  onPointerMove(event: PointerEvent): void {
    const drag = this.#drag
    if (!drag) return
    const dx = event.clientX - drag.x
    const dy = event.clientY - drag.y
    if (!drag.moved && Math.hypot(dx, dy) < 4) return
    drag.moved = true
    drag.row.classList.add('dragging')
    drag.row.style.transform = `translate(${dx}px, ${dy}px)`
    const trash = this.refs.trash!
    const others = this.#rows().filter((row) => row !== drag.row)
    for (const other of others)
      other.classList.remove('drop-before', 'drop-after')
    if (inside(trash, event)) {
      drag.to = 'trash'
      trash.classList.add('over')
      return
    }
    trash.classList.remove('over')
    // Among the others, the place the pointer is above the middle of
    const index = others.findIndex((other) => {
      const box = other.getBoundingClientRect()
      return event.clientY < box.top + box.height / 2
    })
    drag.to = index === -1 ? others.length : index
    if (index === -1) others.at(-1)?.classList.add('drop-after')
    else others[index]!.classList.add('drop-before')
  }

  onPointerUp(): void {
    const ended = this.#endDrag()
    if (!ended) return
    // Not moved: a tap or a click, which focuses the note
    if (!ended.moved) ended.row.focus()
    else if (ended.to === 'trash') void remove(ended.row.note)
    else if (ended.to !== null)
      void move(this.state.notes, ended.row.note, ended.to)
  }

  onPointerCancel(): void {
    this.#endDrag()
  }

  #endDrag(): Drag | null {
    const ended = this.#drag
    this.#drag = null
    if (!ended) return null
    ended.row.classList.remove('dragging')
    ended.row.style.transform = ''
    this.refs.trash!.classList.remove('over')
    for (const row of this.#rows())
      row.classList.remove('drop-before', 'drop-after')
    return ended
  }

  // --- The page's own elements

  #rows(): NoteElement[] {
    return [...this.refs.list!.querySelectorAll<NoteElement>('note-row')]
  }

  #row(id: string | undefined): NoteElement | undefined {
    return this.#rows().find((row) => row.note === id)
  }

  #edit(id: string): void {
    const note = this.state.notes[id]
    if (!note || this.state.editing) return
    this.update({
      editing: { note: id, baseline: note.text, order: note.order },
    })
  }
}

mountApp(Notes)
await sync.bind('notes', '/notes')
await sync.bind('presence', '/presence')
document.body.dataset.loaded = 'true'
heartbeat()
