# mumulib/dialog

Import it with the rest of the library, `import { dialog } from 'mumulib'`, or
alone, `import { do_dialog } from 'mumulib/dialog'`, which brings nothing else
with it but what it uses. This is the dialog of the `state` module's pages. An
app's dialog is simpler: its form calls one of the app's methods, as
[app.md](app.md) says.

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

## dialog api

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
