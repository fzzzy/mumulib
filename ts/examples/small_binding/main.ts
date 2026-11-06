import { App, mountApp } from 'mumulib/app'

class Page extends App<{ name: string; loud: boolean }> {
  static state = { name: '', loud: false }

  get greeting(): string {
    const name = this.state.name || 'world'
    return this.state.loud ? `${name.toUpperCase()}!` : name
  }
}

mountApp(Page)
