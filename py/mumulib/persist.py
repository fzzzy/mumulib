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

import aiofiles

from mumulib.consumers import (
    Located,
    add_consumer,
    answer,
    consume,
    refuse,
    write_atomically,
)
from mumulib.mumutypes import (
    Chunk,
    NotFoundResponse,
    Receive,
    Send,
    SpecialResponse,
    State,
)
from mumulib.producers import add_json_form, add_producer

__all__ = ["Persist"]

# How much of the file each body message carries
CHUNK_SIZE = 64 * 1024


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
    if state.get("extension", "json") != "json":
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
    file = thing.file

    async def stream(send: Send, receive: Receive) -> None:
        # The file as it is on disk, a chunk at a time
        async with aiofiles.open(file, "rb") as opened:
            while chunk := await opened.read(CHUNK_SIZE):
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )

    start = {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"application/json")],
    }
    yield SpecialResponse(start, b"", stream)


# A persist answers every method at its own URL: the dict or list it is in
# hands it a PUT, rather than replacing it with what was sent
add_consumer(Persist, _consume_persist, own_methods=True)
add_producer(Persist, _produce_persist)
add_json_form(Persist, lambda persist: persist.document)
