"""Resources: objects that decide how their own URLs answer.

    make server SERVER=resources

A Resource subclass is published like anything else. Its children are its
child_ attributes, walked into by name, and a request that ends at it is
answered by its handle_<METHOD>, called with the request's state. GET
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
    GET    /changes.sse                       "/todos/items/0", "/todos", ...

Every page open is kept up to date with everyone's changes: the app is
given the site's EventSource as changes, and puts on it the URL of whatever
each POST, PUT or DELETE changed. The list page listens, and fetches again
what it hears.

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
# back if that fails. The page listens at /changes.sse, where the server
# says what any request changed, so every page open shows every change. A
# slot can set an attribute but not leave one out, and checked is on whenever
# it is there at all, so the box gets its state from data-done instead.
LIST_PAGE = parse_template(
    BytesIO(
        b"""<!doctype html>
<html>
<head><title>To do</title></head>
<body>
<h1>To do</h1>
<ul data-slot="items">
  <li data-pat="item">
    <input type="checkbox" data-attr="data-url=json_url,data-done=done" />
    <a data-slot="text" data-attr="href=url">An item</a>
  </li>
</ul>
<p><a href="/">Add another</a></p>
<script>
// Each box from its data-done, here and in any list swapped in later
const sync = () => {
  for (const box of document.querySelectorAll("input[data-url]")) {
    box.checked = box.dataset.done === "true";
  }
};
sync();

// A box changed here: PUT it to its item, and put it back if that fails.
// One listener for the page, so it hears boxes in a list swapped in too.
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

// Something changed, here or in anyone else's page: the server says what.
// A changed item is fetched again and shown; anything else of the list's,
// a POST adding to it, is the whole list again.
new EventSource("/changes.sse").onmessage = async (event) => {
  const url = JSON.parse(event.data);
  const box = document.querySelector(`input[data-url="${url}.json"]`);
  if (box) {
    const todo = await (await fetch(`${url}.json`)).json();
    box.dataset.done = String(todo.done);
    box.checked = todo.done;
    box.nextElementSibling.textContent = todo.text;
  } else if (url === "/todos" || url.startsWith("/todos/")) {
    const page = await (await fetch("/todos.html")).text();
    const fresh = new DOMParser().parseFromString(page, "text/html");
    document.querySelector("ul").replaceWith(fresh.querySelector("ul"));
    sync();
  }
};
</script>
</body>
</html>
"""
    )
)
assert LIST_PAGE is not None


def fields(state: State) -> dict[str, Any]:
    """What was sent, a JSON object or a form, as a dict; else empty."""
    body = state.get("parsed_body")
    return cast(dict[str, Any], body) if isinstance(body, dict) else {}


class Todo(Resource):
    """One thing to do: read, and changed with PUT, but never removed."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.done = False

    def handle_GET(self, state: State) -> Any:
        if state["extension"] == "html":
            # The text is a visitor's: escaped, as anything they send must be
            mark = "done" if self.done else "to do"
            return f"<p>{html.escape(self.text)} ({mark})</p>"
        return {"text": self.text, "done": self.done}

    def handle_PUT(self, state: State) -> Any:
        # Only what a Todo is made of, and only of its own types
        changes = fields(state)
        text, done = changes.get("text", self.text), changes.get("done", self.done)
        if not changes or not isinstance(text, str) or not isinstance(done, bool):
            raise HTTPResponse(400, 'Send {"text": a string, "done": true or false}\n')
        self.text, self.done = text, done
        return self.handle_GET(state)


class Todos(Resource):
    """The list: read whole, and added to with POST."""

    def __init__(self, *texts: str) -> None:
        # A child like any other: /todos/items/0.json is child_items[0]
        self.child_items = [Todo(text) for text in texts]

    def handle_GET(self, state: State) -> Any:
        # This resource's own URL, /todos.json, without its extension
        base = str(state.get("url", "")).rpartition(".")[0]
        if state["extension"] == "html":
            return self.render_page(base)
        return [
            {"text": todo.text, "done": todo.done, "url": f"{base}/items/{i}.json"}
            for i, todo in enumerate(self.child_items)
        ]

    def render_page(self, base: str) -> Stan:
        """The list page: the item pattern copied and filled for each item,
        and the copies filled into the page's items slot."""
        assert LIST_PAGE is not None
        items = [
            LIST_PAGE.clone_pat(
                "item",
                # Slots are written out as they are given: the text is a
                # visitor's, so escaped here
                text=html.escape(todo.text),
                url=f"{base}/items/{i}.html",
                json_url=f"{base}/items/{i}.json",
                done="true" if todo.done else "false",
            )
            for i, todo in enumerate(self.child_items)
        ]
        # A copy, filled: the template itself stays as it is for the next
        page = LIST_PAGE.copy()
        page.fill_slots("items", items)
        return page

    def handle_POST(self, state: State) -> Any:
        text = fields(state).get("text")
        if not isinstance(text, str) or not text:
            raise HTTPResponse(400, 'Send {"text": a string}\n')
        self.child_items.append(Todo(text))
        if state["extension"] == "html":
            # A form's answer is the page it asked for: the list, with this
            return self.handle_GET(state)
        base = str(state.get("url", "")).rpartition(".")[0]
        return {"url": f"{base}/items/{len(self.child_items) - 1}.json"}


class About(Resource):
    """Nothing but a template: GET renders it, and the rest is 405."""

    template = "A to-do list, published as resources.\n"


class Site(Resource):
    """The root. It is no container, so its slash is its child_index."""

    child_index = INDEX

    def __init__(self) -> None:
        self.child_todos = Todos("Write the example", "Test it")
        self.child_about = About()
        # /changes.sse: the URL of whatever a request changes, for every
        # page open to fetch again
        self.child_changes = EventSource()


site = Site()
app = consumers_app(site, changes=site.child_changes)
