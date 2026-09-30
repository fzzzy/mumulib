mumulib
=====

Two libraries, released together as one version:

- [`ts/`](ts/README.md), the TypeScript library on npm: `state` for app state,
  `patslot` for HTML templates filled from data, `dialog` for forms in
  `<dialog>`s, and `mumulib/vite-plugin-sfc` for single-file components.
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
  Node ESM and CommonJS bundles, and the type declarations.
- `make run` starts both example servers in the background and returns:
  Vite on port 8000, serving `ts/examples` from source, and a Python example
  from `py/examples` on port 8001 -- `hello` unless `SERVER` names another, as
  in `make run SERVER=resources`. Each reloads as its code changes. `make tail`
  follows their logs, `var/log/vite.log` and `var/log/server.log`; `make stop`
  stops whatever holds either port; and `make dev` is run and tail together.
- `make server` runs the Python example alone, in the foreground.

Each half keeps its own dependencies: `ts/package-lock.json`, installed with
`npm ci`, and `py/uv.lock`, in `py/.venv`. Run `uv lock --project py` after
intentionally editing the Python dependencies.
