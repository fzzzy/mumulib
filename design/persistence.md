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
