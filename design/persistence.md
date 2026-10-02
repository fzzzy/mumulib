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

### 4. A persist learns its URL on first access, and loads then

A persist's URL -- and so its file -- is not its own: it is where it sits in
the tree, which is the path walked to reach it. So it is bound when traversal
first delivers a request to it, carrying the path walked, and its state is
loaded from its file then: identity and hydration happen together, lazily.

### 5. One object, one URL

A resource or persist is only ever reached by the one URL it was first
reached by. Reaching it by any other is an error, checked at every access:
its file, its change announcements and its liveness all hang on its URL, so
one object at two URLs would be one object with two identities.

### 6. Only resources and persists have URLs

A URL ends at a resource or a persist; no scalar -- a string, a number -- is
addressable. Values have no identity of their own, so giving one a URL
aliases it with every equal value elsewhere. Below a persist is the
document's content, read out of it, not tree to traverse: the persist is the
finest addressable unit. A field that needs its own URL, to be fetched or
watched alone, is made a persist nested in its parent.

### 7. PATCH on a container

`PATCH` on a container makes sense. Its language is decided later.

## Open questions

1. **Plain dicts and lists.** Are they still traversable structure, with no
   URL of their own -- or can a container still be fetched whole, as
   `/editors/characters.json` is today?
2. **A resource's state.** Does `/<resource>/state.json` stay, the whole state
   at one URL, with nothing addressable below it -- so `/state/name.txt` goes?
3. **Files and directories.** A `Path` has an identity of its own, its path on
   disk. Is a file a persist, or a kind of its own?
4. **A persist's HTML.** Its `.json` can be its file as it is; its `.html` has
   to be rendered from its state, so the file is parsed. Rendered as a
   resource's is, from a template?
5. **The aliasing error.** Reaching an object by a second URL is a bug in the
   tree. Is a 500, logged with both URLs, the answer?
6. **Writing entries.** Once entries have no URLs, `PUT` and `DELETE` on a
   dict's entries and a list's tombstones go. Does every write then go
   through a resource's or persist's own handlers -- and `PATCH`, when it is
   designed?
7. **The PATCH language.** Decided later in the conversation.
