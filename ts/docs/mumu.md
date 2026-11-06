# mumulib/mumu: components

Components: `Mumu`, the class a component's script extends, and
`mumuElement`, which makes the custom element that stands in front of it.

```typescript
import { Mumu, mumuElement } from 'mumulib/mumu' // or from 'mumulib'
```

It brings no state with it: a component's state is given it by its owner --
an app, [`mumulib/app`](app.md), or code of your own.

A component is a `.sfc.html` file: a `<template>`, which may hold a
`<style>`, and a `<script>` in TypeScript whose class extends `Mumu`.
`mumulib/vite-plugin-sfc` makes each one a module, and `mumuElement` makes
the custom element that stands in front of the class.

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import { sfcPlugin } from 'mumulib/vite-plugin-sfc'

export default defineConfig({ plugins: [sfcPlugin()] })
```

```html
<!-- opener.sfc.html -->
<template>
  <button data-slot="label" data-attr="class=classes">Open</button>
  <p class="panel" data-attr="hidden=closed">Opened</p>
</template>

<script>
  import { Mumu } from 'mumulib'

  export default class Opener extends Mumu<{ open: boolean }> {
    static template = template
    static state = { open: false }

    get label(): string {
      return this.state.open ? 'Close' : 'Open'
    }
    get classes(): string {
      return this.state.open ? 'open' : ''
    }
    get closed(): boolean {
      return !this.state.open
    }
    onClick(): void {
      this.emit('toggle')
    }
  }
</script>
```

```typescript
/// <reference types="mumulib/sfc-client" />
import { mumuElement } from 'mumulib'
import Opener from './opener.sfc.html'

customElements.define('my-opener', mumuElement(Opener))

const opener = document.querySelector('my-opener')!
opener.addEventListener('toggle', () => (opener.open = !opener.open))
```

The class never touches the page. It reads its state, works out what to
show in getters, and asks for changes with `emit`; the element does the
rest. Whoever owns the element -- the page, or a component around it --
keeps the state, sets it, and listens for what the component asks.

[http://127.0.0.1:8000/examples/use_mumu/](http://127.0.0.1:8000/examples/use_mumu/)

## State

`static state` names the component's state and gives each its default.
Each is a property of the element: its owner sets it, `opener.open = true`,
and the component reads it as `this.state.open`. The component cannot change
its state -- a setter in its class is an error -- and asks its owner to,
with `emit`.

- **Setting a property renders.** Setting one to the very value it already
  has does nothing, so an owner can set all of a component's state again on
  every change without asking what changed.
- **A change is a new value.** Whether something changed is decided with
  `===`, so a list or an object changed in place looks the same and shows
  nothing. Give the component a new one: `{ ...town, name }`, `[...lines,
line]`.
- **Properties, not attributes.** `<my-opener open>` does not set the
  state: an attribute is a string, and the state is any value. Set the
  property, from code, or from a component around it with `data-prop`.
- **Names an element already has are refused.** A state property is a
  property of the element, so `title`, `role`, `hidden` and every other name
  an element has would hide the element's own. `mumuElement` throws, naming
  it, when the component is defined.

## The template

Four attributes mark what a template shows. Each names a slot, and a slot's
value is the state property of that name, or else the component's getter of
that name.

- **`data-slot="label"`** fills the element's content with the slot's value,
  as text.
- **`data-attr="class=classes,title=hint"`** fills attributes: `class` from
  the slot `classes`, `title` from `hint`. A boolean adds the attribute or
  takes it away -- `data-attr="hidden=closed"`, `disabled=busy` -- as an
  attribute's presence, and not its value, is what it means.
- **`data-prop="value=level"`** sets the element's property `value` from the
  slot `level`. That is how a component hands state to a component inside
  it, `<my-light data-prop="connected=online">`, and how an `<input>` is
  given its `value`.
- **`data-pat="foreach"`** inside a slot makes the slot a list. Its value is
  a list of objects, and the element marked is copied once for each, its own
  `data-slot`, `data-attr` and `data-prop` filled from the object's fields.
  A component may have as many lists as it has slots. A slot with two rows is
  an error, and so is a list of objects given to a slot with none.

  ```html
  <ul data-slot="people">
    <li data-pat="foreach" data-attr="class=kind" data-slot="name">Ada</li>
  </ul>
  ```

  The row may instead be the one element inside a `<template
data-pat="foreach">`. A template's content is inert -- a component in it
  is not made -- until the row is copied into the page, which is what a page
  whose markup is in the HTML wants: its rows are not running before there
  is anything to show.

  ```typescript
  get people() {
    return this.state.people.map((p) => ({ key: p.id, name: p.name, kind: p.role }))
  }
  ```

A render writes only what changed: a slot whose value is the very one it
last had is not written again. A list's rows are kept from one render to the
next, matched to the items by each item's `key`, or by its place in the list
if it has none, and a kept row is filled again only when its item's values
change. Give items a `key` when they come and go from anywhere but the end.

The template is plain HTML, so it can be opened and edited with its sample
content in it: "Open", "Ada". What a slot holds in the file is replaced as
the component renders.

## Events

A method named `on` and an event, in any case -- `onClick`, `onInput`,
`onKeyDown`, `onPointerCancel` -- is called for that event anywhere inside
the component, whether or not the event bubbles: `onFocus` hears a focus,
and `onClose` a `<dialog>`'s close. The events are those of elements in the
HTML standard and the standards beside it: mouse, pointer and touch,
keyboard and composition, focus, forms, clipboard, drag and drop, dialogs and
popovers, scrolling, animations and transitions, and media. A method named
for an event that no element has, `onClik`, is an error.

`this.emit(name, detail)` dispatches a custom event from the element, for
its owner. It bubbles out of every component it is inside, to wherever the
state is kept.

## Binding, and dialogs

A component's controls are bound as an app's are: `<input name="this.text">`
shows the component's `text`, and what is typed in it goes to the component's
owner, as a change of whatever the owner gave it as `text` by `data-prop` --
`<my-field data-prop="text=title">` is bound to the app's `title`. The
component handles nothing: it cannot change its state, and the change is its
owner's to make. A `<form>` in a `<dialog>` calls the component's own method
as it is submitted, and the component asks its owner with `emit`.
[app.md](app.md) says how both work.

## Its own elements

The state is the owner's, but the component's own elements are its own, to
do with what it likes: open a dialog, read a form, draw on a canvas.

- **`data-ref="dialog"`** puts the element in `this.refs.dialog`.
- **`onMount()`** is called once, as the component first appears: to open
  its dialog, say.
- **`onRender()`** is called after every render: to redraw a canvas.
- **`autofocus`** on an element in the template gives it the focus as the
  component appears. The element passes the focus it is given to what is
  inside it.
- **`<style>`** in the template styles the component alone: its template is
  in a shadow root.

Define the elements before anything makes one: an element made, and its
state set, ahead of `customElements.define` would hide its state
properties, and it throws as it is defined, saying so.
