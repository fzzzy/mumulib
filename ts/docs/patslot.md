# mumulib/patslot

Import it with the rest of the library, `import { patslot } from 'mumulib'`,
or alone, `import { fill, clone_pat } from 'mumulib/patslot'`, which brings
nothing else with it but what it uses.

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

## patslot api

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
