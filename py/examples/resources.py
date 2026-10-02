"""Resources: objects that decide how their own URLs answer.

    make server SERVER=resources

A Resource subclass is published like anything else. Its children are its
child_ attributes, walked into by name, and a request that ends at it is
answered by its handle_<METHOD>, called with the request. GET
renders its template unless it says otherwise; any method it has no handler
for is 405, with Allow naming the ones it has. What a handler returns is
produced as though it had been published there, of the URL's type.

    GET    /                                  the page: a form, and the list
    GET    /about.txt                         About's template, as text
    GET    /todos.json                        [{"text": ..., "done": ..., "url": ...}]
    GET    /todos.html                        the list's page, from a template,
                                              with a checkbox that PUTs each item
    POST   /todos.json  {"text": "Milk"}      {"url": "/todos/items/2.json"}
    POST   /todos.html  text=Milk             the list's page  (the form at /)
    GET    /todos/items/0.json                {"text": ..., "done": ...}
    GET    /todos/items/                      a listing of links to each item
    PUT    /todos/items/0.json  {"done": true}    the item, done
    DELETE /todos/items/0.json                405, Allow: GET, PUT
    GET    /mumulib/changes.sse               "/todos/items/0", "/todos", ...
    GET    /mumulib/live.js                   the script that follows them

Every page open is kept up to date with everyone's changes: the app is
given an EventSource as changes, and puts on it the URL of the resource each
POST, PUT or DELETE changed. The list page links mumulib's live.js: the list
watches /todos, which a POST adding to it announces, and each item its own
URL, which a PUT to it announces -- so the page is fetched again and the
list, or the one item, put in place.

Each item is a Todo in a plain list. A list would replace an element on
PUT and tombstone it on DELETE, but a resource answers every method at its
own URL itself, wherever it is: the list hands the request to the Todo,
whose handle_PUT changes it in place and checks what it is sent, and which
has no handle_DELETE, so it cannot be removed.
"""

import html
from io import BytesIO
from typing import Any, cast

from mumulib.mumutypes import HTTPResponse, State
from mumulib.resource import Resource
from mumulib.server import EventSource, consumers_app
from mumulib.tags import Stan, parse_template

INDEX = """<!doctype html>
<title>Resources</title>
<form method="post" action="/todos.html">
  <label>To do <input name="text" value="Milk" /></label>
  <button>Add</button>
</form>
<p><a href="/todos.html">The list</a>, <a href="/todos.json">as JSON</a>,
and <a href="/todos/items/">each item</a>.</p>
"""


# The list's page. The <li> is a pattern, data-pat: copied for each item,
# and its slots, data-slot for content and data-attr for attributes, filled
# on the copy. The <ul> is the page's slot, filled with the copies, which
# takes the place of the pattern that was there.
#
# Each item's checkbox PUTs {"done": ...} to the item's own URL, and is put
# back if that fails; checked is an attribute slot, there when done is True
# and left out when it is False. The page's one script of its own is that:
# live.js keeps the list and each item up to date.
LIST_PAGE = parse_template(
    BytesIO(
        b"""<!doctype html>
<html>
<head><title>To do</title></head>
<body>
<h1>To do</h1>
<ul id="items" data-live="/todos" data-slot="items">
  <li data-pat="item" data-attr="id=item_id,data-live=watch">
    <input type="checkbox" data-attr="data-url=json_url,checked=done" />
    <a data-slot="text" data-attr="href=url">An item</a>
  </li>
</ul>
<p><a href="/">Add another</a></p>
<script src="/mumulib/live.js" defer></script>
<script>
// A box changed here: PUT it to its item, and put it back if that fails.
// One listener for the page, so it hears boxes in an item swapped in too.
document.addEventListener("change", async (event) => {
  const box = event.target;
  if (!box.dataset.url) return;
  const response = await fetch(box.dataset.url, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ done: box.checked }),
  });
  if (!response.ok) box.checked = !box.checked;
});
</script>
</body>
</html>
"""
    )
)
assert LIST_PAGE is not None


def own_url(request: State) -> str:
    """The URL the request named, without its extension: /todos.json's is
    /todos, below which its items are."""
    return str(request.get("url", "")).rpartition(".")[0]


def fields(request: State) -> dict[str, Any]:
    """What was sent, a JSON object or a form, as a dict; else empty."""
    body = request.get("parsed_body")
    return cast(dict[str, Any], body) if isinstance(body, dict) else {}


class Todo(Resource):
    """One thing to do: read, and changed with PUT, but never removed."""

    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text
        self.done = False

    async def handle_GET(self, request: State) -> Any:
        if request["extension"] == "html":
            # The text is a visitor's: escaped, as anything they send must be
            mark = "done" if self.done else "to do"
            return f"<p>{html.escape(self.text)} ({mark})</p>"
        return {"text": self.text, "done": self.done}

    async def handle_PUT(self, request: State) -> Any:
        # Only what a Todo is made of, and only of its own types
        changes = fields(request)
        text, done = changes.get("text", self.text), changes.get("done", self.done)
        if not changes or not isinstance(text, str) or not isinstance(done, bool):
            raise HTTPResponse(400, 'Send {"text": a string, "done": true or false}\n')
        self.text, self.done = text, done
        return await self.handle_GET(request)


class Todos(Resource):
    """The list: read whole, and added to with POST.

    Its page is LIST_PAGE, filled from its slot_ methods by Resource's own
    handle_GET: slot_items is the item pattern, copied for each to-do.
    """

    template = LIST_PAGE

    def __init__(self, *texts: str) -> None:
        super().__init__()
        # A child like any other: /todos/items/0.json is child_items[0]
        self.child_items = [Todo(text) for text in texts]

    async def handle_GET(self, request: State) -> Any:
        if request["extension"] == "html":
            return await super().handle_GET(request)
        base = own_url(request)
        return [
            {"text": todo.text, "done": todo.done, "url": f"{base}/items/{i}.json"}
            for i, todo in enumerate(self.child_items)
        ]

    def slot_items(self, request: State) -> list[Stan]:
        base = own_url(request)
        return [
            self.pattern(
                "item",
                # A visitor's text, escaped as the page is written out
                text=todo.text,
                url=f"{base}/items/{i}.html",
                json_url=f"{base}/items/{i}.json",
                # True writes checked, False leaves it out
                done=todo.done,
                item_id=f"item-{i}",
                watch=f"{base}/items/{i}",
            )
            for i, todo in enumerate(self.child_items)
        ]

    async def handle_POST(self, request: State) -> Any:
        text = fields(request).get("text")
        if not isinstance(text, str) or not text:
            raise HTTPResponse(400, 'Send {"text": a string}\n')
        self.child_items.append(Todo(text))
        if request["extension"] == "html":
            # A form's answer is the page it asked for: the list, with this
            return await self.handle_GET(request)
        return {"url": f"{own_url(request)}/items/{len(self.child_items) - 1}.json"}


class About(Resource):
    """Nothing but a template: GET renders it, and the rest is 405."""

    template = "A to-do list, published as resources.\n"


class Site(Resource):
    """The root. It is no container, so its slash is its child_index."""

    child_index = INDEX

    def __init__(self) -> None:
        super().__init__()
        self.child_todos = Todos("Write the example", "Test it")
        self.child_about = About()


# Every change announced on it: consumers_app serves it, and live.js
changes = EventSource()

site = Site()
app = consumers_app(site, changes=changes)
