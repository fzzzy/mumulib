# Persistence

Status: design in progress. Started 2026-10-01.

How state outlives the process: graduating from objects in RAM to JSON
documents on disk.

## What the code does today

- All state is in memory: plain dicts and lists, and each `Resource`'s
  `self.state`, given to its constructor. Nothing is written to disk, and a
  restart loses every change.
- Every value is addressable. A dict's entry is its own URL
  (`/editors/characters/c1`), and so is a list's element (`/todos/0.json`)
  and a scalar inside either (`/todos/0.txt`). A resource's state is read at
  `/<resource>/state.json`, and each entry below it, `/state/name.txt`.
- Plain containers are writable by default: `PUT` and `DELETE` on an entry
  replace and remove it, a list keeps a tombstone where an element was, and
  `PUT` to `last` appends.
- An object does not know its URL. Traversal carries the segments still to
  walk and the request's whole URL; nothing in the middle of a path knows the
  prefix that reached it.

## Decisions

### 1. One process, one thread, coroutines

Design for the architecture there is: a single process, one thread, and
asyncio. Threads and processes come later, and are designed when they do.

### 2. JSON documents on disk

The next step from RAM is a JSON document on disk for each persisted object.

### 3. Two kinds of node with identity: Resource and Persist

- A **Resource** keeps its state in memory, has behaviour of its own, and
  renders from `self.state`.
- A **Persist** keeps its state on disk, as a file that is the truth, and
  serves it straight from disk.

Behaviour and hot: a resource. Plain durable data: a persist.

Persist starts with JSON alone: its `.json` is its file as it is. Anything
that does not fit that is marked TODO for now.

- TODO: a persist's `.html`, which has to be rendered from its state, so its
  file parsed -- presumably from a template, as a resource's is.

### 4. A persist learns its URL on first access, and loads then

A persist's URL -- and so its file -- is not its own: it is where it sits in
the tree, which is the path walked to reach it. So it is bound when traversal
first delivers a request to it, carrying the path walked, and its state is
loaded from its file then: identity and hydration happen together, lazily.

### 5. One object, one URL

A resource or persist is only ever reached by the one URL it was first
reached by. Reaching it by any other is an error, checked at every access,
and answered with a 500 that logs both URLs: its file, its change
announcements and its liveness all hang on its URL, so one object at two URLs
would be one object with two identities.

### 6. Addressing stays as it is

Everything addressable today stays addressable, and writable as it is:

- plain dicts and lists are traversed as now, and each entry, element and
  scalar inside them has its URL;
- a resource's state is read at `state.json`, and each entry below it, as
  `/state/name.txt`;
- `PUT` and `DELETE` on an entry work as now, a list's tombstones and `last`
  included;
- a `Path`, a file or a directory, is served as it is now.

### 7. Writing: whole-container commits, PATCH for several fields

- A sub-URL's **container** is the nearest persist above it.
- `PATCH` on a container changes several of its fields in one atomic write.
  Its language is JSON Patch (RFC 6902) to start with: a list of operations
  -- `add`, `remove`, `replace`, `move`, `copy`, `test` -- each at a JSON
  Pointer into the document, applied in order, all or none. We see whether
  we like it.
- `PUT` on a sub-URL stays, for the convenient one-field change.
- Either way, a write is one atomic commit of the whole container: its file
  rewritten as a whole (to a temporary file, then renamed over the old). A
  patch is a smaller request, not a smaller write.

### 8. Liveness: a write announces its container

A write to a sub-URL inside a persist announces the **container's** URL, not
the sub-URL: `PUT /characters/c1/name.json`, `c1` being a persist, announces
`/characters/c1`. So an element watching `/characters/c1` hears every change
to it, wherever in it the change was made.

A write with no persist above it -- into plain dicts and lists in memory --
announces what it does today, the request's own URL.

### 9. Caching: sub-URLs share their container's ETag

- A container's `ETag` is its version, derived from its file's modification
  time and its size, so that two writes within the clock's resolution are
  still told apart.
- Every sub-URL inside a container answers with the **container's** `ETag`:
  they are views of one file, so they have one version, and cannot drift
  from it.
- Sub-URL responses, and the container's own, are `Cache-Control: no-cache`
  -- kept, but revalidated before every use -- so each use sends
  `If-None-Match` with the container's `ETag`: 304 if the container has not
  changed, a fresh 200 if it has.
- State in memory, with no file, has no `ETag` for now. The final persist
  design persists state in memory too; that comes later.
