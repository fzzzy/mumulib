# Changelog

mumulib ships as one version on npm (the TypeScript library) and PyPI (the
Python package). Breaking changes come first under each release.

## 2.0.0 — unreleased

### Breaking

- **Python server: a URL's extension is its type, and nothing else.**
  `consumers_app` serves every response with the type its URL names:
  `.json`, `.html`, `.txt`, `.sse` (server-sent events), or any extension
  Python's `mimetypes` knows. The request's own `Content-Type` still decides how
  its body is parsed, but it no longer changes what comes back, so no response
  depends on request headers and none needs `Vary`.
  - The extension names a representation, not a key: `/motto.json` and
    `/motto.txt` are both `root["motto"]`. Keys no longer carry extensions. A
    URL without an extension is 404, and so is an extension with no type.
  - A container -- a dict, list, tuple or directory -- has one URL per type:
    its slash, `/todos/`, as HTML, for browsers, and its name,
    `/todos.json`, as any other type. `/todos.html` is 404, and so is
    `index.<ext>` spelled out, anywhere; the root, with no name of its own,
    has `/` alone.
  - The slash is the container's `"index"` entry if it has one, and else the
    container; the name is always the container, as data. `PUT` and `DELETE`
    on the slash write and remove the `"index"` entry, where they used to
    write a `""` key nothing could read, and on the name replace and remove
    the container. Anywhere else in a path, `index` is a key like any other.
  - A producer that starts the response itself, such as a file or an
    `EventSource`, gets the URL's type in place of its own.
- **Each Python module declares its public API in `__all__`,** and only
  those names are promised. `from mumulib.<module> import *` brings in those
  alone; the body parsers, the built-in consumers and producers, the limits,
  the element lists and the other helpers are the modules' own.
- **`tags.all` is now `tags.every`:** `tags.every.div` and so on. Under
  `import *`, `all` shadowed the builtin; there is no alias.
- **Python types are inline.** The `.pyi` stub files are gone; the package is
  annotated throughout, passes pyright in strict mode, and ships `py.typed`.
- **`tags.produce_html` refuses an attribute that is not text.** An attribute
  whose value produces bytes or a `SpecialResponse` raises `TypeError` naming
  the attribute.
- **`domino-shim.js` is gone.** It re-exported `dist/cjs/index.cjs`, which
  `require('mumulib')` already resolves to, and was never in the published
  package.
- **The npm package no longer includes the built examples.** `dist/` holds the
  library bundles and their types; the examples are served from source by
  `make run`.

### Added

- **`mumulib/vite-plugin-sfc`**: a Vite plugin for single-file components as
  HTML. A `.sfc.html` holds a `<template>` and a TypeScript `<script>`, and
  importing it gives the custom element class. Components' scripts have source
  maps to their own lines, and coverage tools count them. Vite is an optional
  peer dependency.
- **`mumulib-sfc-check`** (and `checkSfc` from `mumulib/sfc-check`): type
  checking for `.sfc.html` scripts with the project's tsconfig, each error at
  its line and column in the component. TypeScript is an optional peer
  dependency.
- **`mumulib/sfc-client`**: the declaration of what importing a `.sfc.html`
  gives, referenced as `vite/client` is.
- **`consumers.GetOnly(obj)`**: an object published read-only. A consumer
  that hands `GET` on to what it wraps and answers anything else with 405
  Method Not Allowed, at any depth below it. `consumers_app` publishes for
  reading and writing alike, on purpose; this is how to publish read-only,
  all of an object or part of one.
- **Directories, served**: a `pathlib.Path` to a directory is walked into, so
  `{"static": Path("static")}` serves its files at `/static/<name>`, the URL's
  extension part of the name. `..`, hidden names and symlinks that lead
  outside are not found, and a directory is read-only. A `Path` to a file is
  served as one, as file objects are.
- **Directory listings**: a directory's slash, if it has no `index.html` of
  its own, is a `<ul>` of links named for its files, and its name as JSON is
  `{name: URL}`. Only what could be fetched is listed.
- **`consumers.RefuseIndex(obj)`**: a guard under which an index is not found
  at any depth, nor any container reached through it; only leaves come out.
- **Python examples**, in `py/examples`, run with `make server`
  (`SERVER=<name>`): `hello.py` publishes one string, and `files.py` a page
  from an open file with its assets from a directory, both read-only in
  `GetOnly`.
- **`patslot.fill(element, slots)`**: fills an element's slots from a dict, as
  `fill_body` does for the page. It existed but was never exported.
- **Python server hardening**: request bodies are limited in size (413 when
  over), dictionary keys and list indexes from URLs are validated, and errors
  come back as JSON.

### Fixed

- **patslot works in Node.** It read `element.dataset`, which domino -- the DOM
  mumulib brings to Node -- does not have, so every fill threw there; it reads
  and writes the `data-*` attributes instead, the same in a browser. The Node
  bundles also supply the element classes the code checks with `instanceof`,
  as they already supplied `document`, and `state` schedules a re-run with a
  timeout where there is no `requestAnimationFrame`. `make check` now installs
  the packed package and uses it from Node, by `require` and by `import`.
- The Python server sent a producer's binary response as the text of its
  Python repr (`b'...'`) instead of the bytes.
- `PUT` to a list's `last` answers with the new element's own URL in
  `Location` -- `/todos/3.json` -- instead of `/todos/last.json/3`.
- Files of every type are served as their exact bytes. The file producer read
  all but `.ttf` fonts as text, so an image or any other binary file failed to
  decode, and text was re-encoded; nothing is decoded now. A file's type is
  the URL's, or else the one its name's extension gives.
- Multipart form bodies are decoded correctly.
- The README's `fill_slots` example passed a dict where the function takes one
  slot name and value.

### Development

- Built and served with Vite 8 instead of a hand-written esbuild script; the
  library bundles and their declarations are unchanged.
- TypeScript 6; ESLint and prettier; ruff, pyright (strict) and pytest for the
  Python.
- The repository is two directories: `ts/` for the TypeScript library, its
  package.json, configs, tests and examples, and `py/` (was `python/`) for the
  Python package. The Makefile at the root runs both.
- `make check` runs everything CI runs, including browser coverage from the
  Playwright tests; `make run`, `stop`, `tail` and `dev` serve the examples.
