# Vite

Status: built. Started 2026-10-01.

How a page served by the Python server becomes a TypeScript app built by
Vite: its HTML served by Python, and its modules and hot reloading from
Vite's dev server directly, while developing; read from Vite's build in
production.

## What the code did before

- The Python server and Vite run separately: `make run` starts Vite on 8000
  for `ts/examples` and a Python example on 5959. Neither serves the other's
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

### 1. Everything Vite serves is under one prefix, /mumulib-vite/

Vite's `base` is `/mumulib-vite/`, so everything it serves is under that
one prefix: in development its own client and helpers, every source module
(which Vite
otherwise serves at its file path, `/src/index.ts`, where it could collide
with the tree) and the HMR websocket; in production the built chunks and
assets, `/mumulib-vite/assets/...`.

### 2. In development, the browser talks to Vite's dev server directly

In development, a page's modules, Vite's client and the HMR websocket come
straight from the Vite dev server, not through Python. Python does not
proxy `/mumulib-vite/`.

Three reasons, from the review of this doc against the others:

- Python reloads, with `--reload`, on every change to its code. A websocket
  through it would be cut each time, and would hold up each reload's
  graceful shutdown, as event streams did, until it was closed.
- Vite's URLs do not follow the Python server's:
  `/mumulib-vite/@vite/client` has no extension, others carry queries, and
  a `.ts` is served as JavaScript.
- No ASGI proxy for HTTP and websockets is needed.

### 3. Vite's dev server has a port of its own, always the same

The Vite dev server runs on one fixed port, chosen to be unlikely to collide
with other projects' servers, and always that one: 5757.

### 4. Production by default, development by an environment variable

The Python server is in production mode unless an environment variable says
development: `MUMULIB_DEVELOPMENT=1`.

### 5. Bundled and code-split from the start

Pages are built with Vite's bundling and code splitting from the start. In
production Python serves `/mumulib-vite/` from Vite's build directory, as bytes:
Python does not know the graph between the chunks, since the HTML Vite built
names them, and their hashed file names bust caches.

`/mumulib-vite/` is handled before `split_path`, as a special case: its URLs are
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
its `.sfc.html` imports, mumulib's `state`, `patslot` and `sync`. It talks
back to the Python server over Ajax -- `GET`, `PUT` and `DELETE`, and
`PATCH` when [patch.md](patch.md) is built, against the published tree --
and listens to the change stream, through `sync.bind`.

### 9. In development, Python serves the HTML, naming Vite's server in it

A `Page` is served by Python in development too, from Python's origin: it
asks the Vite dev server for the entry and serves what it gets. The URLs
Vite writes into it -- its client, the entry's modules and stylesheets --
name the Vite dev server in full, `http://127.0.0.1:5757/mumulib-vite/...`, so the
browser fetches them, and opens the HMR websocket, from Vite directly.

Tried with Vite 8.3.1, a page served from another origin:

- A full-URL `base`, or `server.origin`, does not do it: in development Vite
  writes the HTML's URLs root-relative, `/mumulib-vite/src/main.ts`, whatever
  either says, and they would be fetched from Python.
- A plugin of Vite's own, run only by the dev server, does: a
  `transformIndexHtml` hook, after Vite's, puts the origin in front of the
  base wherever it appears quoted (decision 10). It ships with the library,
  `mumulib/vite-plugin-origin`, and also sets `server.origin`, for the asset
  URLs Vite writes into modules and CSS.
- Past the HTML, nothing else needs it. Imports inside the modules are
  root-relative and resolve against the module's own URL, on Vite; Vite's
  client opens its websocket to the host it was loaded from; and Vite
  answers CORS for a page on `127.0.0.1`'s other ports by default.
- An edit to a module that does not accept hot updates reloads the page,
  from Python's origin.

### 10. The base is distinctive, so it is found by its text

The base is `/mumulib-vite/`, not `/vite/`: a prefix nothing else on a page,
or in the tree, would have. The origin plugin then needs no pattern for an
HTML attribute: it replaces the quoted base, `"/mumulib-vite/`, wherever it
appears, with the dev server's origin in front.

### 11. An entry's URLs are root-relative, and a relative one is an error

An entry loads what it loads by a root-relative URL,
`<script src="/notes/main.ts">`, which Vite writes under the base. Vite
leaves a relative one, `./main.ts`, as it is, and it would resolve against
Python's page; so the origin plugin refuses an entry with a relative `src`,
or a relative `href` on a `<link>`, naming the entry and the URL, in
development and in a build alike. A link to another page, `<a href>`, is
the page's own, and is left alone.

Refusing is a trial: to see whether, and when, root-relative URLs become
annoying to write. The alternative, if they do, is to rewrite a relative URL
to root-relative, resolved against the entry's own path, before Vite's
transform, with a check after it that every URL a page loads is under the
base or has a scheme of its own, so a mistake stays loud.

### 12. An entry is always an index.html, at any depth

Every page Vite builds for Python is a directory's `index.html`, its slash:
`pages/notes/index.html`, or deeper, `pages/notes/settings/index.html`, which
is `Page("notes/settings/index.html")`. Every one under the pages' root is an
entry, so development and production serve the same pages, and every one is
checked for relative URLs in the build too. Components, `.sfc.html`, are
not pages and are not checked: loading one that is wrong fails visibly.

## As built

- `consumers_app(root, vite=...)` names the directory Vite builds the pages
  into, `ts/build/pages` in this repository, and keeps `/mumulib-vite/` for
  itself only when it is given one. A `Page` is in `mumulib.static`.
- In development a `Page` asks Vite's dev server with `urllib`, in a thread;
  an async client is a TODO. If the dev server does not answer, it is a 502.
- The pages' Vite project is `ts/vite.pages.config.mts`: its root
  `ts/pages`, every `index.html` under it an entry, and a dependency cache
  of its own, `node_modules/.vite-pages`, so it and the examples' dev server
  do not re-optimize each other's dependencies.
- `make run` starts the pages' dev server on 5757 and the Python example
  with `MUMULIB_DEVELOPMENT=1`; `make pages` builds them; `make production`
  serves a Python example with them built, and no Vite.
- A built file's content type is mumulib's own table's, or Python's built-in
  one: never the machine's.
- `py/examples/notes.py` and `ts/pages/notes` are the example: a Vite page
  beside a `Persist`, bound with `sync.bind`.
