# Vite

Status: decided, not yet built. Started 2026-10-01.

How a page served by the Python server becomes a TypeScript app built by
Vite: proxied to Vite's dev server, with hot reloading, while developing,
and read from Vite's build in production.

## What the code does today

- The Python server and Vite run separately: `make run` starts Vite on 8000
  for `ts/examples` and a Python example on 8001. Neither serves the other's
  files.
- One prefix is already Python's own: given `changes=`, `consumers_app`
  serves `/mumulib/changes.sse` and `/mumulib/live.js` ahead of the tree.
- `consumers_app` answers HTTP and the lifespan protocol only, and asserts
  on any other scope: there is no websocket support.
- The Python package depends on no HTTP client or proxy.
- There is no development mode in mumulib.
- `tags.page(title, *content, stylesheets=, scripts=, live=)` builds a whole
  page in Stan.

## Decisions

### 1. Everything Vite serves is under one prefix, /vite/

Vite's `base` is `/vite/`, so everything it serves is under that one prefix:
in development its own client and helpers, every source module (which Vite
otherwise serves at its file path, `/src/index.ts`, where it could collide
with the tree) and the HMR websocket; in production the built chunks and
assets, `/vite/assets/...`.

### 2. In development, the browser talks to Vite's dev server directly

In development, a page's modules, Vite's client and the HMR websocket come
straight from the Vite dev server, not through Python. Python does not
proxy `/vite/`.

Three reasons, from the review of this doc against the others:

- Python reloads, with `--reload`, on every change to its code. A websocket
  through it would be cut each time, and would hold up each reload's
  graceful shutdown, as event streams did, until it was closed.
- Vite's URLs do not follow the Python server's: `/vite/@vite/client` has no
  extension, others carry queries, and a `.ts` is served as JavaScript.
- No ASGI proxy for HTTP and websockets is needed.

### 3. Vite's dev server has a port of its own, always the same

The Vite dev server runs on one fixed port, chosen to be unlikely to collide
with other projects' servers, and always that one: 5757.

### 4. Production by default, development by an environment variable

The Python server is in production mode unless an environment variable says
development: `MUMULIB_DEVELOPMENT=1`.

### 5. Bundled and code-split from the start

Pages are built with Vite's bundling and code splitting from the start. In
production Python serves `/vite/` from Vite's build directory, as bytes:
Python does not know the graph between the chunks, since the HTML Vite built
names them, and their hashed file names bust caches.

`/vite/` is handled before `split_path`, as a special case: its URLs are
Vite's, not the tree's, and are served as the files they name.

Built files are cached as persistence caches a file
([persistence.md](persistence.md), decision 9): an `ETag` from the file's
modification time and size.

### 6. A Page serves a Vite HTML entry as Vite made it

A `Page` names a Vite HTML entry -- `Page("editors/index.html")`, say -- and
serves that HTML exactly as Vite made it: in development by asking Vite's
dev server for it, so it comes with Vite's client and hot reloading; in
production by reading Vite's build of it from disk. Python does not fill or
change it.

`Page`, the class, and `tags.page()`, the Stan function, are different
things, and differ at least by case. `Page` goes in a new module, `static`, for
things served from disk that are not persists.

### 7. A Vite page is kept up to date by state sync, not live.js

live.js refetches the page and replaces its `data-live` elements with the
fresh copy's, which suits a page Python renders. A Vite page's HTML is the
entry as built, before any TypeScript has run, so a fresh copy of it would
put the template's markup back over what the page rendered. A Vite page
uses state sync ([state-sync.md](state-sync.md)) instead: its state paths
bound to URLs, fetched again when the change stream announces them.

### 8. Past the HTML, the TypeScript world

Once the HTML is served, the page is Vite's and TypeScript's: its modules,
its `.sfc.html` imports, mumulib's `state` and `patslot`. It talks back to
the Python server over Ajax -- `GET`, `PUT` and `PATCH`
([patch.md](patch.md), later) against the published tree -- and listens to
the change stream.

## Open questions

1. **How a Page gets its HTML in development.** Python asking Vite's dev
   server for it, a page linking Vite's client and entry itself, or a
   redirect to Vite: to be worked out when it is built, by what works.
