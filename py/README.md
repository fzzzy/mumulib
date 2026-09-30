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
- `mumulib.consumers`: `consume`, `add_consumer` to walk into a new type --
  `container=True`, or a function of the thing, if it is a container -- and
  the guards `GetOnly`, to publish an object read-only, and `RefuseIndex`, to
  publish it with no index.
- `mumulib.producers`: `produce`, and `add_producer` to render a new type.
- `mumulib.resource`: `Resource`, a class to subclass for an object with
  children of its own and handlers for each method.
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

- `/motto.json` is `root["motto"]` as JSON, and `/motto.txt` the same value as
  text. The extension is the type, not part of the key. `.txt` is plain text,
  `.sse` server-sent events, and any other extension is the type `mimetypes`
  gives it. A URL without an extension is 404, and so is one whose extension
  has no type.
- A container -- a dict, list, tuple or directory -- has one URL per type:
  its slash, `/todos/`, as HTML, which is for people in browsers, and its
  name, `/todos.json`, as anything else, as a leaf's is. `/todos.html` is
  404, and so is `index.<ext>` spelled out, anywhere.
- The slash is the container's `"index"` entry if it has one, and else a
  `<ul>` of links to what is in it, as a directory's is: a container by its
  slash, a file by its own extension, anything else as `.html`, and only what
  could be fetched. Its name is always the container itself, as data. `PUT`
  and `DELETE` on the slash write and remove the `"index"` entry, and on the
  name replace and remove the container.
- The root is the one exception: it has no name in a parent, so `/` is its
  only URL, and it cannot be replaced whole. Its data is its entries'.
- A string is its own content as any type, and a number its digits; `True`
  and `False` are JSON alone. What has no producer for the URL's type is 404,
  never its `str()`; and in JSON, a value with no JSON form is an error, not a
  quiet `null`. A `None` is `null` in a JSON document, but is not found as a
  URL's own answer: a consumer's `None` means not found.
- The request's `Content-Type` says how its body is parsed (JSON, form or
  multipart), never what the response is; no response varies by request
  headers.

## Examples

`py/examples` holds servers built on mumulib, each a module with an ASGI `app`;
`make server` at the repository root runs one (`SERVER=<name>`, default
`hello`) on port 8001. The smallest, `hello.py`, publishes
`{"index": "Hello, world!"}`: `/`, `/index.txt` and `/index.json` are the one
string as HTML, text and JSON, and it is wrapped in `GetOnly`, read-only (see
Guards). `files.py` (`SERVER=files`) serves a page from an open file and its
stylesheet, text and image from a directory, and `functions.py`
(`SERVER=functions`) a function that answers `GET` and `POST`.

## Resources

A subclass of `mumulib.resource.Resource` names its children as attributes,
`child_<name>`, and answers a request that ends at it with `render(state)`,
which calls `handle_<METHOD>(state)`:

```python
class Profile(Resource):
    template = "<h1>Ada</h1>"
    child_name = "Ada"


class Site(Resource):
    child_index = "<h1>Home</h1>"
    child_profile = Profile()


app = consumers_app(Site())  # /, /profile.html, /profile/name.txt
```

`handle_GET` renders `template`; every other method is 405, with `Allow`
naming `GET` and whatever the subclass handles. What a handler returns is
produced as though it had been published there, of the URL's type: `state`
says which, in `"content_type"` and `"extension"`. A resource is not a
container -- it is named as a file, `/profile.html` or `/profile.json` -- and
its children can be anything publishable. Each subclass is registered as it
is defined, by `__init_subclass__`.

A resource's handlers answer when the walk ends at it through another
resource, or at the root; a plain dict answers `PUT` and `DELETE` for its own
entries itself, replacing or removing the resource.

## Files and directories

A file object -- what `open()` returns -- is served as its bytes, read afresh
on each request. A `pathlib.Path` is too, and a `Path` to a directory is walked
into: `{"static": Path("static")}` serves `static/style.css` at
`/static/style.css`. The URL's extension is put back on the last segment as
part of the file's name, and is the type it is served as, so a file needs an
extension to be served.

The slash, `/static/`, is the directory's `index.html` if it has one, and
else a `<ul>` of links, each named for its file. Its name, `/static.json`, is
`{name: URL}`, a subdirectory's URL its own listing, `/static/sub.json`. Only
what could be fetched is listed, and `RefuseIndex` is how to have no listing
(see Guards).

Only what is in the directory is found: `..`, hidden names such as `.git` and
`.env`, and symlinks that lead outside are not. A directory is never written;
anything but `GET` is 405.

## Functions

A function the URL ends at is its own producer: it is called as `f(state)`,
where `state` holds the request -- `"method"`, `"url"`, `"extension"`,
`"content_type"`, and `"parsed_body"` for a request with a body. Any kind of
function will do. What an async generator or a generator yields is the
response; what a coroutine or a plain function returns is produced as though
it had been published there, so a dict is JSON at `.json`. Either way it is
the URL's type.

```python
async def greet(state):
    yield "Hello, world!"


app = consumers_app(MappingProxyType({"greet": greet}))
```

It is called for `GET` and for `POST`, with the body. It is a leaf: nothing is
below it, and it has no slash. `PUT` and `DELETE` at its name are its
parent's to answer -- a plain dict would replace or remove the function -- so
publish it in a `MappingProxyType`, which refuses both.

A method -- bound, built in, or a wrapper such as `"abc".__str__` -- is not a
function to call for a request, and is not found.

## Guards

`consumers_app` publishes an object for reading and writing alike, on purpose:
`PUT` writes an entry of a dict or a list (to a list's `last`, it appends),
and `DELETE` removes one. A `PUT` that creates is 201 Created, one that
replaces and a `DELETE` are 204 No Content, and a `DELETE` of nothing is 404.
A list's elements keep their URLs: `DELETE /todos/1.json` leaves `None` in its
place, not found and `null` in the list's JSON, and `/todos/2.json` is still
the same element. A `PUT` to `/todos/1.json` brings it back, and `last` never
reuses it. How long a list or a dict may grow is the application's to decide.
What can be changed is the object's to decide, and
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

A container is served whole by default: at its slash, its `"index"` entry or
itself, and at its name, itself -- a dict as JSON, a directory's listing.
`RefuseIndex` is how to have neither:

```python
app = consumers_app({"static": RefuseIndex(Path("static"))})
```

No slash is found below it, and no container reached through it -- nor the
wrapped object itself, if it is one. Nor is a container written whole there:
not replaced, not removed, and not put where there was none. Only what is not
a container comes out, or goes in: a directory's files, a dict's leaves. The
two guards nest:
`GetOnly(RefuseIndex(root))`.

What counts as a container is what was registered as one:
`add_consumer(type, consumer, container=True)` for a type of your own, or a
function of the thing for a type only some of whose things are, as a `Path` is
one if it is a directory.

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
