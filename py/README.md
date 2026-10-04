# mumulib for Python

Python utilities for ASGI request handling, traversing and updating objects,
producing responses, validating data shapes, and HTML templating.

The package includes `consumers`, `producers`, `server`, `shaped`, `mumutypes`,
and `tags`. Runtime dependencies are aiofiles and lxml.

## API

Each module's `__all__` is its public API, and what mumulib promises to keep
working; anything else in a module is its own.

- `mumulib.server`: `consumers_app(root)`, to publish an object, and
  `EventSource()`, server-sent events to every client listening.
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
  `produce_html`, `Markup`, and the tag groups -- `tags.every.<element>` for
  any element. Written out, a tree's text is escaped and its attributes too,
  so a slot filled with what a visitor sent shows it rather than running
  it. A tree in a tree is markup, and so is `Markup("<i>mine</i>")`, for HTML
  you wrote yourself; `<script>` and `<style>` are written as they are.
  The template attributes have short names in Stan: `t.tr(pat="row")` is a
  pattern, `data-pat`; `t.td(slt="name")` a slot, `data-slot` -- `slot` is
  HTML's own, for shadow DOM; and `t.a(attr="href=url")`, or
  `attr={"href": "url"}`, fills attributes from slots, `data-attr`; and
  `live=True` marks an element live.js keeps up to date. An attribute that is
  `True` is written by its name, `required`, and one that is `False` or
  `None` is left out, as boolean attributes must be. `page(title, *content,
stylesheets=, scripts=, live=)` is a whole page: the doctype, a UTF-8
  charset and a viewport, the title, the stylesheets and scripts, and the
  content as its body.
- `mumulib.mumutypes`: the ASGI and mumulib types those use, `SpecialResponse`
  and the HTTP responses, and `content_type_for`.

## URLs

`server.consumers_app(root)` publishes a Python object: a URL's path walks
into it, through dicts by key and lists and tuples by index, and its
extension alone decides what comes back.

- `/motto.json` is `root["motto"]` as JSON, and `/motto.txt` the same value as
  text. The extension is the type, not part of the key. `.txt` is plain text,
  `.sse` server-sent events, `.xml` `application/xml`, and any other extension
  is the type Python's own table gives it -- never the machine's
  `/etc/mime.types`, so a type is the same on every machine, every time. A
  URL without an extension is 404, and so is one whose extension has no type.
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
- A list's or tuple's element has one URL: its index is `0`, or ASCII digits
  with no leading zero. `-1`, `01` and `+1` are not found, though Python's
  `int()` would take them for some element.
- The root is the one exception: it has no name in a parent, so `/` is its
  only URL, and it cannot be replaced whole. Its data is its entries'.
- A string is text: its own content at `.txt`, and a JSON string at `.json`,
  and a number its digits at both. As anything else -- `.html`, `.js`,
  `.css`, `.xml` -- it is not found, since a string, a visitor's included,
  served as markup or code is anyone's page. HTML of your own is a
  `tags.Markup`, served at `.html` alone; a resource's template is its
  markup. `True` and `False` are JSON alone. What has no producer for the URL's type is 404,
  never its `str()`; and in JSON, a value with no JSON form is an error, not a
  quiet `null`. A `None` is `null` in a JSON document, but is not found as a
  URL's own answer: a consumer's `None` means not found.
- An error tells the client its status and no more: what went wrong -- an
  exception and its traceback, a body that would not parse -- is logged,
  to the `mumulib.server` logger and its like, and never sent. A 500 is
  logged at `ERROR`, a 400 or 413 at `INFO`. With no logging configured,
  Python's own last resort still prints an `ERROR` and its traceback.
- A write -- anything but `GET`, `HEAD` or `OPTIONS` -- that a browser sends
  from another origin is 403: a page elsewhere cannot post a form here with
  a visitor's cookies. `Sec-Fetch-Site` decides where a browser sends it;
  else `Origin`, whose host must be the request's `Host`. A request with
  neither, from `curl` or a script, is no browser's and is let through.
- `HEAD` is answered wherever `GET` is, as `GET`: the same status and
  headers, and no body.
- The request's `Content-Type` says how its body is parsed (JSON, form or
  multipart), never what the response is; no response varies by request
  headers.

## Examples

