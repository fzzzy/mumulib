/**
 * An app: the page's body is its template, and Todo draws it from its state.
 * Its inputs are bound to the state, through the field component too; what
 * the page asks for -- adding, removing, a component's toggle -- comes to
 * Todo's methods by data-on; and the edit dialog's form calls save().
 */
import { App, mountApp, mumuElement } from 'mumulib'
import type { FormArgs } from 'mumulib'
import Opener from '../use_mumu/opener.sfc.html'
import Field from './field.sfc.html'

// The page's components first: the app sets their properties as it draws.
customElements.define('my-opener', mumuElement(Opener))
customElements.define('my-field', mumuElement(Field))

interface Item {
  key: string
  text: string
  done: boolean
}

class Todo extends App<{
  title: string
  draft: string
  items: Item[]
  next: number
  open: boolean
  editing: string | null
}> {
  static state = {
    title: 'Things to do',
    draft: '',
    items: [] as Item[],
    next: 1,
    open: false,
    editing: null as string | null,
  }

  get titleLabel(): string {
    return 'Title'
  }
  get count(): string {
    const { items } = this.state
    const done = items.filter((item) => item.done).length
    return `${items.length === 1 ? '1 thing' : `${items.length} things`}, ${done} done`
  }
  get empty(): boolean {
    return !this.state.draft.trim()
  }
  get editor(): { key: string; text: string }[] {
    const item = this.state.items.find((i) => i.key === this.state.editing)
    return item ? [{ key: item.key, text: item.text }] : []
  }

  add(): void {
    const { draft, items, next } = this.state
    if (!draft.trim()) return
    this.update({
      items: [...items, { key: String(next), text: draft.trim(), done: false }],
      next: next + 1,
      draft: '',
    })
  }
  remove(event: Event): void {
    const key = keyOf(event)
    this.update({ items: this.state.items.filter((item) => item.key !== key) })
  }
  edit(event: Event): void {
    this.update({ editing: keyOf(event) })
  }
  save({ key, text }: FormArgs): void {
    this.update({
      items: this.state.items.map((item) =>
        item.key === key ? { ...item, text: String(text) } : item
      ),
      editing: null,
    })
  }
  stopEditing(): void {
    this.update({ editing: null })
  }
  toggle(): void {
    this.update({ open: !this.state.open })
  }
}

/** The key of the row an event came from. */
function keyOf(event: Event): string {
  return (event.target as Element)
    .closest('[data-key]')!
    .getAttribute('data-key')!
}

mountApp(Todo)

// For the tests, which try to mount a second app beside this one.
Object.assign(window, { mumu: { App, mountApp } })
