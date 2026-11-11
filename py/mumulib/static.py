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
dev server, always at VITE_DEV_SERVER, and served as it answers; and
everything under /mumulib-vite/ is passed on to it, as it comes -- each
module, stylesheet and asset a page loads, and the hot reloading websocket.
The page has one origin, this server's: Vite listens on this machine alone,
and a page opened from another reaches it through here, as it does in
production, over whatever this server speaks -- HTTP/2 over TLS, with
Hypercorn, every module of a page on one connection.
"""

import asyncio
import contextlib
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import aiofiles
import httpx2
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidHandshake
from websockets.typing import Subprotocol

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

logger = logging.getLogger(__name__)

# Where Vite's dev server always is, in development: a port of its own, on
# this machine, which only this server asks
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


def _below(page: bytes, prefix: str) -> bytes:
    """A built page with each URL under VITE_BASE put below prefix: wherever
    the base follows a quote, an attribute's =, or url(."""
    pattern = re.compile(rb"""(["'=(])""" + re.escape(VITE_BASE.encode()))
    return pattern.sub(
        lambda match: match[1] + prefix.encode() + VITE_BASE.encode(), page
    )


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
            page = await asyncio.to_thread(_fetch, url)
        except (urllib.error.URLError, OSError) as exc:
            logger.warning("Vite's dev server did not answer for %s: %s", url, exc)
            raise HTTPResponse(
                502, f"Vite's dev server did not answer for {url}\n"
            ) from exc
        # Its URLs name /mumulib-vite/ on this server, which passes them on
        yield page
        return
    file = file_of(thing, state)
    if file is None:
        raise HTTPResponse(500, "consumers_app was given no vite directory\n")
    if not file.is_file():
        # Where it was looked for is the server's to know, not the client's
        logger.error("%s is not built, in %s", thing.entry, file.parent)
        raise HTTPResponse(500, f"{thing.entry} is not built\n")
    prefix = state.get("prefix") or ""
    if prefix:
        # Mounted below a prefix: what the page loads from Vite's base is
        # below it too, as the page is
        page = await asyncio.to_thread(file.read_bytes)
        yield _below(page, prefix)
        return
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
    scope: dict[str, Any],
    send: Send,
    receive: Receive,
    vite: Path | None,
    development: bool,
) -> None:
    """A request under /mumulib-vite/: in production, the file Vite built
    there; in development, passed on to Vite's dev server."""
    text = [(b"content-type", b"text/plain; charset=UTF-8")]
    if development:
        await forward_http(scope, receive, send)
        return
    # Reached only in development, or given a build directory
    assert vite is not None
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


# =============================================================================
# In development, /mumulib-vite/ passed on to Vite's dev server
# =============================================================================

# Headers about the one connection they came on, not what it carried: not
# passed on, either way. Nor the host, which the client sets, nor what
# lets a browser in here, which is no business of Vite's
_HOP_BY_HOP = frozenset(
    {
        b"connection",
        b"keep-alive",
        b"proxy-connection",
        b"transfer-encoding",
        b"upgrade",
        b"te",
        b"trailer",
        b"host",
        b"cookie",
        b"authorization",
    }
)

_client: httpx2.AsyncClient | None = None


def _vite_client() -> httpx2.AsyncClient:
    """One client for every request passed on: a page loads hundreds of
    modules, each a request. No read timeout, for what streams."""
    global _client
    if _client is None:
        _client = httpx2.AsyncClient(timeout=httpx2.Timeout(10.0, read=None))
    return _client


def _on_vite(scope: dict[str, Any], scheme: str) -> str:
    """Where on Vite a request goes: the path below any prefix this app is
    mounted at, and the query, as they came."""
    raw = scope.get("raw_path") or scope["path"].encode()
    prefix = (scope.get("root_path") or "").encode()
    if prefix and raw.startswith(prefix):
        raw = raw[len(prefix) :]
    query = scope.get("query_string", b"")
    vite = urllib.parse.urlsplit(VITE_DEV_SERVER)
    where = f"{scheme}://{vite.netloc}{raw.decode('latin-1')}"
    return where + (f"?{query.decode('latin-1')}" if query else "")


def _passed_on(headers: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    return [(k, v) for k, v in headers if k.lower() not in _HOP_BY_HOP]


async def forward_http(scope: dict[str, Any], receive: Receive, send: Send) -> None:
    """A request, to Vite, and its answer, as it comes: its bytes as Vite
    sent them, compressed or not."""
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body"):
            break
    request = _vite_client().build_request(
        scope["method"],
        _on_vite(scope, "http"),
        headers=_passed_on(scope["headers"]),
        content=body,
    )
    try:
        response = await _vite_client().send(request, stream=True)
    except httpx2.HTTPError as exc:
        message = f"Vite's dev server, at {VITE_DEV_SERVER}, did not answer: {exc}\n"
        await _answer(
            send,
            502,
            message.encode(),
            [(b"content-type", b"text/plain; charset=UTF-8")],
        )
        return
    # Relayed until it ends, or until the browser has gone: a server does
    # not say so by failing a send -- what is sent to no one is dropped --
    # but by an http.disconnect on receive. Then Vite's response is closed,
    # so nothing goes on reading what no one will see
    relaying = asyncio.ensure_future(_relay(response, send))
    gone = asyncio.ensure_future(_disconnected(receive))
    try:
        await asyncio.wait({relaying, gone}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in (relaying, gone):
            task.cancel()
        await asyncio.gather(relaying, gone, return_exceptions=True)
        await response.aclose()


async def _relay(response: httpx2.Response, send: Send) -> None:
    """Vite's response, to the browser, as it comes."""
    await send(
        {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": _passed_on(list(response.headers.raw)),
        }
    )
    async for chunk in response.aiter_raw():
        await send({"type": "http.response.body", "body": chunk, "more_body": True})
    await send({"type": "http.response.body", "body": b""})


async def _disconnected(receive: Receive) -> None:
    """Over once the browser has gone: the request's body already read,
    what receive gives next is only that, its http.disconnect."""
    await receive()


async def forward_websocket(
    scope: dict[str, Any], receive: Receive, send: Send
) -> None:
    """A websocket -- Vite's hot reloading -- to Vite, and each message
    either way, until one side closes."""
    await receive()  # websocket.connect
    asked = [Subprotocol(p) for p in scope.get("subprotocols", [])]
    try:
        upstream = await connect(
            _on_vite(scope, "ws"), subprotocols=asked or None, max_size=None
        )
    except OSError, InvalidHandshake:
        await send({"type": "websocket.close", "code": 1011})
        return
    await send({"type": "websocket.accept", "subprotocol": upstream.subprotocol})
    down = asyncio.create_task(_to_browser(upstream, send))
    try:
        while True:
            message = await receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") is not None:
                await upstream.send(message["text"])
            elif message.get("bytes") is not None:
                await upstream.send(message["bytes"])
    except ConnectionClosed:
        pass
    finally:
        down.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await down
        await upstream.close()


async def _to_browser(upstream: ClientConnection, send: Send) -> None:
    """Vite's messages, to the browser; and its close, when it closes."""
    with contextlib.suppress(ConnectionClosed):
        async for message in upstream:
            if isinstance(message, str):
                await send({"type": "websocket.send", "text": message})
            else:
                await send({"type": "websocket.send", "bytes": message})
    with contextlib.suppress(RuntimeError):
        await send({"type": "websocket.close", "code": 1000})
