# Vite

Status: design in progress. Started 2026-10-01.

How a page served by the Python server becomes a TypeScript app built by
Vite: proxied to Vite's dev server, with hot reloading, while developing,
and read from Vite's build when not.

## What the code does today

- The Python server and Vite run separately: `make run` starts Vite on 8000
  for `ts/examples` and a Python example on 8001. Neither serves the other's
  files. The TypeScript examples that needed Python data used Vite's
  `server.proxy` to reach it, the other way round.
- One prefix is already Python's own: given `changes=`, `consumers_app`
  serves `/mumulib/changes.sse` and `/mumulib/live.js` ahead of the tree.
- `consumers_app` answers HTTP and the lifespan protocol only, and asserts
  on any other scope: there is no websocket support.
- The Python package depends on no HTTP client.
- There is no development mode in mumulib.
- `tags.page(title, *content, stylesheets=, scripts=, live=)` builds a whole
  page in Stan.

## Decisions

### 1. Python proxies Vite while developing, hot reloading included

In development, the Python server passes Vite's URLs on to the Vite dev
server, its HMR websocket included, so a page served by Python reloads as
its TypeScript changes.

### 2. Vite's URLs are reserved

Python's own handlers own Vite's URLs -- its infrastructure, the built
assets, the HMR socket -- ahead of the tree, as `/mumulib/` already is. No
published object can be reached there. _(Which URLs: open question 1.)_

### 3. A Page switches between Vite and the build

A `Page` object serves a Vite page: in development, by asking Vite's dev
server for it, so it comes with Vite's client and hot reloading; otherwise,
by reading the files Vite built from disk. Which, is the Python server's
development mode. _(How the mode is chosen, and what a Page is: open
questions 2 and 3.)_

### 4. Single-file bundles first

A page is built to start with as one self-contained file. Code splitting
comes later, when duplication between pages hurts: the reserved assets
prefix is then served from Vite's build directory, its hashed file names
busting caches, and Python serves those files as bytes without knowing the
graph between them -- the HTML Vite built names them.

### 5. Past the HTML, the TypeScript world

Once the HTML is served, the page is Vite's and TypeScript's: its modules,
its `.sfc.html` imports, mumulib's `state` and `patslot`. It talks back to
the Python server over Ajax -- `GET`, `PUT` and `PATCH` against the
published tree -- and listens to the change stream.

## Open questions

1. **Which URLs are Vite's.** In development Vite serves not only its own
   prefixes (`/@vite/`, `/@id/`, `/@fs/`, `/node_modules/.vite/`) but every
   source module at its file path (`/src/index.ts`), which can collide with
   the tree. Proposed: Vite's `base` set to one prefix, say `/vite/`, so
   everything Vite serves -- sources, its client, the HMR socket, and the
   build's assets as `/vite/assets/` -- is under it, and Python reserves that
   one prefix.
2. **How the development mode is chosen.** An environment variable
   (`MUMULIB_DEV=1`, which `make run` sets), or an argument
   (`consumers_app(..., dev=True)`)?
3. **What a Page is.** Does a `Page` name a Vite HTML entry
   (`Page("editors/index.html")`) and serve that HTML as Vite made it -- or is
   that HTML a template whose slots Python fills from the resource's state,
   so that `template = Page(...)` works as a Stan template does? And how does
   it sit beside `tags.page()`, the Stan page skeleton?
