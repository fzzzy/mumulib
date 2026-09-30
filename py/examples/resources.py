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
    GET    /todos.html                        the list as <ul>
    POST   /todos.json  {"text": "Milk"}      {"url": "/todos/items/2.json"}
    POST   /todos.html  text=Milk             the list as <ul>  (the form at /)
    GET    /todos/items/0.json                {"text": ..., "done": ...}
    GET    /todos/items/                      a listing of links to each item
    PUT    /todos/items/0.json  {"done": true}    the item, done
    DELETE /todos/items/0.json                405, Allow: GET, PUT

Each item is a Todo in a plain list. A list would replace an element on
PUT and tombstone it on DELETE, but a resource answers every method at its
own URL itself, wherever it is: the list hands the request to the Todo,
whose handle_PUT changes it in place and checks what it is sent, and which
has no handle_DELETE, so it cannot be removed.
"""

import html
from typing import Any, cast

from mumulib.mumutypes import HTTPResponse, State
from mumulib.resource import Resource
from mumulib.server import consumers_app

INDEX = """<!doctype html>
<title>Resources</title>
<form method="post" action="/todos.html">
  <label>To do <input name="text" value="Milk" /></label>
  <button>Add</button>
</form>
<p><a href="/todos.html">The list</a>, <a href="/todos.json">as JSON</a>,
and <a href="/todos/items/">each item</a>.</p>
"""


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
            items = "".join(
                f'  <li><a href="{base}/items/{i}.html">{html.escape(todo.text)}'
                f"</a>{' (done)' if todo.done else ''}</li>\n"
                for i, todo in enumerate(self.child_items)
            )
            return f"<ul>\n{items}</ul>\n"
        return [
            {"text": todo.text, "done": todo.done, "url": f"{base}/items/{i}.json"}
            for i, todo in enumerate(self.child_items)
        ]

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


app = consumers_app(Site())
