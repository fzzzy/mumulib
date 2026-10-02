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
assets, `/vite/assets/...`. Python reserves `/vite/` for its own handlers,
ahead of the tree, as it does `/mumulib/`: no published object can be
reached there.

### 2. Python proxies Vite while developing, hot reloading included

In development, the Python server passes everything under `/vite/` on to the
Vite dev server, the HMR websocket included, so a page served by Python
reloads as its TypeScript changes.

This needs an ASGI proxy for HTTP and websockets, pulled in as a dependency
when it is built.

### 3. Development by default, production by an environment variable

The Python server is in development mode unless an environment variable
says production -- `MUMULIB_PRODUCTION=1`, say; the name is settled when it
is built.

### 4. Bundled and code-split from the start

Pages are built with Vite's bundling and code splitting from the start. In
production `/vite/` is served from Vite's build directory, as bytes: Python
does not know the graph between the chunks, since the HTML Vite built names
them, and their hashed file names bust caches.

### 5. A Page serves a Vite HTML entry as Vite made it

A `Page` names a Vite HTML entry -- `Page("editors/index.html")`, say -- and
serves that HTML exactly as Vite made it: in development by asking Vite's
dev server for it, so it comes with Vite's client and hot reloading; in
production by reading Vite's build of it from disk. Python does not fill or
change it.

`Page`, the class, and `tags.page()`, the Stan function, are different
things, and differ at least by case; `Page` may well go in a module of its
own, for things served from disk.

### 6. Past the HTML, the TypeScript world

Once the HTML is served, the page is Vite's and TypeScript's: its modules,
its `.sfc.html` imports, mumulib's `state` and `patslot`. It talks back to
the Python server over Ajax -- `GET`, `PUT` and `PATCH` against the
published tree -- and listens to the change stream.
