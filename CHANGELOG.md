# Changelog

mumulib ships as one version on npm (the TypeScript library) and PyPI (the
Python package). Breaking changes come first under each release.

## 2.0.0 — unreleased

### Breaking

- **Files are written off the event loop, and `Persist.write()` is a
  coroutine: `await persist.write()`.** `Resource.save()` and a `Persist`'s
  write ran the atomic write -- a temporary file, `fsync`, a rename -- on
  the loop, so every request and event stream waited on the disk. They run
  it in a thread now, as both `load()`s do their reads. A file's writes are
  made in turn, in the order asked for, so a slow one never lands after a
  later one; the JSON is made on the loop first, the state as it was then.
- **An error's message is no longer the exception's.** A 500, 400 or 413
  said `str(exc)` to the client -- an internal error's text, a parser's, a
  built page's directory -- and a 500 printed its traceback. The client is
  told a fixed sentence now, and the rest is logged: `logging`, to
  `mumulib.server`, `mumulib.static` and `mumulib.shaped`, in place of
  `print` and `traceback.print_exc`.
- **A write from another origin is refused, 403.** A `POST`, `PUT`,
  `PATCH` or `DELETE` a browser sends from another site's page -- by
  `Sec-Fetch-Site`, or else by an `Origin` whose host is not the request's
  `Host` -- is refused before its body is read. One with neither header,
  from `curl` or a script, is let through.
- **A multipart file is a `mumutypes.Upload`**, its `filename`,
  `content_type` and `data`, in place of its bytes alone. Multipart is read
  by python-multipart, a new dependency: the hand-written parser filed a
  part under its filename when that came before its name, and cut trailing
  dashes and newlines from every value, a file's bytes included.
- **`Resource.handle_HEAD` is gone.** A `HEAD` is answered as the `GET` it
  would have been, so a subclass's own could not be reached.

- **TypeScript: the state tree is not exported.** `state.state` is gone: a
  page reads the state as `onstate` gives it, and changes it with
  `set_state` and `set_path`, never by reaching in and mutating it.
- **TypeScript: `patslot.template(url)`, a promise, in place of
  `new patslot.Template(url)`.** The class is a type alone now. Resolving
  at once for now, it leaves room to fetch the page before it does.
- **TypeScript: `sync.watched` is private**, the comparison `bind` makes.

- **The Python package requires Python 3.14.** It had allowed 3.12, which
  CI ran -- the runner's own -- while development was on 3.14, and the two
  differ: 3.12's own table of types has no `.md` or `.ttf`, and its
  `types.GeneratorType` is not generic. CI now runs 3.14, as required.

- **A string is text, never HTML.** Strings and numbers answer `.txt` and
  `.json` alone, and are not found as `.html`, `.js`, `.css` or anything
  else: a string at `.html` was served as markup, so a visitor's note was a
  page they wrote. HTML of your own is `tags.Markup`, which now has an HTML
  producer; a resource's template, string or Stan, is HTML alone, and not
  found as `.json` or `.txt`. A listing links a string as `.txt`. An
  attribute is its value's text, whatever the page is asked for as, and one
  with no text is an error naming it.
- **A file is its own type alone.** An open file or a `Path` is served only
  at its extension on disk: `style.css` as `/style.html` is not found, and a
  file with no extension is not listed.

- **Python server: a URL's extension is its type, and nothing else.**
  `consumers_app` serves every response with the type its URL names:
  `.json`, `.html`, `.txt`, `.sse` (server-sent events), `.xml`, or any
  extension in Python's own table of types -- never the machine's, which
  Python's `mimetypes` module reads the first time it guesses, so that a
  type had depended on the machine and on what had run before. The request's own `Content-Type` still decides how
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
- **Nothing is served as its `str()`.** What has no producer for the URL's
  type is 404; it had been served as its Python repr -- a dict's
  `{'a': 1}` as HTML, an object's `<Thing at 0x…>`. Strings and numbers are
  text, at `.txt`, and JSON; `True` and `False` are JSON
  alone, and `None` is `null` in a JSON document but not found as a URL's own
  answer.
- **Deleting from a list leaves `None` in the element's place,** so no other
  element's URL changes: after `DELETE /todos/1.json`, `/todos/2.json` is the
  same element it was, where it used to be the next one along. The deleted
  element's URL is not found, and `null` in the list's JSON, until a `PUT`
  there brings it back.
- **A list's or tuple's element has one URL.** Its index is `0` or ASCII
  digits with no leading zero; a negative index, `01`, `+1`, `1_0` and the
  rest of what `int()` accepts are not found, where `/todos/-1.json` had been
  the last element.
