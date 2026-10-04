# mumulib

mumulib is a simple typescript state management, html templating, and form processing library. It contains four modules: state, patslot, dialog, and sync.

state provides a simple method for managing state and a way to register onstate callbacks to react to state changes.

patslot provides a simple html templating api, with html templates that can be filled with sample data and all logic being performed in normal TypeScript or JavaScript code.

dialog provides functionality to show html dialog elements populated with state from the state module, and automatically update the state when form inputs in the dialog change.

sync binds a path in the state to a URL on mumulib's Python server, and keeps it the same as the server's, as anyone changes it.

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

## Examples

The links below go to the examples as `make run` serves them, from the
[repository](https://github.com/fzzzy/mumulib), which also says how to build
and check the library.

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

Whether to log the state, and write it to the body's `data-state`, on each change.

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
`{members: ['c1']}`; a name given twice is a list too. The render function may
fill the dialog in place and return it, and may be async.

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

A page has one change stream, opened by its first `bind`. A bound URL is a
resource or a persist: a slash is refused. `ts/pages/notes`, served by
`py/examples/notes.py`, is a whole page bound this way.

### sync api

```ts
bind(path: string, url: string): Promise<void>
```

Fetch `<url>.json` into the state at path, and fetch it again whenever the change stream announces url -- compared as paths on this origin, without an extension, a query or a fragment, a trailing slash kept. Resolves once the first fetch is in place.

## single-file components

`mumulib/vite-plugin-sfc` is a Vite plugin for components written as one HTML
file: a `<template>`, which may hold a `<style>`, and a `<script>` in
TypeScript. Importing a `.sfc.html` gives the custom element class its script
exports as default. With no script, it is a class that renders the template
into its shadow root. The script sees `template`, the parsed `<template>`, and
`defineComponent(template)`, which makes that default class.

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import { sfcPlugin } from 'mumulib/vite-plugin-sfc'

export default defineConfig({ plugins: [sfcPlugin()] })
```

```typescript
/// <reference types="mumulib/sfc-client" />
import Counter from './counter.sfc.html'

customElements.define('my-counter', Counter)
```

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

[http://127.0.0.1:8000/examples/use_sfc/](http://127.0.0.1:8000/examples/use_sfc/)

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
