import { App, mountApp } from 'mumulib/app'
import type { FormArgs } from 'mumulib/app'

class Page extends App<{ name: string; editing: boolean }> {
  static state = { name: 'world', editing: false }

  get renaming(): { name: string }[] {
    return this.state.editing ? [{ name: this.state.name }] : []
  }
  rename(): void {
    this.update({ editing: true })
  }
  save({ name }: FormArgs): void {
    this.update({ name: String(name), editing: false })
  }
  stop(): void {
    this.update({ editing: false })
  }
}

mountApp(Page)