- **Writes answer with what they did.** A `PUT` that creates an entry is
  201 Created, as it was; one that replaces an entry is 204 No Content, where
  it was 201. A `DELETE` is 204, where it was 200, and a `DELETE` of an entry
  that is not there, or of a list index that is not a number, is 404, where it
  was 200. A `PUT` to a list index that is not a number is 404, not 405. A
  405 from a tuple or a `MappingProxyType` names what it allows in `Allow`.
- **`EventSource` sends every event to every client.** It had one queue that
  its clients took turns reading from, so each event reached only one of
  them; and under a real server a stream ended after its first ping, since
  it took the request's own empty body for the client leaving. Now
  `EventSource()` is published itself, `put(item)` sends to every stream open
  then, and each stream has its own buffer, closed if its client falls
  `max_backlog` items behind. A stream ends when its client goes, with one
  `receive` for the whole stream, where each event left another waiting. It
  is found at `.sse` and nothing else.
- **Each event's data is the item's JSON,** encoded once in `put`, which
  raises `TypeError` for an item with no JSON form. Items had been sent as
  their `str()`: a dict as its Python repr, and a string with a newline in
  it broke the stream's framing.
- **A server stops at once with event streams open.** At lifespan startup,
  `consumers_app` chains a SIGINT and SIGTERM handler before the server's:
  it ends every open stream, then hands the signal on. uvicorn had waited
  for them for ever, "Waiting for connections to close".
- **In JSON, a value with no JSON form is an error,** a 500 naming its type,
  where it had quietly been `null`.
- **A function in the tree is called as `f(state)`,** not `f(f, state)`:
  the function itself was the first argument, which nothing used.
- **Python types are inline.** The `.pyi` stub files are gone; the package is
  annotated throughout, passes pyright in strict mode, and ships `py.typed`.
- **`tags.produce_html` writes a child that is neither text nor a tree as
  the HTML a producer makes of it** -- a dict as its listing -- and one with
  no HTML form is a `TypeError`.
- **`tags.produce_html` escapes text.** A string in a tree -- a filled slot,
  a child -- had been written out as it was, so a visitor's `<script>` in one
  ran; it is now escaped, and so is every attribute value, where only `"` had
  been. A string meant as HTML is wrapped in `tags.Markup`; a tree in a tree
  is markup as before, and `<script>` and `<style>` are left as they are.
  Text a template held as an entity, `&amp;`, comes out as one again.
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

- `HEAD` is answered wherever `GET` is: the same status and headers, from
  every consumer, a `Persist`, the Vite build and the ETag, and no body.
  `Allow` names `HEAD` wherever it names `GET`.
- **`mumulib/vite-plugin-sfc`**: a Vite plugin for single-file components as
  HTML. A `.sfc.html` holds a `<template>` and a TypeScript `<script>`, and
  importing it gives the custom element class. Components' scripts have source
  maps to their own lines, and coverage tools count them. Vite is an optional
  peer dependency.
- **`mumulib-sfc-check`** (and `checkSfc` from `mumulib/sfc-check`): type
  checking for `.sfc.html` scripts with the project's tsconfig, each error at
  its line and column in the component. TypeScript is an optional peer
  dependency.
  Given `--project`, it checks the files that tsconfig names as well, and an
  import of a `.sfc.html` in them resolves to the component's own class, with
  its own properties, rather than `sfc-client`'s wildcard declaration. With
  `--declarations` it writes each component's `<name>.sfc.html.d.ts` beside
  it, which tsc and editors read for the import with no setting needed.
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
- **Container listings**: a dict's, list's or tuple's slash, with no
  `"index"` entry, is a `<ul>` of links to its entries, as a directory's is --
  a container by its slash, a file by its own extension, anything else as
  `.html`, and only what could be fetched.
- **Directory listings**: a directory's slash, if it has no `index.html` of
  its own, is a `<ul>` of links named for its files, and its name as JSON is
  `{name: URL}`. Only what could be fetched is listed.
- **`consumers.RefuseIndex(obj)`**: a guard under which no container is
  handled whole, by any verb: no slash is found, no container is read,
  replaced or removed, and none is put where there was none. Only leaves come
  out or go in.
- **`add_consumer(type, consumer, container=...)`**: says whether a type's
  things are containers -- `True`, or a function of the thing -- which is
  what the one-URL-per-type rule and `RefuseIndex` go by.
