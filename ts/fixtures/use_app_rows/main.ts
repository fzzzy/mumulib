/**
 * Rows: a list in the state, a row each, and in each row a control bound to
 * its own item. Checking a box changes that item's done; removing a row
 * leaves the others bound to theirs.
 */
import { App, mountApp } from 'mumulib/app'

interface Item {
  key: string
  text: string
  done: boolean
}

class Rows extends App<{ items: Item[] }> {
  static state = {
    items: [
      { key: '1', text: 'one', done: false },
      { key: '2', text: 'two', done: false },
      { key: '3', text: 'three', done: false },
    ],
  }

  get count(): string {
    const { items } = this.state
    const done = items.filter((item) => item.done).length
    return `${items.length === 1 ? '1 thing' : `${items.length} things`}, ${done} done`
  }

  remove(event: Event): void {
    const key = (event.target as Element)
      .closest('[data-key]')!
      .getAttribute('data-key')
    this.update({ items: this.state.items.filter((item) => item.key !== key) })
  }
}

mountApp(Rows)
