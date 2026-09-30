# mumulib for Python

Python utilities for ASGI request handling, traversing and updating objects,
producing responses, validating data shapes, and HTML templating.

The package includes `consumers`, `producers`, `server`, `shaped`, `mumutypes`,
and `tags`. Runtime dependencies are aiofiles and lxml.

## API

Each module's `__all__` is its public API, and what mumulib promises to keep
working; anything else in a module is its own.

- `mumulib.server`: `consumers_app(root)`, to publish an object, and
  `EventSource(queue)`, to stream events from it.
- `mumulib.consumers`: `consume`, `add_consumer` to walk into a new type, and
  `GetOnly` to publish an object read-only.
- `mumulib.producers`: `produce`, and `add_producer` to render a new type.
- `mumulib.shaped`: `is_shaped`, `make_shape`, `would_retain_shape`,
  `anything`, and the `ShapeMismatch` and `MalformedShape` exceptions.
- `mumulib.tags`: `Stan`, `Template`, `parse_template`, the slot functions,
  `produce_html`, and the tag groups -- `tags.every.<element>` for any element.
- `mumulib.mumutypes`: the ASGI and mumulib types those use, `SpecialResponse`
  and the HTTP responses, and `content_type_for`.

## URLs

`server.consumers_app(root)` publishes a Python object: a URL's path walks
into it, through dicts by key and lists and tuples by index, and its
extension alone decides what comes back.

- `/todos.json` is `root["todos"]` as JSON, and `/todos.html` the same object
  as HTML. The extension is the type, not part of the key. `.txt` is plain
  text, `.sse` server-sent events, and any other extension is the type
  `mimetypes` gives it.
- A URL without an extension is 404, and so is one whose extension has no
  type -- except one ending in a slash, which is its index as HTML: `/` is
  `/index.html`, and `/todos/` is `/todos/index.html`.
- `index`, last in a path, is the container's `"index"` entry if it has one,
  and else the container itself: `/todos/index.json` is the todos. `PUT` and
  `DELETE` there act on the `"index"` entry.
- The request's `Content-Type` says how its body is parsed (JSON, form or
  multipart), never what the response is; no response varies by request
  headers.

## Examples

`py/examples` holds servers built on mumulib, each a module with an ASGI `app`;
`make server` at the repository root runs one (`SERVER=<name>`, default
`hello`) on port 8001. The smallest, `hello.py`, publishes
`{"index": "Hello, world!"}`: `/`, `/index.txt` and `/index.json` are the one
string as HTML, text and JSON, and it is wrapped in `GetOnly`, read-only (see
Guards).

## Guards

`consumers_app` publishes an object for reading and writing alike, on purpose:
`PUT` writes an entry of a dict or a list (to a list's `last`, it appends),
and `DELETE` removes one. What can be changed is the object's to decide, and
mumulib does not guess. To publish an object to be read and nothing else,
wrap it in `GetOnly`:

```python
from mumulib.consumers import GetOnly
from mumulib.server import consumers_app

app = consumers_app(GetOnly(root))  # all of it, read-only
app = consumers_app({"notes": notes, "about": GetOnly(about)})
```

`GetOnly` is a consumer: it hands `GET` on to what it wraps, and answers
anything else with 405 Method Not Allowed and `Allow: GET`, at any depth below
it. It guards what is reached through it, not its own place in a parent: in
the second app, `PUT /about.json` is the unguarded dict's to answer, and would
replace the entry. Guard the parent, or the root, to keep that too.

A tuple, or a `types.MappingProxyType` -- the read-only view of a dict --
cannot be changed either, and refuses `PUT` and `DELETE` with 405; `POST` to a
`MappingProxyType`'s entry still reads it.

## Development

From the repository root:

```sh
uv sync --project py --extra dev --locked
uv run --directory py --extra dev --locked pytest --cov=mumulib --cov-branch
uv run --directory py --extra dev --locked ruff check
uv run --directory py --extra dev --locked ruff format --check
uv run --directory py --extra dev --locked pyright
```

The development extra includes pytest with pytest-cov, ruff, pyright and
lxml-stubs. The package is checked with pyright in strict mode and ships its
inline annotations with `py.typed`; the tests (`*_test.py`, next to the
modules) are checked at pyright's standard level.

Requires Python 3.12 or newer. Licensed under MIT; see LICENSE.

The companion TypeScript library and browser examples are documented in the
[repository README](https://github.com/fzzzy/mumulib#readme).
