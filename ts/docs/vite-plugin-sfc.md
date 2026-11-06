# mumulib/vite-plugin-sfc: single-file components

`mumulib/vite-plugin-sfc` makes each `.sfc.html` file a module, for Vite:
its `<template>` parsed, and its `<script>` -- TypeScript -- the module's
code. A component whose class extends `Mumu` is in [mumu.md](mumu.md); here
is the rest: a component without Mumu, and checking a component's types.

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import { sfcPlugin } from 'mumulib/vite-plugin-sfc'

export default defineConfig({ plugins: [sfcPlugin()] })
```

## Without Mumu

A `.sfc.html` whose class `extends HTMLElement` is a custom element as it
is, and `mumuElement` gives it back unchanged. One with no `<script>` is an
element that shows its template. The script sees `template`, the parsed
`<template>`, and `defineComponent(template)`, which makes that element.

[http://127.0.0.1:8000/examples/use_sfc/](http://127.0.0.1:8000/examples/use_sfc/)

## Type checking

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
