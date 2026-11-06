# mumulib/app: the app

`import { App, mountApp } from 'mumulib/app'`, or from `'mumulib'`.

The app is the one component on a page with state of its own. Its template
is the page itself: `mountApp(Page)` takes the body's markup, as the page has
it, sample content and all, and draws the app there from then on. There is
no shadow root, so the page's own styles reach everything in it.

```html
<head>
  <script type="module" src="./main.ts"></script>
</head>
<body>
  <my-counter data-prop="count=count" data-on="add=add"></my-counter>
  <p data-attr="hidden=few">That's a lot.</p>
</body>
```

```typescript
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

[http://127.0.0.1:8000/examples/small_app/](http://127.0.0.1:8000/examples/small_app/)

An app is a component -- it has what [mumu.md](mumu.md) says a component
has: slots, `data-attr`, `data-prop`, `foreach` rows, `on<Event>` methods,
refs, `onMount` and `onRender` -- and beside that:

- **`static state`** is the state it starts with.
- **`this.update(change)`** changes the state: the change is merged into it,
  and the page drawn again, once for the whole change. An app may override
  it, to have its changes go through something else -- a store, say.
- **The state is frozen**, the state object and each value in it one level
  down. A change is a new value, `[...items, item]`; an array pushed onto,
  or an object assigned to, throws where it happens, rather than showing
  nothing.
- **Getters only present the state.** They work out what the page shows from
  it, and nothing writes to them.
- **One app on a page.** Mounting a second while the first is in the page
  throws.

## The page

`mountApp(Page)` draws into the body; `mountApp(Page, element)` draws into
that element instead, for an app in part of a page. The page's scripts go in
the `<head>` -- a module script is deferred anyway -- since everything in the
body is the app's template.

What the page holds shows until the app first draws, so it can hold a spinner,
and its sample content can be opened and edited as it is. What should not
run before the first draw -- a component that starts work as it is made --
goes in a row's `<template data-pat="foreach">`, inert until it is copied in.
What comes and goes is a list of none or one, from a getter:

```typescript
get panels() {
  return this.state.open ? [{ key: 'panel' }] : []
}
```

Define the page's custom elements before mounting it: the app sets their
properties as it first draws.

## Events: data-on

`data-on="event=method"` on any element of the page, in a row too, calls the
app's method when that event reaches the element: `data-on="click=add"`,
`data-on="close=stop,retry=retry"`. A component's own events, which `emit`
sends out of every component around it, come up the same way as the
browser's. The method is given the event. A `data-on` naming a method the app
does not have is refused as the app is mounted.

## Binding

A control whose name starts with `this.` is bound to the state:
`<input name="this.name">` shows the state's `name`, and what is typed in it
is the state's `name`, as it is typed. No form, no method, no event.

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

[http://127.0.0.1:8000/examples/small_binding/](http://127.0.0.1:8000/examples/small_binding/)

A checkbox is whether it is checked; a radio button, as it is checked, its
value; a multiple `<select>` the list of its chosen values; anything else its
text. The state is shown in a control whenever what it is bound to changes --
a draft cleared as it is added clears the input, though it has the focus.

A path is followed through the state: `name="this.profile.name"`. In a row,
`this.` is the row's item, so `<input type="checkbox" name="this.done">` in
a row of the state's list `items` is bound to `items.<its place>.done`. In a
component, `this.` is the component's own state, which its owner gave it, so
the change goes up to the owner, through each `data-prop` it came down by,
until it reaches the app's state.

A binding goes through the state alone. A getter only presents the state, and
cannot be written to, so a control bound to one, a row of a getter's list
with a bound control in it, or a component bound to what a getter gave it, is
refused -- as the page is mounted, where that can be known, or as it is typed
in.

## Dialogs

A dialog's form is a draft, and calls a method when it is submitted. A
hidden input named `method` names the method, which is called with the
form's values by name; a submit button whose value is `cancel` closes the
dialog and calls nothing, as Escape does. Its fields are filled from the
state as the dialog is drawn, with `data-prop="value=name"`, and are not bound
-- a `this.` control in a `<dialog>` is refused, as is a `method` the app does
not have.

A dialog that is a row -- a list of none or one, there while the state says
so -- opens as it appears.

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

[http://127.0.0.1:8000/examples/small_dialog/](http://127.0.0.1:8000/examples/small_dialog/)

The method is given what [dialog.md](dialog.md) says a form's method is: a
`[]` name always a list, a name given twice a list too. `close` comes when the
dialog closes however it closes, so `stop` puts the state back after Escape
and Cancel; after Save, `save` has already done so.

`examples/use_app` puts all of it together: a to-do list, with a bound input,
bound checkboxes in its rows, a component bound to the app's title, and a
dialog editing one item.
