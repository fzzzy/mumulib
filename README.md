mumulib
=====

Two libraries, released together as one version:

- [`ts/`](ts/README.md), the TypeScript library on npm: components, each one
  `.sfc.html` file of an HTML template and the class that fills it, and the
  app, a page whose own HTML is its template and whose class keeps the state.
  Its README begins with four small examples -- a component, an app, binding
  and a dialog -- and each part, importable alone, has its own page in
  [`ts/docs/`](ts/docs): `mumu`, `app`, `state`, `patslot`, `dialog`,
  `events`, `sync`, and the Vite plugins.
- [`py/`](py/README.md), the Python package on PyPI: an ASGI server that
  publishes a Python object at URLs, with shape checking and server-side HTML
  templates in the same `data-slot` markup `patslot` fills.

[CHANGELOG.md](CHANGELOG.md) says what changed in each release.

Development
=====

It needs [uv](https://docs.astral.sh/uv/) for the Python and Node for the
TypeScript; everything runs from here, through the Makefile.

- `make check` runs everything CI runs: ESLint and prettier, `tsc` and the
  `.sfc.html` type checker over the TypeScript, ruff and pyright (strict) over
  the Python, the build, the Python tests with branch coverage (the floor is in
  `py/pyproject.toml`), and the Playwright tests in Chromium and WebKit, with
  the coverage of `ts/src/` they reach.
- `make fix` applies the linters' fixes and formatting.
- `make build` writes the npm package to `ts/dist`: the browser bundle, the
  Node ESM and CommonJS bundles, and the type declarations; and builds the
  pages Python serves, `ts/pages`, into `ts/build/pages`, as `make pages`
  does alone.
- `make run` starts the example servers in the background and returns: Vite
  on port 8000, serving `ts/examples` from source; a Python example from
  `py/examples` on port 5959 -- `hello` unless `SERVER` names another, as in
  `make run SERVER=notes` -- in development, `MUMULIB_DEVELOPMENT=1`; and the
  Vite dev server of the pages it serves, on 5757. Each reloads as its code
  changes. `make tail` follows their logs, in `var/log`; `make stop` stops
  whatever holds any of the ports; and `make dev` is run and tail together.
- `make server` runs the Python example alone, in the foreground, and
  `make production` runs it in production, its pages built, with no Vite.
- `make check` and `make run` write each example component's declarations,
  `<name>.sfc.html.d.ts`, so tsc and editors know its class. They are made
  from the components, and git ignores them.

Each half keeps its own dependencies: `ts/package-lock.json`, installed with
`npm ci`, and `py/uv.lock`, in `py/.venv`. Run `uv lock --project py` after
intentionally editing the Python dependencies.
