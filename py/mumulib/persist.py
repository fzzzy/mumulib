"""Persist: a JSON document published at a URL, and kept in a file there.

    people = Persist({"ada": {"name": "Ada"}, "grace": {"name": "Grace"}})
    app = consumers_app({"people": people})

    GET    /people.json             the file, as it is on disk
    GET    /people/ada/name.txt     Ada, from the document in memory
    PUT    /people/ada/name.json    "Augusta": set there, and the file written
    DELETE /people/grace.json       removed, and the file written
    PUT    /people.json             the whole document replaced

A persist is Located: the first request to reach it gives it its URL, and
its file, named by it in the app's data directory -- var/data/people.json.
The file is loaded as the document, if there is one: an existing file wins
over what the persist was made with. With none, what it was made with is
written there at once, so that the file is what GET serves from then on.

Below it, the document is walked as any dict or list is, and written the
same way: a PUT sets an entry, a DELETE removes one. A write that succeeds
writes the whole document to the file again, atomically, before it is
answered, and announces the persist's URL -- the container it changed --
wherever inside it the write was made.

JSON only, to start: its own URL as anything but .json is not found.
TODO: its .html.
"""

import json
from collections.abc import AsyncIterator
from typing import Any

from mumulib.consumers import (
    Located,
    add_consumer,
    answer,
    consume,
    plain,
    refuse,
    write_atomically,
)
from mumulib.mumutypes import (
    Chunk,
    NotFoundResponse,
    Send,
    SpecialResponse,
    State,
)
from mumulib.producers import add_producer
from mumulib.static import stream
from mumulib.xml_producer import to_xml

__all__ = ["Persist"]


class Persist(Located):
    """A JSON document, kept in its file, and served from it."""

    # Everything read at or below it is its file's: the file's ETag is theirs
    cached = True

    def __init__(self, document: Any = None) -> None:
        # What it was made with: the document until its file says otherwise
        self.document: Any = {} if document is None else document

    async def load(self) -> None:
        """Its file, if it has one, as the document; else the document,
        written there now."""
        if self.file is None:
            return
        if self.file.exists():
            self.document = json.loads(self.file.read_text(encoding="utf-8"))
        else:
            self.write()

    def write(self) -> None:
        """The whole document, to its file, atomically. With no file -- no
        data directory -- it is kept in memory alone."""
        plain(self.document, self.url or type(self).__name__)
        if self.file is not None:
            write_atomically(self.file, json.dumps(self.document))


def _succeeded(result: Any) -> bool:
    return isinstance(result, SpecialResponse) and (
        200 <= result.asgi_send_dict["status"] < 300
    )


async def _consume_persist(
    parent: Persist, segments: list[str], state: State, send: Send
) -> Any:
    result = await consume(parent.document, segments, state, send)
    if state.get("method", "GET").upper() != "GET" and _succeeded(result):
        parent.write()
    return result


async def _produce_persist(thing: Persist, state: State) -> AsyncIterator[Chunk]:
    """The persist at its own URL: GET is its file, PUT replaces it."""
    extension = state.get("extension", "json")
    if extension == "xml" and state.get("method", "GET").upper() == "GET":
        # Its document as XML, from memory -- the same as its file -- when it
        # is a dict, as only a dict is XML
        document: Any = thing.document
        if not isinstance(document, dict):
            raise NotFoundResponse()
        yield to_xml(document, type(thing).__name__)
        return
    if extension != "json":
        raise NotFoundResponse()
    method = state.get("method", "GET").upper()
    if method == "PUT":
        thing.document = state.get("parsed_body")
        thing.write()
        raise answer(204)
    if method != "GET":
        raise refuse("GET, PUT")
    if thing.file is None:
        yield json.dumps(thing.document)
        return
    start = {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"application/json")],
    }
    # The file as it is on disk, a chunk at a time
    yield SpecialResponse(start, b"", stream(thing.file))


# A persist answers every method at its own URL: the dict or list it is in
# hands it a PUT, rather than replacing it with what was sent
add_consumer(Persist, _consume_persist, own_methods=True)
add_producer(Persist, _produce_persist)
