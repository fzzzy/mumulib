# mumulib

mumulib builds web pages from components and state, in TypeScript, with
templates in plain HTML.

A component is one `.sfc.html` file: a `<template>` of ordinary HTML, marked
with a few `data-` attributes, and a class that says what the template shows.
Set a component's properties and it fills its template; it asks for changes
by sending events. The page keeps its state with the `state` module and
gives each component its part of it.

Beside them are the parts the components are built on, each usable alone:
`patslot` fills a template from code, `dialog` shows forms in `<dialog>`s,
`events` shares event streams, and `sync` keeps part of the state the same
as mumulib's Python server's.

## Examples

The links below go to the examples as `make run` serves them, from the
[repository](https://github.com/fzzzy/mumulib), which also says how to build
and check the library.

## Components

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

### State

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

### The template

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

### Events

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

### Its own elements

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

### Without Mumu

A `.sfc.html` whose class `extends HTMLElement` is a custom element as it
is, and `mumuElement` gives it back unchanged. One with no `<script>` is an
element that shows its template. The script sees `template`, the parsed
`<template>`, and `defineComponent(template)`, which makes that element.

[http://127.0.0.1:8000/examples/use_sfc/](http://127.0.0.1:8000/examples/use_sfc/)

### Type checking

A component's script has a source map back to its own lines in the
`.sfc.html`, and coverage tools such as vite-plugin-istanbul count it -- give
them `.html` among their extensions.

Vite strips a component's types without checking them, and tsc cannot see
into a `.sfc.html`, so `mumulib-sfc-check` checks them: with the project's
tsconfig, each error at its line and column in the component, exiting 1 if
there are any. Give it the directories to look in, or it searches the working
directory; `--project` names a tsconfig. It needs `typescript` installed.

```sh
npx mumulib-sfc-check src
```

Given a tsconfig with `--project`, it checks the files that tsconfig names
too, in the same program, and an import of a `.sfc.html` in any of them is
the component's own class: `InstanceType<typeof Counter>` has the counter's
properties, where tsc alone knows only `sfc-client`'s "some custom element".
Run it so in place of tsc, as `make check` does over the examples:

```sh
npx mumulib-sfc-check --project tsconfig.examples.json examples
```

With `--declarations` it also writes each component's declarations beside
it, `counter.sfc.html.d.ts`, which TypeScript reads for an import of
`./counter.sfc.html` with no setting needed. Then tsc, and any editor, knows
the component's own class too, not only the checker. They are generated from
the component, so leave them out of git -- `*.sfc.html.d.ts` in
`.gitignore` -- and write them whenever the components may have changed, as
this repository's `make check` and `make run` do.

## state

The state module provides simple state management with a toplevel javascript object and a function set_state which takes a new object and updates the state by merging all toplevel keys with the old state. The onstate function registers a callback which is called when the state has changed.

```typescript
import { state } from 'mumulib'

state.onstate((new_state) => {
  const node = document.createElement('div')
  node.textContent = 'Got state ' + JSON.stringify(new_state)
  document.appendChild(node)
})

state.set_state({ hello: 'world' })

state.set_path('hello', 'everybody')
```

[http://127.0.0.1:8000/examples/use_state/](http://127.0.0.1:8000/examples/use_state/)

&lt;input&gt; elements whose name starts with "this." will automatically update the state when those inputs change. Validation can be performed by using JavaScript setter functions in your state tree or by using the built in html input types such as color, email, month, number, range, tel, time, url, etc.

```html
<div>
  <input name="this.name" placeholder="Name" />
  <input name="this.age" placeholder="Age" type="number" />
  <div>Favorite color <input name="this.color" type="color" /></div>
</div>
```

```typescript
import { state } from 'mumulib'

state.onstate((new_state) => {
  const node = document.createElement('div')
  node.textContent = 'Got state ' + JSON.stringify(new_state)
  document.appendChild(node)
})
```

[http://127.0.0.1:8000/examples/use_state_input/](http://127.0.0.1:8000/examples/use_state_input/)

There is a special toplevel state key "selected" which is the path to the currently selected state object. Inputs whose name start with "selected." will use the object at the path specified by the toplevel "selected" key as the root when traversing the path and setting the state.

```html
<input type="radio" name="selected" value="person1" />
<input type="radio" name="selected" value="person2" />

<div>
  <input name="selected.name" placeholder="Name" />
  <input name="selected.age" placeholder="Age" type="number" />
  <div>Favorite color <input name="selected.color" type="color" /></div>
</div>
```

```typescript
import { state } from 'mumulib'

state.onstate(async (new_state) => {
  const node = document.createElement('div')
  node.textContent = 'Got state ' + JSON.stringify(new_state)
  document.body.appendChild(node)
})
```

[http://127.0.0.1:8000/examples/use_state_selected/](http://127.0.0.1:8000/examples/use_state_selected/)

### state and components

A page keeps its state with `state`, and draws itself from it with one
`onstate` callback: it sets each component's properties from the state,
every time, all of them. That is cheap however little changed, as a
component set to what it already has does nothing. What a component asks
for, the page does with `set_state`, and the state comes round again.

```typescript
import { state } from 'mumulib'

const opener = document.querySelector('my-opener')!
const lights = document.querySelector('my-lights')!

state.onstate(async (s) => {
  opener.open = s.open
  lights.connected = s.open
})
opener.addEventListener('toggle', () => state.set_state({ open: !opener.open }))

state.set_state({ open: false })
```

### state api

```ts
type State = { [key: string]: any } | any
type OnStateChange = (state: State) => Promise<void>
```

```ts
onstate(callback: OnStateChange): Promise<void>
```

Registers callback to be called when the state has changed.

```ts
set_state(new_state: State): Promise<void>
```

Applies all toplevel keys in new_state to the old state object, and calls all the onstate handlers if the state has changed. onstate handlers are free to call set_state again and onstate handlers will be called again on the next animation frame.

```ts
set_path(path: string, new_substate: State): Promise<void>
```

Traverses the given path and sets the substate to new_substate. If the state has changed, calls all the onstate handlers.

```ts
debug(mode: boolean): void
```

Whether to log the state, and write it to the body's `data-state`, on each change; and to log what changes it, and what dialogs do. Nothing is logged unless it is on.

The state itself is not exported. A page reads it as `onstate` gives it, as it changes, and changes it with `set_state` and `set_path` -- never by reaching into the tree and mutating it.

## patslot

Patterns and Slots provide a very simple html templating mechanism with templates that can be edited with sample data in them in a graphical html editor. There are only three tag attributes: data-pat, data-slot, and data-attr. All logic is delegated to normal TypeScript or JavaScript code.

```html
<dl data-pat="person" data-attr="style=color">
  <dt>Name</dt>
  <dd data-slot="name">John Smith</dd>
  <dt>Age</dt>
  <dd data-slot="age">42</dd>
</dl>
```

```typescript
import { patslot } from 'mumulib'

window.onload = async () => {
  // Returns an HTMLElement with the slots filled
  let node = await patslot.clone_pat('person', {
    name: 'Jane Smith',
    age: 12,
    color: 'color: blue',
  })

  document.body.appendChild(node)
}
```

[http://127.0.0.1:8000/examples/use_patslot/](http://127.0.0.1:8000/examples/use_patslot/)

There is a convenience function fill_body you can use to fill the top level slots in your page. If you have an HTML element you wish to fill, fill does the same for its slots, and fill_slots fills one slot by name.

```html
<dl data-attr="style=color">
  <dt>Name</dt>
  <dd data-slot="name">John Smith</dd>
  <dt>Age</dt>
  <dd data-slot="age">42</dd>
</dl>

<div id="fill-element">
  This element has <span data-slot="fill_me"> not been filled yet.</span>
</div>
```

```typescript
import { patslot } from 'mumulib'

window.onload = async () => {
  await patslot.fill_body({
    name: 'Jane Smith',
    age: 12,
    color: 'color: blue',
  })
  setTimeout(() => {
    patslot.fill_slots(
      document.getElementById('fill-element') as HTMLElement,
      'fill_me',
      'now been filled.'
    )
  }, 500)
}
```

[http://127.0.0.1:8000/examples/use_patslot_fill/](http://127.0.0.1:8000/examples/use_patslot_fill/)

You can use JavaScript generators to make rendering nested hierarchies easy.

```html
<main>
  <ol data-slot="towns">
    <li data-pat="town">
      <h1>Town:</h1>
      <div data-slot="town_name"></div>
      <h2>People:</h2>
      <div data-slot="people">
        <dl data-pat="person">
          <dt>Name</dt>
          <dd data-slot="name"></dd>
          <dt>Age</dt>
          <dd data-slot="age"></dd>
        </dl>
      </div>
    </li>
  </ol>
</main>

<footer data-slot="footer"></footer>
```

```typescript
import { patslot } from 'mumulib'

const dataset = {
  towns: [
    {
      name: 'Los Angeles',
      people: [
        { name: 'Joe Smith', age: 67 },
        { name: 'Example Person', age: 2 },
      ],
    },
    {
      name: 'London',
      people: [
        { name: 'Jane Smith', age: 23 },
        { name: 'John Doe', age: 34 },
      ],
    },
  ],
}

function render_people(people) {
  return people.map((person) => patslot.clone_pat('person', person))
}

function* render_towns(towns) {
  for (const town of towns) {
    yield patslot.clone_pat('town', {
      town_name: town.name,
      people: render_people(town.people),
    })
  }
}

window.onload = async () => {
  patslot.fill_body({
    towns: await render_towns(dataset.towns),
    footer: 'This is the footer.',
  })
}
```

[http://127.0.0.1:8000/examples/use_patslot_nested/](http://127.0.0.1:8000/examples/use_patslot_nested/)

### patslot api

```ts
type SyncPattern =
  | HTMLElement
  | (
      | HTMLElement
      | Promise<HTMLElement | string>
      | Generator<Pattern>
      | AsyncGenerator<Pattern>
      | string
    )[]
  | Generator<Pattern>
  | AsyncGenerator<Pattern>
  | string
  | number
type Pattern = Promise<SyncPattern> | SyncPattern
```

```ts
clone_pat(pattern_name: string, slot_values: { [key: string]: Pattern }): Promise<HTMLElement>
```

Clone a pattern in the current html page and fill any slots with the given values. Return the filled HTMLElement.

```ts
template(url: string): Promise<Template>
```

The template at url: another page, whose patterns its `clone_pat(pattern_name, slot_values)` clones and fills, as `clone_pat` does the current page's. A promise, so how it is had can change -- fetched before it resolves, say -- without changing a caller.

```ts
fill(element: HTMLElement, slot_values: { [key: string]: Pattern }): Promise<void>
```

Given an HTMLElement, fill its slots with the given slot_values, as fill_body does for the page.

```ts
fill_slots(element: HTMLElement, slot_name: string, slot_value: Pattern): Promise<void>
```

Given an HTMLElement, fill the slots with the given name with the given value.

```ts
append_to_slots(element: HTMLElement, slot_name: string, slot_value: Pattern): Promise<void>
```

Given an HTMLElement, append the given values to the named slots.

```ts
fill_body(slot_values: { [key: string]: Pattern }): Promise<void>
```

Fill slots in the current html page body with the given slot_values.

## dialog

The dialog module provides a simple function for showing a &lt;dialog&gt; element with forms in it and automatically calling a method of your choice when a form is submitted.

If your dialog contains a &lt;form&gt; element, you can use a hidden input with the name "path" and one with the name "method" to specify a "path" into the state tree to an object whose "method" attribute will be called with a list of all of the &lt;form&gt; &lt;input&gt; values when a form is submitted.

```html
<dialog id="my_dialog">
  <form>
    <input type="hidden" name="path" value="this.my_object" />
    <input type="hidden" name="method" value="my_method" />
    <input name="name" />
    <input type="number" name="age" />
    <button>Save</button>
  </form>
</dialog>
```

```typescript
import { state, dialog } from 'mumulib'

class MyObject {
  my_method(args) {
    const node = document.createElement('div')
    node.textContent = 'my_method was called ' + args.name + ' ' + args.age
    document.body.appendChild(node)
  }
}

state.onstate(async (new_state) => {
  if (!new_state.my_object) {
    state.set_state({ my_object: new MyObject() })
  } else {
    dialog.do_dialog('my_dialog', 'this.my_object', (el, _state) => {
      return el
    })
  }
})
```

[http://127.0.0.1:8000/examples/use_dialog/](http://127.0.0.1:8000/examples/use_dialog/)

The method is called with every value the form has, by name: a `<textarea>`
and a `<select>` as well as each `<input>`, and a form-associated custom
element as any control. A name ending in `[]` is always a list, without the
brackets, so a `<select multiple name="members[]">` with one choice gives
`{members: ['c1']}`, and with none `{members: []}`, unless it is disabled; a
name given twice is a list too. The render function may fill the dialog in
place and return it, and may be async.

### dialog api

```ts
type RenderFunc = (
  el: HTMLElement,
  state: object
) => HTMLElement | Promise<HTMLElement>
type FormArgs = { [key: string]: string | string[] }
```

```ts
do_dialog(dialog_id: string, path: string, render: RenderFunc): Promise<void>
```

Fetch the state at path, call the render function, set the contents of the &lt;dialog&gt; element with the id dialog_id to the result of the render function, and display the dialog.

## events

`events.source(url)` listens to the event stream at `url` as
`new EventSource(url)` would -- `onmessage`, `onopen`, `onerror`,
`addEventListener`, `close`, `readyState` -- but every source on a page
shares one connection: the Python server's hub, `/mumulib/events.sse`, which
subscribes to each and sends everything back on one stream. A browser opens
six connections to a host, and an event stream holds one for as long as it
is open; over the hub a page holds one, however many it listens to.

```typescript
import { events } from 'mumulib'

const terminal = events.source('api/terminal.sse')
terminal.onmessage = (event) => write(event.data)
terminal.addEventListener('turn_ended', () => beep())
const shots = events.source('api/screenshots.sse')
```

Sources made at once open one stream; adding or closing one opens it again
with the topics there are. A page below a prefix -- an app mounted at
`/cb/` -- says so first, `events.at('/cb/')`. `examples/use_events` is a
page listening to three.

### events api

```ts
source(url: string): Source
at(prefix: string): void
```

`source`: an `EventSource`'s shape for the stream at url, over the hub's. `at`: where the hub is, the app's prefix, `/` unless said.

## sync

`sync.bind(path, url)` fetches `<url>.json` from mumulib's Python server -- a
resource's state, or a persist's document -- and puts it in the state at
`path`, with `set_path`. It fetches it again whenever the server's change
stream, `/mumulib/changes.sse`, announces `url`: every page open shows each
change, anyone's, without reloading. URLs are compared as paths, without an
extension, a query or a fragment, so `/notes` and `/notes.json` are one.

The page never changes a bound path itself. It writes with a request -- a
`PUT` or a `DELETE` inside a persist, or what a resource's handler answers
-- and its own change comes back as anyone's does, announced and fetched.

```typescript
import { state, sync } from 'mumulib'

await state.onstate(async (current) => render(current.notes ?? []))
await sync.bind('notes', '/notes')

// Adding one: the server writes it, announces /notes, and the page fetches
await fetch('/notes/last.json', { method: 'PUT', body: JSON.stringify('Milk') })
```

A page has one change stream, opened by its first `bind`, over the hub's
stream with whatever else it listens to (see events). A bound URL is a
resource or a persist: a slash is refused. `ts/pages/notes`, served by
`py/examples/notes.py`, is a whole page bound this way.

### sync api

```ts
bind(path: string, url: string): Promise<void>
```

Fetch `<url>.json` into the state at path, and fetch it again whenever the change stream announces url -- compared as paths on this origin, without an extension, a query or a fragment, a trailing slash kept. Resolves once the first fetch is in place.

## The origin plugin

`mumulib/vite-plugin-origin` is for pages another server serves -- mumulib's
Python server, with `static.Page` -- while Vite's dev server serves their
modules. In development, Vite writes the URLs in an HTML entry
root-relative, `/mumulib-vite/notes/main.ts`, which from the other server's
origin would be asked of it. `originPlugin(origin)` puts the dev server's
origin in front of each, wherever the base appears quoted -- a base as
distinctive as `/mumulib-vite/` is in nothing else on a page -- so the
browser fetches Vite's client and the page's modules from Vite, and hot
reloading connects to it. It needs that base: under Vite's default, `/`,
every root-relative URL on the page would be sent to Vite, links to the
other server's pages too, so the dev server refuses to start with it.

```ts
import { originPlugin } from 'mumulib/vite-plugin-origin'

export default defineConfig({
  base: '/mumulib-vite/',
  plugins: [originPlugin('http://127.0.0.1:5757')],
  server: { host: '127.0.0.1', port: 5757, strictPort: true },
})
```

An entry loads by root-relative URLs, `<script src="/notes/main.ts">`, which
Vite puts under the base. A relative `src`, or a relative `href` on a
`<link>`, would resolve against the other server's page, so the plugin
refuses the entry, naming it and the URL, in development and in a build
alike. It changes nothing else in a build. This repository's
`ts/vite.pages.config.mts` uses it, for `ts/pages`.

## Node

In Node, import `mumulib/node`: the library, with a DOM made first by
[domino](https://github.com/fgnass/domino) -- `document`, and the element
classes mumulib needs, set on `globalThis`. A DOM already there, such as
jsdom's, is left alone.

```js
import { state, patslot } from 'mumulib/node'
// or
const { state, patslot } = require('mumulib/node')
```

`mumulib` itself sets nothing on import. Where you have a DOM of your own,
import it instead; with none, it cannot load, as it reads `document` as it
does.