`py/examples` holds servers built on mumulib, each a module with an ASGI `app`;
`make run` at the repository root runs one (`SERVER=<name>`, default
`hello`) on port 5959, in the background, and `make server` in the
foreground. The smallest, `hello.py`, publishes
`{"index": Markup("Hello, world!")}`: `/` is that HTML, and the only URL
there is, since the root has no name of its own. It is wrapped in `GetOnly`,
read-only (see Guards). `files.py` (`SERVER=files`) serves a page from an open file and its
stylesheet, text and image from a directory, `functions.py`
(`SERVER=functions`) a function that answers `GET` and `POST`, and
`resources.py` (`SERVER=resources`) a to-do list of resources: a list that
takes `POST`, and items in it that answer their own `PUT` and cannot be
deleted, on a page that listens to `changes` and shows everyone's at once;
and `editors.py` (`SERVER=editors`, then `/editors/`) a character, party and
deploy editor: every page built in Stan, each object a `Resource` whose state
fills its edit form, each form a plain post its resource checks and answers
with 303 See Other, and one small script that fetches the tables again when
anything changes. `notes.py` (`SERVER=notes`) is a Vite page, `ts/pages/notes`,
served by Python beside a `Persist` it binds with the TypeScript library's
`sync.bind`, so every page open shows everyone's notes; `make production
SERVER=notes` serves it built.

## Resources

A subclass of `mumulib.resource.Resource` names its children as attributes,
`child_<name>`, and answers a request that ends at it with `render(request)`,
which calls `handle_<METHOD>(request)`. Its state is a dict, given to the
constructor:

```python
class Profile(Resource):
    template = "<h1>Ada</h1>"
    child_name = "Ada"


class Site(Resource):
    child_index = Markup("<h1>Home</h1>")
    child_profile = Profile({"name": "Ada"})


app = consumers_app(Site())  # /, /profile.html, /profile.json, /profile/name.txt
```

`handle_GET` renders `template`; every other method is 405, with `Allow` naming `GET`, `HEAD` and whatever the subclass handles.
Handlers are `async def`, and `render` awaits them. What a handler returns is
produced as though it had been published there, of the URL's type: the
request says which, in `"content_type"` and `"extension"`. The base
`handle_GET` answers `.html` with the template and `.json` with the state,
`/profile.json`, read-only -- only the resource's handlers change it -- and
anything else is not found. A plain dict or list is JSON nested as it is,
at any depth, and only a resource or a persist in it is written as the URL
of its own: `/people.json` is `{"ada": "/people/ada.json"}`, for a client
to fetch, or bind. A resource's state holds no resource or
persist, and a persist's document none either: a container in a container
is not allowed, yet, and is a `TypeError` naming where it is. A form is read with `self.form(request)`: `form.text("name")`, stripped, and
`form.texts("tags")`, every value sent as `tags[]` or `tags`. A form with
`attr="action=url"` posts back to its own page, the `url` slot every
resource has, and its post is answered with `self.see_other(url)`, 303 See
Other, as `self.refuse()` answers with 405. A resource is not a
container -- it is named as a file, `/profile.html` or `/profile.json` -- and
its children can be anything publishable. Each subclass is registered as it
is defined, by `__init_subclass__`.

A resource answers every method at its own URL, wherever it is published:
in a dict, a list, a tuple or a `MappingProxyType`, the container hands it
the request rather than writing, deleting or refusing it. `PUT
/profile.json` is the resource's `handle_PUT`, not a replacement for it, and
`DELETE` its `handle_DELETE`; one it does not handle is 405. Guards above it
still narrow: under `GetOnly` it is only read. A type of your own can answer
for itself the same way, registered with
`add_consumer(type, consumer, own_methods=True)`.

### Persistence

A resource keeps its state in a file named by its URL, in the app's data
directory: `var/data` beside where the server runs, or the one
`consumers_app(root, data=...)` names. `/editors/characters/c1` keeps
`var/data/editors/characters/c1.json`, and an index, `/editors/`,
`var/data/editors/index.json`. The root is a dict, as it is anywhere else: a
resource at `/` is its `"index"` entry, keeping `var/data/index.json`.
Don't publish a resource as the root, with another as its `child_index`:
the index would be `/` as well, and share its file. The process is one, on
one thread, so a resource's state in memory is the state.

The first request to reach a resource loads its file, if there is one, as
`self.state` -- an existing file wins over the state it was made with.
With none, the constructor's state is kept, and answered from memory. A
handler that changes the state saves it:

```python
class Character(Resource):
    async def handle_POST(self, request):
        self.state["name"] = self.form(request).text("name")
        await self.save()
        self.see_other("/editors/")
