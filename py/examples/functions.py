"""A function in the tree: called for each request that ends at it.

    make server SERVER=functions

A function published in the tree is its own producer. When a URL ends at
it, it is called as f(state), where state holds the request: "method",
"url", "extension", "content_type", and "parsed_body" for a request with
one. Any kind of function will do: what an async generator or a generator
yields is the response, and what a coroutine or a plain function returns is
produced as though it had been published there -- a string as text, a dict
as JSON -- of the type the URL names.

    GET  /greet.txt                     Hello, world!
    GET  /greet.json                    {"greeting": "Hello, world!"}
    POST /greet.json  {"name": "Ada"}   {"greeting": "Hello, Ada!"}
    POST /greet.html  name=Ada          <p>Hello, Ada!</p>  (the form at /)

A function is a leaf: nothing is below it, and it has no slash. PUT or
DELETE at its name would be its parent's to answer -- replacing or
removing the function -- so the dict here is a MappingProxyType, the
read-only view of a dict, which refuses both with 405 and lets GET and
POST through to the function.
"""

import html
import json
from collections.abc import AsyncIterator
from types import MappingProxyType
from typing import Any, cast

from mumulib.mumutypes import State
from mumulib.server import consumers_app

INDEX = """<!doctype html>
<title>Functions</title>
<form method="post" action="/greet.html">
  <label>Name <input name="name" value="Ada" /></label>
  <button>Greet</button>
</form>
"""


async def greet(state: State) -> AsyncIterator[str]:
    # A JSON object or a form: either way, a dict of what was sent
    body = state.get("parsed_body")
    fields = cast(dict[str, Any], body) if isinstance(body, dict) else {}
    name = str(fields.get("name", "world"))
    greeting = f"Hello, {name}!"
    if state["extension"] == "json":
        yield json.dumps({"greeting": greeting})
    elif state["extension"] == "html":
        # The name is the visitor's: escaped, as anything they send must be
        yield f"<p>{html.escape(greeting)}</p>"
    else:
        yield greeting


app = consumers_app(MappingProxyType({"index": INDEX, "greet": greet}))
