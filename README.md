mumulib
=====

mumulib is a simple typescript state management, html templating, and form processing library. It contains three modules: state, patslot, and dialog.

state provides a simple method for managing state and a way to register onstate callbacks to react to state changes.

patslot provides a simple html templating api, with html templates that can be filled with sample data and all logic being performed in normal TypeScript or JavaScript code.

dialog provides functionality to show html dialog elements populated with state from the state module, and automatically update the state when form inputs in the dialog change.

Building
=====

Running `make build` converts the typescript files into JavaScript files ready for the browser in the `dist` directory.

Examples
=====

Running `make` also runs build and starts a server on port 8000 which can be used to view the examples link below.

state
=====

The state module provides simple state management with a toplevel javascript object and a function set_state which takes a new object and updates the state by merging all toplevel keys with the old state. The onstate function registers a callback which is called when the state has changed.

```typescript
import { state } from "mumulib";

state.onstate(new_state => {
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.appendChild(node);
});

state.set_state({hello: "world"});

state.set_path("hello", "everybody");
```

[http://127.0.0.1:8000/examples/use_state/](http://127.0.0.1:8000/examples/use_state/)

<input> elements whose name starts with "this." will automatically update the state when those inputs change. Validation can be performed by using JavaScript setter functions in your state tree or by using the built in html input types such as color, email, month, number, range, tel, time, url, etc.

```html
<div>
  <input name="this.name" placeholder="Name" />
  <input name="this.age" placeholder="Age" type="number" />
  <div>Favorite color <input name="this.color" type="color" /></div>
</div>
```

```typescript
import { state } from "mumulib";

state.onstate(new_state => {
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.appendChild(node);
});
```

[http://127.0.0.1:8000/examples/use_state_input/](http://127.0.0.1:8000/examples/use_state)input/)

There is a special toplevel state key "selected" which is the path to the currently selected state object. Inputs whose name start with "selected." will use the object at the path specified by the toplevel "selected" key as the root when traversing the path and setting the state.

```html
<input type="radio" name="selected" value="person1">
<input type="radio" name="selected" value="person2">

<div>
  <input name="selected.name" placeholder="Name" />
  <input name="selected.age" placeholder="Age" type="number" />
  <div>Favorite color <input name="selected.color" type="color" /></div>
</div>
```

```typescript
import { state } from "mumulib";

state.onstate(async new_state => {
  const node = document.createElement("div");
  node.textContent = "Got state " + JSON.stringify(new_state);
  document.body.appendChild(node);
});
```

[http://127.0.0.1:8000/examples/use_state_selected/](http://127.0.0.1:8000/examples/use_state_selected/)

state api
=====

type State = { [key: string]: any };
type OnStateChange = (state: State) => Promise<void>;

onstate(callback: OnStateChange): Registers callback to be called when the state has changed.

set_state(new_state: State): Applies all toplevel keys in new_state to the old state object, and calls all the onstate handlers if the state has changed. onstate handlers are free to call set_state again and onstate handlers will be called again on the next animation frame.

set_path(path: string, new_substate: any): Traverses the given path and sets the substate to new_substate. If the state has changed, calls all the onstate handlers.

patslot
=====

Patterns and Slots provide a very simple html templating mechanism with templates that can be edited with sample data in them in a graphical html editor. There are only three tag attributes: data-pat, data-slot, and data-attr. All logic is delegated to normal TypeScript or JavaScript code.

```html
<dl data-pat="person" data-attr="style=color">
  <dt>Name</dt>
  <dd data-slot="name">
    John Smith
  </dd>
  <dt>Age</dt>
  <dd data-slot="age">
    42
  </dd>
</dl>
```

```typescript
import { patslot } from "mumulib";

window.onload = async () => {
  // Returns an HTMLElement with the slots filled
  let node = await patslot.clone_pat("person", {
    name: "Jane Smith",
    age: 12,
    color: "color: blue"
  });

  document.body.appendChild(node);
}
```

[http://127.0.0.1:8000/examples/use_patslot/](http://127.0.0.1:8000/examples/use_patslot/)

There is a convenience function fill_body you can use to fill the top level slots in your page. There is also the function fill_slots if you have an HTML element you wish to fill.


```html
<dl data-attr="style=color">
  <dt>Name</dt>
  <dd data-slot="name">
    John Smith
  </dd>
  <dt>Age</dt>
  <dd data-slot="age">
    42
  </dd>
</dl>

<div id="fill-element">
  This element has <span data-slot="fill_me"> not been filled yet.</span>
</div>
```

```typescript
import { patslot } from "mumulib";

window.onload = async () => {
  await patslot.fill_body({
    name: "Jane Smith",
    age: 12,
    color: "color: blue"
  });
  setTimeout(() => {
    patslot.fill_slots(
      document.getElementById("fill-element"),
      { fill_me: "now been filled." }
    );
  });
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

<footer data-slot="footer">

</footer>
```

```typescript


import { patslot } from '../../src';


const dataset = {
  towns: [
    {
      name: "Los Angeles",
      people: [
        {"name": "Joe Smith", age: 67},
        {"name": "Example Person", age: 2}
      ]
    },
    {
      name: "London",
      people: [
        {"name": "Jane Smith", age: 23},
        {"name": "John Doe", age: 34}
      ]
    }
  ]
};


function render_people(people) {
  return people.map((person) => patslot.clone_pat("person", person));
}


function* render_towns(towns) {
  for (const town of towns) {
    yield patslot.clone_pat("town", {
      town_name: town.name,
      people: render_people(town.people)
    });
  }
}


window.onload = async () => {
  patslot.fill_body({
    towns: await render_towns(dataset.towns),
    footer: "This is the footer."
  });
}

```

[http://127.0.0.1:8000/examples/use_patslot_nested/](http://127.0.0.1:8000/examples/use_patslot_nested/)

patslot api
=====

type SyncPattern = HTMLElement |
    (HTMLElement | Generator<Pattern> | string)[] |
    Generator<Pattern> |
    string |
    number;
type Pattern = Promise<SyncPattern> | SyncPattern;

clone_pat(pattern_name: string, slot_values: { [key: string]: Pattern}) => HTMLElement: Clone a pattern in the current html page and fill any slots with the given values. Return the filled HTMLElement.

fill_slots(element: HTMLElement, 
slot_name: string, slot_value: Pattern): Given an HTMLElement, fill any slots with the given values.

append_to_slots(element: HTMLElement, slot_name: string, slot_value: Pattern): Given an HTMLElement, append the given values to the named slots.

fill_body(slot_values: { [key: string]: Pattern }): Fill slots in the current html page body with the given slot_values.

dialog
=====

The dialog module provides a simple function for showing a <dialog> element with forms in it and automatically calling a method of your choice when a form is submitted.

If your dialog contains a <form> element, you can use a hidden input with the name "path" and one with the name "method" to specify a "path" into the state tree to an object whose "method" attribute will be called with a list of all of the <form> <input> values when a form is submitted.

dialog api
=====

type RenderFunc = (el: HTMLElement, state: object) => HTMLElement;

do_dialog(dialog_id: string, path: string, render: RenderFunc) => HTMLElement: Fetch the state at path, call the render function, set the contents of the <dialog> element with the id dialog_id to the result of the render function, and display the dialog.