```

`save()` writes the state as `/<resource>.json` answers it, atomically: to a
temporary file beside it, then renamed into place, so the file is the state
before or the state after. Nothing else saves: a change not saved is gone
when the process is. A resource no request has reached has no file, and
saving it is an error.

### Persist

`mumulib.persist.Persist` is the other persistent kind: a JSON document,
kept in its file and served from it, for data with nothing to compute.

```python
people = Persist({"ada": {"name": "Ada"}})
app = consumers_app({"people": people})  # var/data/people.json
```

Its first request loads its file as the document -- an existing file wins
-- or, with none, writes what it was made with there at once. `GET
/people.json` is then the file, streamed as it is on disk. Below it, the
document is walked as any dict or list: `GET /people/ada/name.txt` reads
it, and a `PUT` or `DELETE` there sets or removes an entry, then writes the
whole document to the file, atomically, before it is answered. A `PUT
/people.json` replaces the document. Every write inside it announces
`/people`. It is JSON only for now: `/people.html` is not found.

### Caching

What a file holds is cached by it. A `GET` of a persist, or of anything
below it, and of a resource's own `.json`, when that is its state, is
answered with the file's `ETag` -- its modification time and size, so a
write is a new one -- and `Cache-Control: no-cache`, so the client asks
each time; asked with `If-None-Match` naming it, the answer is 304 Not
Modified, and nothing else. A resource's own answers, what its handlers
compute, have neither, and neither does anything held in memory alone.

### Slots

When `template` is a parsed template, `handle_GET` fills a copy of it: each
slot, `data-slot` or `data-attr`, from the resource's `slot_<name>` -- a
method called with the request, async or not, or a plain value -- or, with
no `slot_`, from its state's entry of that name:

```python
class Todos(Resource):
    template = parse_template(open("todos.html", "rb"))
    slot_title = "To do"

    async def slot_items(self, request):
        return [self.pattern("item", text=t.text) for t in await load()]
```

A slot takes what it is given as text, escaped; a tree, or a list of them,
as markup -- `self.pattern(name, **slots)` is a filled copy of one of the
template's `data-pat` patterns; and anything else as the HTML a producer
makes of it, so a dict is its listing and a resource its page. `None` empties
a slot, and a slot with neither a `slot_` nor a state entry keeps what the
template has there. A slot
inside a pattern is the pattern's, filled when it is copied. A value with no
HTML form is a `TypeError` naming its slot, before anything is sent.

## Vite pages

A page written in TypeScript and built by Vite is published as a
`mumulib.static.Page`, naming its HTML entry in the Vite project, and served
exactly as Vite made it: Python does not fill it. Past the HTML the page is
TypeScript's, asking the tree for what it shows.

```python
app = consumers_app(
    {"index": Page("notes/index.html"), "notes": Persist([])},
    vite="ts/build/pages",
)
```

The Vite project's `base` is `/mumulib-vite/`, which `consumers_app` then
keeps for itself, ahead of the tree. In production -- the default -- the
page is Vite's build of it, read from the `vite` directory, and
`/mumulib-vite/` serves everything else Vite built there:
`/mumulib-vite/assets/notes-3f2a.js`. Each is cached by its file, with an
`ETag`.

With `MUMULIB_DEVELOPMENT=1` in the environment, the page is asked of Vite's
dev server, always at `http://127.0.0.1:5757`. With mumulib's origin plugin
in the Vite config, the URLs Vite writes into it name that server in full,
so the browser loads the page's modules, and opens hot reloading, from Vite
itself, and `/mumulib-vite/` is not Python's at all. The page's own requests
-- the tree, the change stream -- are still to Python, its origin. An
entry's own URLs are root-relative, `/notes/main.ts`; the plugin refuses a
relative one.

## XML

At `.xml`, a dict is XML, for the readers that read it best -- language
models among them: a resource's state, a persist's document, a plain dict.
Each key is an element named by it, and each element says its type, by
JSON's name for it; the root is named by the document's class:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Character type="object">
  <name type="string">Code Reviewer</name>
  <tags type="array">
    <item type="string">review</item>
  </tags>
  <archived type="boolean">false</archived>
  <parent type="null"/>
</Character>
```

A key that is no element name -- `1st`, `a b` -- is
`<entry key="1st">`. Only a dict is XML: a list, or a string, at `.xml` is
not found. It is read alone; writes stay JSON and forms.

## Files and directories

A file object -- what `open()` returns -- is served as its bytes, read afresh
on each request. A `pathlib.Path` is too, and a `Path` to a directory is walked
into: `{"static": Path("static")}` serves `static/style.css` at
`/static/style.css`. The URL's extension is put back on the last segment as
part of the file's name, and is the type it is served as, so a file needs an
extension to be served. A file is its own type and no other: a `Path` to
`style.css`, published as `style`, is `/style.css`, and `/style.html` is not
found.

The slash, `/static/`, is the directory's `index.html` if it has one, and
else its index, as Apache's were: a page headed "Index of /static", with a
link to the parent directory and then one to each of its files. A plain
dict's or list's slash is the same; as a slot's filling inside a page, a
listing is its `<ul>` of links alone. Its name, `/static.json`, is
`{name: URL}`, a subdirectory's URL its own listing, `/static/sub.json`. Only
what could be fetched is listed, and `RefuseIndex` is how to have no listing
(see Guards).

Only what is in the directory is found: `..`, hidden names such as `.git` and
`.env`, and symlinks that lead outside are not. A directory is never written;
anything but `GET` or `HEAD` is 405.

## Functions

A function the URL ends at is its own producer: it is called as `f(state)`,
where `state` holds the request -- `"method"`, `"url"`, `"extension"`,
`"content_type"`, and `"parsed_body"` for a request with a body -- a
multipart form's files in it as `mumutypes.Upload`, its filename, type and
bytes as sent. Any kind of function will do. What an async generator or a generator yields is the
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

## Events

An `EventSource` published at a `.sse` URL is a stream of server-sent
events, and `put(item)` sends an item to every stream open at that moment:

```python
from mumulib.server import EventSource, consumers_app