- **`resource.Resource`**: a class to subclass, with children as `child_`
  attributes and `render(state)` calling `handle_<METHOD>`: `GET` renders its
  `template`, and anything else is 405 unless the subclass handles it. Every
  subclass is registered as it is defined. Handlers are `async def`. A parsed
  template is filled from `slot_<name>` methods and values, with
  `pattern(name, **slots)` for copies of its patterns. Its state is a dict
  given to the constructor: read-only as its own `.json`, `/profile.json`,
  the URL of its `.json` inside a plain dict or list, and what slots with no
  `slot_` are filled from. A state holds no resource or persist. Handlers are
  given the request. `see_other(url)` answers a form post with 303 See Other;
  `form(request)` reads one, with `text(name)` and `texts(name)`; and the
  `url` slot is the request's own URL, for a form that posts back.
  A resource answers every method
  at its own URL: a dict, list, tuple or `MappingProxyType` it is in hands it
  the request instead of replacing, removing or refusing it.
- **`consumers_app(root, changes=events)`**: every `POST`, `PUT`, `PATCH` or
  `DELETE` answered with success puts the URL of the container it changed
  on the `EventSource` `events` -- the nearest resource at or above what
  was written, with no extension, `/todos`, or `/` with none -- for pages
  listening to fetch it again.
- **A resource knows its URL**: `url`, learnt from the path the first
  request to reach it walked, `/todos` or `/todos/` for an index. One
  resource has one URL; reached by a second, it is a 500 naming both.
- **Persistent resources**: a resource's state is kept in a file named by
  its URL, `var/data/todos.json`, in the directory
  `consumers_app(root, data=...)` names. It is loaded when a request first
  reaches the resource -- an existing file wins over the constructor's
  state -- and written, atomically, by `await self.save()`, which a handler
  that changes the state calls.
- **`Persist(document)`**: a JSON document kept in its file, named by its
  URL. Its first request writes what it was made with there, if there is no
  file yet; `GET` at its URL streams the file; a `PUT` or `DELETE` below it
  sets the document and writes the file again, atomically; a `PUT` at its
  URL replaces it. JSON only, for now.
- **Caching by the file**: a `GET` of a persist or below it, or of a
  resource's own `.json` when that is its state, has an `ETag` from the file's
  modification time and size and `Cache-Control: no-cache`, and is 304 Not
  Modified to an `If-None-Match` naming it. What a resource computes is not
  cached.
- **Vite pages served by Python**: `static.Page("notes/index.html")` serves a
  Vite HTML entry as Vite made it, and `consumers_app(root, vite=...)` names
  the directory Vite builds into. In production, the default, the page and
  everything Vite built are read from there, under `/mumulib-vite/`, each
  with its file's `ETag`. With `MUMULIB_DEVELOPMENT=1`, a page is asked of Vite's dev
  server, always on 5757, and the browser loads its TypeScript, and hot
  reloading, from Vite directly.
- **XML** at `.xml`: a dict -- a resource's state, a persist's document, a
  plain dict -- each key an element named by it, each element with its
  `type`, and the root named by the document's class, as `application/xml`.
- **`sync.bind(path, url)`** (TypeScript): a path in the state bound to a
  resource or persist on mumulib's Python server, fetched as `<url>.json`
  and fetched again whenever the change stream announces it.
- **`mumulib/vite-plugin-origin`**: `originPlugin(origin)` names the dev
  server in full in each URL Vite writes into an HTML entry, so a page
  another server serves loads its modules from Vite; and refuses an entry
  that loads anything by a relative URL.
