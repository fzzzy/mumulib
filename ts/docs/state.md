# mumulib/state

Import it with the rest of the library, `import { state } from 'mumulib'`, or
alone, `import { onstate, set_state } from 'mumulib/state'`, which brings
nothing else with it but what it uses.

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

## state and components

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

## state api

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