events = EventSource()
app = consumers_app({"events": events})

events.put("hello")  # to every browser at /events.sse right now
```

Each item is sent as JSON, encoded as a `.json` URL's answer is, so a client
reads every event's data the same way, whatever was put:

```js
new EventSource('/events.sse').onmessage = (e) => show(JSON.parse(e.data))
```

A string arrives as a string, and a dict as an object; JSON has no raw
newline, so an item is always one event. Something with no JSON form raises
`TypeError` from `put`, and goes to no one.

Each stream has a buffer of its own, from when its client connects until it
goes, so a client hears what is put after it connects and nothing from
before. A client that falls `max_backlog` items behind (1000 unless given)
is closed rather than buffered for without end; a browser's `EventSource`
reconnects by itself. `listeners` is how many streams are open. Its only URL
is `.sse`: `/events.json` is not found. `put` is called from the event
loop's thread.

For events meant for one user, give them an `EventSource` of their own at a
URL no one else can guess, and tell only them where it is:

```python
import secrets

streams: dict[str, EventSource] = {}
app = consumers_app({"events": streams})

key = secrets.token_urlsafe()
streams[key] = EventSource()  # /events/<key>.sse is theirs alone
```

### Changes

Given an `EventSource` as `changes`, `consumers_app` puts on it the URL of
the container each request changes: each `POST`, `PUT`, `PATCH` or `DELETE`
answered with success, any 2xx, or a form post's 303 See Other. The app
serves it itself, read-only, at `/mumulib/changes.sse`, and beside it
`/mumulib/live.js`, which keeps a page's live elements up to date:

```python
changes = EventSource()
app = consumers_app(Site(), changes=changes)

# In a page made with tags.page(..., live=True): each live element has an id,
# and watches a URL -- live="/todos/3", or live=True for the page's own.
t.tr(id="todo-3", live="/todos/3")[...]
```

When a change announces the URL an element watches -- compared as paths,
without an extension, query or fragment, a trailing slash kept, and exactly
-- the page is fetched again, once for the change, and each element
watching it is replaced by the element with the same id in the fresh page.
Other elements are left as they are, and a change nothing watches fetches
nothing. A page of your own, not made with `tags.page`, links
`<script src="/mumulib/live.js" defer>` as it would any script.

A page of your own can listen too: `new EventSource("/mumulib/changes.sse")`,
each event's data the JSON of a URL.

The container is the nearest resource at or above what was written --
the `Resource` the request walked to, or the deepest it walked through --
whatever inside it was written: a `POST` to `/todos.json` and a `PUT` to
`/todos/items/3.json`, `items` being a list of the `/todos` resource's own,
both put `/todos`. A write with no resource above it puts `/`. The URL names
the object, not a representation of it, so it has no extension, and a
listener adds the extension it wants. It is put as the response's final
body is produced, so a change is heard even if the client that made it has
gone. A request that fails -- 404, 405, 500 -- puts nothing.

A resource learns its URL from the path a request first reaches it by, and
keeps it, as `url`: `/todos` for `/todos.json`, `/todos.html` and
`/todos/items/3.json` alike, or `/todos/` for one that is an index. One
resource has one URL: published in two places, the second to be reached is
a 500, logged with both.

An event stream never ends by itself, and a server stopping waits for open
responses to finish. So when `consumers_app` starts -- at the ASGI lifespan
startup, which uvicorn sends -- it puts a SIGINT and SIGTERM handler in front
of the server's own: one that ends every open stream and then hands the
signal on, so the server's wait is over at once. It is undone at lifespan
shutdown. A server run with lifespan off, or the app started off the main
thread, gets no handler, and its streams keep a stop waiting.

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
anything else with 405 Method Not Allowed and `Allow: GET, HEAD`, at any depth below
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

Requires Python 3.14 or newer. Licensed under MIT; see LICENSE.

The companion TypeScript library and browser examples are documented in the
[repository README](https://github.com/fzzzy/mumulib#readme).
