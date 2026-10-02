# Persistence

Status: built, but for a persist's `.html` (a TODO) and `PATCH`
([patch.md](patch.md), lower priority). Started 2026-10-01.

How state outlives the process: graduating from objects in RAM to JSON
documents on disk.

## What the code did before

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

### 3. Two kinds of node with identity, both persistent: Resource and Persist

Both keep their state in a JSON file; they differ in how they write it after
a change, and in how they answer a `GET`:

- A **Resource** has behaviour of its own and answers by computing: it keeps
  `self.state` in memory and renders from it. It is for what is calculated
  dynamically.
- A **Persist** is plain durable data, and answers a `GET` with its file as it
  is, streamed from disk (decision 10).

### 3a. How a resource is persisted

- **Written by `save()`.** `Resource` has a `save()` method that serializes
  `self.state` to the resource's file, as its `.json` answers. A handler
  that changes `self.state` -- `handle_POST`, `handle_PUT`, `handle_PATCH`,
  `handle_DELETE` -- is required to call it, `await self.save()`, for the
  change to be kept. One that does not keeps its change in memory and not on
  disk: that is the subclass's own mistake to make.
- The base class's handlers stay as they are: a mutating method a subclass
  does not handle is refused with 405.
- **Loaded lazily, on its first request.** A resource does not know where it is
  stored until a request first reaches it -- its file follows from its URL,
  as a persist's does (decision 4) -- and then `self.state` is loaded from
  its file.
- **No file yet: the constructor's state.** If there is no file -- a first run
  -- the state is the one the constructor was given, `GET`s answer from it in
  memory, and the first change creates the file.
- **A resource is a container**, as a persist is: a write to it announces its
  own URL (decision 8), and its file gives it its `ETag` (decision 9).
- **Its state is plain JSON**: it holds no resource or persist
  ([state-sync.md](state-sync.md), decision 14). Saving one that does is a
  `TypeError` naming where. A container in a container is
  [nested-persistence.md](nested-persistence.md), tentative.
- **Where.** Every file is under one data directory, `./var/data` unless
  `consumers_app(..., data=...)` names another -- as tests do, a temporary
  directory of their own -- at the path its URL gives it:
  `/editors/characters/c1` is `./var/data/editors/characters/c1.json`.

### 3b. How a persist is persisted

A persist's file is its state, so there is nothing to ask for after a change:
its mutation implementation writes the file itself. A sub-URL `PUT` or
`DELETE` changes one value in the loaded document, and the document is
written (to a temporary file, then renamed over the old). A `PUT` at the
persist's own URL replaces the document whole. A `PATCH`, changing several
values at once, is [patch.md](patch.md)'s. Its document, like a resource's
state, holds no resource or persist.

A persist can be given its content in Python, as a resource is given its
state. Since it answers a `GET` from its file, it needs its file to exist:
so on its first request -- when it learns its URL, lazily (decision 4) -- a
persist with no file on disk writes the content it was given to its file
then and there, and serves the file from then on. If the file is already
there, a later run, the file is the truth and the content given in Python
is not used, as a resource's file wins over its constructor's state.

Persist starts with JSON alone: its `.json` is its file as it is. Its `.xml`,
when its document is a dict, is the document as XML ([xml.md](xml.md)).
Anything that does not fit that is marked TODO for now.

- TODO: a persist's `.html`, which has to be rendered from its state, so its
  file parsed -- presumably from a template, as a resource's is.

### 4. A persist or resource learns its URL on first access, and loads then

A persist's or resource's URL -- and so its file -- is not its own: it is
where it sits in the tree, which is the path walked to reach it. So it is
bound when traversal first delivers a request to it, carrying the path
walked, and its state is
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
  scalar inside them has its URL -- a scalar's at `.txt` and `.json` alone,
  never `.html`, where a visitor's text would be markup;
- a resource's state is read at its own `.json`, `/editors/characters/c1.json`
  (it was a child, `state.json`, until state sync made a resource's `.json`
  its state: [state-sync.md](state-sync.md), part one);
- `PUT` and `DELETE` on an entry work as now, a list's tombstones and `last`
  included;
- a `Path`, a file or a directory, is served as it is now -- a file at its
  extension on disk alone.

### 7. Writing: whole-container commits, PATCH for several fields

- A sub-URL's **container** is the nearest resource or persist at or above
  it.
- `PATCH` on a container, to change several of its fields in one atomic
  write, is designed in [patch.md](patch.md), and built last.
- `PUT` on a sub-URL stays, for the convenient one-field change.
- Either way, a write is one atomic commit of the whole container: its file
  rewritten as a whole (to a temporary file, then renamed over the old). A
  patch is a smaller request, not a smaller write.

### 8. Liveness: a write announces its container

A write announces its **container's** URL, the nearest resource or persist
at or above what was written, not the sub-URL: `PUT
/characters/c1/name.json`, `c1` being a persist, announces `/characters/c1`.
So an element watching `/characters/c1` hears every change to it, wherever
in it the change was made. A write to a resource, answered by its own
handler, announces the resource.

A write with neither above it announces `/`: the root is the container of
everything not inside a resource or a persist.

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
- State in memory that is in no file -- plain dicts and lists outside any
  persist or resource -- has no `ETag`.
- A resource's `.json` and `.xml`, when they are its state -- `Resource`'s
  own `handle_GET` -- are its file, and have its `ETag` as a persist does;
  so do a persist's. A resource's computed HTML is not cached at all
  by default -- no `ETag` -- since it can depend on more than its own file
  (the editors index shows every character). Each resource subclass decides
  its own caching, setting its own cache headers; that needs a way for a
  handler to set its response's headers, which handlers, returning a value,
  do not have today.

### 10. Serving a file: streamed, zero-copy when a server offers it

A persist's file is streamed, as mumulib serves files now. No ASGI server
supports the zero-copy extension, `http.response.zerocopysend`, so it is
used only where one does -- or `http.response.pathsend`, the simpler one in
which the app names the file -- when a server offers either.

## Caveat: reading another object's memory

An object loads its file when a request first reaches it. One that reads
another object's state directly, from memory -- the editors index rendering
every character's row from `characters[...]` -- sees that object's
constructor state until a request has reached it itself. After a restart,
the index is out of date until each object it shows has been asked for.

Accepted for now. The direction for fixing it: a resource does not reach
into another resource's memory, but asks for its state over HTTP, by its
URL, as any client would -- which reaches it, so it is loaded, and lets the
objects live in different processes, or on different machines, sharded.
