"""Static: things served from disk that are not persists -- a Vite page.

    app = consumers_app(
        {"index": Page("notes/index.html"), "notes": Persist([])},
        vite="ts/dist/pages",
    )

A Page names a Vite HTML entry, relative to the Vite project's root, and is
served as HTML exactly as Vite made it. Python does not fill or change it:
past the HTML, the page is Vite's and TypeScript's.

In production -- the default -- the entry is Vite's build of it, read from
the directory consumers_app is given as vite, and everything else Vite built
is served from there too, under /mumulib-vite/, its base:
/mumulib-vite/assets/index-3f2a.js is <vite>/assets/index-3f2a.js. Each is
cached by its file, as a persist is: an ETag from its modification time and
size, no-cache, and 304 to an If-None-Match naming it.

With MUMULIB_DEVELOPMENT=1 in the environment, the entry is asked of Vite's
dev server, always at VITE_DEV_SERVER, and served as it answers. The URLs
in it name that server in full -- mumulib's Vite origin plugin sees to it --
so the browser fetches the page's modules, and opens the hot reloading
websocket, from Vite directly. Python's /mumulib-vite/ is then not found:
nothing is asked of it.
"""

import asyncio
import logging
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import aiofiles

from mumulib.mumutypes import (
    Chunk,
    HTTPResponse,
    NotFoundResponse,
    Receive,
    Send,
    SpecialResponse,
    State,
    Writer,
    content_type_for,
)
from mumulib.producers import add_producer

__all__ = ["Page", "VITE_DEV_SERVER", "VITE_BASE"]

# Where Vite's dev server always is, in development: a port of its own
logger = logging.getLogger(__name__)

VITE_DEV_SERVER = "http://127.0.0.1:5757"

# Vite's base: everything it serves is below it, built or not
VITE_BASE = "/mumulib-vite/"

# How much of a file each body message carries
CHUNK_SIZE = 64 * 1024


class Page:
    """A Vite HTML entry, served as Vite made it: Page("notes/index.html")."""

    def __init__(self, entry: str) -> None:
        self.entry = entry


def file_etag(file: Path) -> bytes:
    """A file's ETag: its modification time and size, so any write to it is
    a new one."""
    stat = file.stat()
    return f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'.encode()


def cache_headers(file: Path) -> list[tuple[bytes, bytes]]:
    """ETag and Cache-Control for what file holds: no-cache has the client
    ask each time, with If-None-Match."""
    return [(b"etag", file_etag(file)), (b"cache-control", b"no-cache")]


def is_fresh(etag: bytes, headers: list[tuple[bytes, bytes]]) -> bool:
    """Whether If-None-Match names etag, or is *: the client has it."""
    for key, value in headers:
        if key.lower() == b"if-none-match":
            tags = [tag.strip().removeprefix(b"W/") for tag in value.split(b",")]
            return etag in tags or b"*" in tags
    return False


def stream(file: Path) -> Writer:
    """A writer sending file as body messages, a chunk at a time."""

    async def writer(send: Send, receive: Receive) -> None:
        async with aiofiles.open(file, "rb") as opened:
            while chunk := await opened.read(CHUNK_SIZE):
                await send(
                    {"type": "http.response.body", "body": chunk, "more_body": True}
                )

    return writer


def file_of(thing: object, state: State) -> Path | None:
    """The file thing is served from, if it is a Page in production: what
    its answer is cached by."""
    vite: Path | None = state.get("vite")
    if isinstance(thing, Page) and not state.get("development") and vite:
        return vite / thing.entry
    return None


def _fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=10) as response:
        return response.read()


async def _produce_page(thing: Page, state: State) -> AsyncIterator[Chunk]:
    if state.get("extension") != "html":
        raise NotFoundResponse()
    if state.get("development"):
        url = f"{VITE_DEV_SERVER}{VITE_BASE}{thing.entry}"
        try:
            # TODO: an async client; a thread keeps the loop free meanwhile
            yield await asyncio.to_thread(_fetch, url)
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("Vite's dev server did not answer for %s: %s", url, exc)
            raise HTTPResponse(
                502, f"Vite's dev server did not answer for {url}\n"
            ) from exc
        return
    file = file_of(thing, state)
    if file is None:
        raise HTTPResponse(500, "consumers_app was given no vite directory\n")
    if not file.is_file():
        # Where it was looked for is the server's to know, not the client's
        logger.error("%s is not built, in %s", thing.entry, file.parent)
        raise HTTPResponse(500, f"{thing.entry} is not built\n")
    start = {
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/html; charset=UTF-8")],
    }
    yield SpecialResponse(start, b"", stream(file))


add_producer(Page, _produce_page)


async def _answer(
    send: Send, status: int, body: bytes, headers: list[tuple[bytes, bytes]]
) -> None:
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


async def serve_vite(
    scope: dict[str, Any], send: Send, receive: Receive, vite: Path, development: bool
) -> None:
    """A request under /mumulib-vite/: in production, the file Vite built there."""
    text = [(b"content-type", b"text/plain; charset=UTF-8")]
    if development:
        message = f"In development /mumulib-vite/ is Vite's own, at {VITE_DEV_SERVER}\n"
        await _answer(send, 404, message.encode(), text)
        return
    if scope["method"] != "GET":
        await _answer(send, 405, b"Only GET\n", [*text, (b"allow", b"GET, HEAD")])
        return
    file = (vite / scope["path"].removeprefix(VITE_BASE)).resolve()
    if not file.is_relative_to(vite) or not file.is_file():
        await _answer(send, 404, b"Not built\n", text)
        return
    cache = cache_headers(file)
    if is_fresh(cache[0][1], scope["headers"]):
        await _answer(send, 304, b"", cache)
        return
    content_type = (
        content_type_for(file.suffix.removeprefix(".")) or "application/octet-stream"
    )
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", content_type.encode()), *cache],
        }
    )
    await stream(file)(send, receive)
    await send({"type": "http.response.body", "body": b""})
