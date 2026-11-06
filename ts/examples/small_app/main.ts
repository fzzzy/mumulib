import { mumuElement } from 'mumulib/mumu'
import { App, mountApp } from 'mumulib/app'
import Counter from './counter.sfc.html'

customElements.define('my-counter', mumuElement(Counter))

class Page extends App<{ count: number }> {
  static state = { count: 0 }

  get few(): boolean {
    return this.state.count < 3
  }
  add(): void {
    this.update({ count: this.state.count + 1 })
  }
}

mountApp(Page)
