# mumulib/sync

Import it with the rest of the library, `import { sync } from 'mumulib'`, or
alone, `import { bind } from 'mumulib/sync'`, which brings nothing else with
it but what it uses.

`sync.bind(path, url)` fetches `<url>.json` from mumulib's Python server -- a
resource's state, or a persist's document -- and puts it in the state at
`path`, with `set_path`. It fetches it again whenever the server's change
stream, `/mumulib/changes.sse`, announces `url` or a URL inside it: every
page open shows each change, anyone's, without reloading. A write inside
what was fetched changes it -- a binding of `/presence` hears
`/presence/p7` -- and `{ exact: true }` hears `url` alone. URLs are compared as paths, without an
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

## sync api

```ts
bind(path: string, url: string, options?: { exact?: boolean }): Promise<void>
```

Fetch `<url>.json` into the state at path, and fetch it again whenever the change stream announces url, or a URL inside it unless exact -- compared as paths on this origin, without an extension, a query or a fragment, a trailing slash kept. Resolves once the first fetch is in place.
