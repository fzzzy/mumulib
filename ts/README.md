# mumulib

mumulib builds web pages from components and state, in TypeScript, with
templates in plain HTML.

A component is one `.sfc.html` file: a `<template>` of ordinary HTML, marked
with a few `data-` attributes, and a class that says what the template shows.
The page is the app: its own HTML is its template, and its class keeps the
state, hands each component its part, and does what they ask.

Four small examples show the whole of it. Each is a page in `examples/`,
which `make run` serves from the
[repository](https://github.com/fzzzy/mumulib).

## Setting up

Components are compiled by mumulib's Vite plugin:

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import { sfcPlugin } from 'mumulib/vite-plugin-sfc'

export default defineConfig({ plugins: [sfcPlugin()] })
```

## A component

A counter, which shows its count and asks for one more. It never changes its
count itself: it is given it, and asks its owner with `emit`.

```html
<!-- counter.sfc.html -->
<template>
  <p>Count: <span data-slot="count">0</span></p>
  <button>Add one</button>
</template>

<script>
  import { Mumu } from 'mumulib/mumu'

  export default class Counter extends Mumu<{ count: number }> {
    static template = template
    static state = { count: 0 }

    onClick(): void {
      this.emit('add')
    }
  }
</script>
```

`data-slot="count"` shows the state's `count`, and `onClick` is called for a
click anywhere in the component.

## An app

The page's body is the app's template. `data-prop` hands the counter its
count from the app's state, `data-on` brings its `add` back to the app's
method, and a getter works out what the page shows from the state.

```html
<!-- index.html -->
<head>
  <script type="module" src="./main.ts"></script>
</head>
<body>
  <my-counter data-prop="count=count" data-on="add=add"></my-counter>
  <p data-attr="hidden=few">That's a lot.</p>
</body>
```

```typescript
// main.ts
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
```

[examples/small_app](http://127.0.0.1:8000/examples/small_app/)

## Binding

A control whose name is `this.` and a path into the state is bound to it:
it shows it, and what is typed in it is the state's, as it is typed.

```html
<body>
  <input name="this.name" placeholder="Your name" />
  <label><input type="checkbox" name="this.loud" /> Loud</label>
  <p>Hello, <span data-slot="greeting">world</span></p>
</body>
```

```typescript
import { App, mountApp } from 'mumulib/app'

class Page extends App<{ name: string; loud: boolean }> {
  static state = { name: '', loud: false }

  get greeting(): string {
    const name = this.state.name || 'world'
    return this.state.loud ? `${name.toUpperCase()}!` : name
  }
}

mountApp(Page)
```

[examples/small_binding](http://127.0.0.1:8000/examples/small_binding/)

## A dialog

A dialog's form is a draft: filled from the state as it is drawn, and given to
a method when it is saved. The hidden `method` input names the method; Cancel
and Escape call nothing. The dialog is a list of none or one, in a
`<template>`, and opens as it appears.

```html
<body>
  <p>Hello, <span data-slot="name">world</span></p>
  <button data-on="click=rename">Rename</button>
  <div data-slot="renaming">
    <template data-pat="foreach">
      <dialog data-on="close=stop">
        <form>
          <input type="hidden" name="method" value="save" />
          <input name="name" data-prop="value=name" />
          <button>Save</button>
          <button value="cancel">Cancel</button>
        </form>
      </dialog>
    </template>
  </div>
</body>
```

```typescript
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
```

[examples/small_dialog](http://127.0.0.1:8000/examples/small_dialog/)

## The parts

Each part is imported alone by its own path, and brings only what it uses --
`mumulib/mumu` brings no state -- or all of them together from `mumulib`.

| Import                                                     | What it is                                                           |
| ---------------------------------------------------------- | -------------------------------------------------------------------- |
| [`mumulib/mumu`](docs/mumu.md)                             | Components: `Mumu`, `mumuElement`                                    |
| [`mumulib/app`](docs/app.md)                               | The app: `App`, `mountApp`, `data-on`, binding, dialogs              |
| [`mumulib/vite-plugin-sfc`](docs/vite-plugin-sfc.md)       | The `.sfc.html` plugin, components without Mumu, and type checking   |
| [`mumulib/state`](docs/state.md)                           | The page's state as one tree, with `onstate` and `set_state`         |
| [`mumulib/patslot`](docs/patslot.md)                       | Templates filled from code: patterns and slots                       |
| [`mumulib/dialog`](docs/dialog.md)                         | Forms in `<dialog>`s for pages kept with `state`                     |
| [`mumulib/events`](docs/events.md)                         | Event streams, all sharing one connection to mumulib's Python server |
| [`mumulib/sync`](docs/sync.md)                             | Part of the state kept the same as the Python server's               |
| [`mumulib/vite-plugin-origin`](docs/vite-plugin-origin.md) | Pages another server serves, their modules from Vite's dev server    |
| [`mumulib/node`](docs/node.md)                             | The library in Node, with a DOM made for it                          |

The notes page, `pages/notes`, served by `py/examples/notes.py`, is an app
with all of it at once, its state bound to the server.