- **Short names for the template attributes in Stan**: `pat=` for
  `data-pat`, `slt=` for `data-slot` (`slot` is HTML's own), `attr=` for
  `data-attr`, as `"href=url"` or `{"href": "url"}`, and `live=` for
  `data-live`. An attribute that is `True` is written by its name, and one
  that is `False` or `None` is left out.
- **`tags.page(title, *content, stylesheets=, scripts=, live=)`**: a whole
  page, doctype, charset, viewport and all.
- **Live pages**: `consumers_app(root, changes=events)` serves the change
  stream at `/mumulib/changes.sse` and `/mumulib/live.js`. Each `data-live`
  element watches one URL, its value or the page's own; a change announcing
  it, matched exactly as a path, fetches the page again once and replaces the
  elements watching it alone. The Python package ships `live.js`.
- **Stan's `clone_pat` fills a pattern's own attribute slots**, its
  `data-attr`, as `Template.clone_pat` did; only those of its children had
  been.
- **`producers.add_json_form(type, to_json)`**: what a type's things are in
  JSON, wherever one is found; a `Resource` is its state.
- **`add_consumer(..., own_methods=True)`**: a type whose things answer every
  method at their URL themselves, as `Resource` is registered.
- **Python examples**, in `py/examples`, run with `make run` or `make server`
  (`SERVER=<name>`): `hello.py` publishes one string, and `files.py` a page
  from an open file with its assets from a directory, both read-only in
  `GetOnly`; `functions.py` a function answering `GET` and `POST`, in a
  `MappingProxyType`; and `resources.py` a to-do list of `Resource`s.
- **The editors example**: `py/examples/editors.py`, run with
  `make run SERVER=editors` and found at `/editors/`: a character, party and
  deploy editor built in Stan, with forms posted as forms and handled by each
  object's resource, and a small script that fetches the tables again on
  every change.
- **`patslot.fill(element, slots)`**: fills an element's slots from a dict, as
  `fill_body` does for the page. It existed but was never exported.
- **Python server hardening**: request bodies are limited in size (413 when
  over), dictionary keys and list indexes from URLs are validated, and errors
  come back as JSON.

### Fixed

- A body that does not parse -- malformed JSON or multipart, or not UTF-8
  -- is 400, not 413: the size limit's `ValueError` was caught with every
  other. An unknown `Content-Type` on a `POST`, `PUT`, `PATCH` or `DELETE`
  is 415, where it had been printed and the request handled as bodiless.
- A form post's values are decoded once: `parse_qsl` had decoded them, and
  they were decoded again, so a literal `%41` arrived as `A`.
- `tags`: `t.p["a", t.b["b"]]` is two children, as a list is; it had been one
  tuple. A page, an `<html>` tree, is written with its `<!doctype html>`.
- `consumers_app(..., changes=)` announces a form post answered with 303 See
  Other, as it does any 2xx.

- A dialog's method is called with every control's value: `<textarea>`,
  `<select>` and form-associated custom elements as well as `<input>`, which
  had been the only ones read. A name ending in `[]` is always a list
  (`FormArgs`, now exported). After a dialog was cancelled, its next submit
  was taken for a cancel too: its `returnValue` is now cleared each time it
  is shown. A `RenderFunc` may be async, as `do_dialog` already awaited it.
- A dialog's Cancel and Escape save nothing. Its forms' submit handler closed
  it without the button's value, so a `value="cancel"` button never reached
  `returnValue`, and Escape closed it with none: both saved the first form.
  Now a close with no submit, or with `cancel`, is a cancel, and a submit
  saves the form submitted unless `returnValue` names another.
- `data-attr` is read one way, in one place: `tags.attr_slots` in Python and
  its like in `patslot`. Only the first `=` divides a pair, and one without
  both a name and a slot is none. `fill_slots`, `append_slots` and
  `Template.clone_pat` each split it themselves and raised `ValueError` on
  a pair such as `a=b=c`, `patslot` filled that pair's slot as `b`, and
  `Resource` took `=x` for a slot named `x`.
- `patslot`: any slot or pattern name is found, `item.name` or `2 col` as
  much as `name`. Each was put bare into a selector, `[data-slot=item.name]`,
  which throws; names are compared as text now, with no selector built from
  them, and a dialog's `returnValue` too. And a fill stops at what is already
  filled: a pattern's slots and `data-attr` are its own, so filling a page's
  `name` no longer overwrites the `name` of every row already put in a list.
- `set_state`: a key set to `undefined` is deleted and counts as a change,
  so `onstate` hears of it; it had been deleted silently. A callback that
  throws no longer leaves every later change waiting on it forever. A field
  cleared to empty reaches the state; one only focused and left does not.
- `patslot`'s `Pattern` type allows an array of promises, such as
  `items.map(clone_pat)`, which it had always filled.

- **patslot works in Node.** It read `element.dataset`, which domino -- the DOM
  mumulib brings to Node -- does not have, so every fill threw there; it reads
  and writes the `data-*` attributes instead, the same in a browser. The Node
  bundles also supply the element classes the code checks with `instanceof`,
  as they already supplied `document`, and `state` schedules a re-run with a
  timeout where there is no `requestAnimationFrame`. `make check` now installs
  the packed package and uses it from Node, by `require` and by `import`.
- A function in the tree answers whatever kind it is. Only an async
  generator did; a plain function, a coroutine, a plain generator or a lambda
  was a 500. What a function returns is produced as though it had been
  published there.
- A method in the tree -- bound, built in, or a wrapper -- is 404. It had been
  served as its repr, which says where it lives in memory.
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
- `ts/pages` holds the Vite pages Python serves, with a config of their own,
  `ts/vite.pages.config.mts`; `make pages` builds them into `ts/build/pages`,
  and `make production` serves a Python example with them built. The Python
  example server is on port 5959.
