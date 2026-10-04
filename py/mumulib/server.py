import asyncio
import json
import os
import signal
import threading
import traceback
from collections.abc import AsyncIterator, Callable
from pathlib import Path
from types import FrameType
from typing import Any
from urllib import parse

from python_multipart.multipart import (
    MultipartParser,
    MultipartState,
    parse_options_header,
)

# Registers XML for dicts, at .xml
from mumulib import xml_producer  # noqa: F401  # pyright: ignore[reportUnusedImport]
from mumulib.consumers import GetOnly, consume, is_container
from mumulib.mumutypes import (
    ASGIApp,
    Message,
    Receive,
    Scope,
    Send,
    SpecialResponse,
    State,
    Upload,
    content_type_for,
)
from mumulib.producers import add_producer, custom_serializer, produce
from mumulib.static import VITE_BASE, cache_headers, file_of, is_fresh, serve_vite

# The public API: Publishing an object, and streaming events from it. The body
# parsers and path helpers are the app's own.
__all__ = [
    "consumers_app",
    "EventSource",
]

# Default max request body size: 10MB
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


class BodyTooLarge(Exception):
    """A request body over the limit: 413.

    Not a ValueError, which is what a body that will not parse raises -- a
    json.JSONDecodeError, a UnicodeDecodeError -- and is a 400.
    """


async def send_error_response(
    send: Send, status: int, error_type: str, message: str
) -> None:
    """
    Send a consistent JSON error response.

    Args:
        send: ASGI send callable
        status: HTTP status code
        error_type: Error type/title (e.g., "Bad Request", "Internal Server Error")
        message: Detailed error message
    """
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json; charset=UTF-8")],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": json.dumps({"error": error_type, "message": message}).encode(
                "utf-8"
            ),
            "more_body": False,
        }
    )


async def parse_json(
    receive: Receive, max_size: int = DEFAULT_MAX_BODY_SIZE
) -> Any | None:
    body = b""

    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        # ASGI servers should only send http.request during body reading
        if message["type"] == "http.request":  # pragma: no branch
            # Accumulate body chunks
            body += message.get("body", b"")

            # Check if body size exceeds limit
            if len(body) > max_size:
                raise BodyTooLarge(
                    f"Request body too large: {len(body)} bytes exceeds limit "
                    f"of {max_size} bytes"
                )

            # Check if this is the last body chunk
            if not message.get("more_body", False):
                break

    # Process the full body
    body_text = body.decode("utf-8")
    if len(body_text):
        return json.loads(body_text)
    return None


async def parse_urlencoded(
    receive: Receive, max_size: int = DEFAULT_MAX_BODY_SIZE
) -> dict[str, Any]:
    body = b""

    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        # ASGI servers should only send http.request during body reading
        if message["type"] == "http.request":  # pragma: no branch
            # Accumulate body chunks
            body += message.get("body", b"")

            # Check if body size exceeds limit
            if len(body) > max_size:
                raise BodyTooLarge(
                    f"Request body too large: {len(body)} bytes exceeds limit "
                    f"of {max_size} bytes"
                )

            # Check if this is the last body chunk
            if not message.get("more_body", False):
                break
    result: dict[str, Any] = {}
    # parse_qsl decodes each name and value once, which is all they are
    # encoded: decoding again made a literal %41 an A
    for k, v in parse.parse_qsl(body.decode("utf-8")):
        if k.endswith("]") and "[" in k:
            values_list = result.get(k, [])
            values_list.append(v)
            result[k] = values_list
        else:
            result[k] = v
    return result


async def parse_multipart(
    receive: Receive, boundary: bytes, max_size: int = DEFAULT_MAX_BODY_SIZE
) -> dict[str, Any]:
    """A multipart/form-data body, by field name: boundary is the
    Content-Type's own parameter, without the leading dashes.

    A part with a filename is an Upload; any other is text. name[] collects
    every value sent by that name into a list, as for a urlencoded form.
    """
    parts: list[tuple[list[tuple[bytes, bytes]], bytearray]] = []
    header: list[bytearray] = []

    def on_part_begin() -> None:
        parts.append(([], bytearray()))

    def on_header_field(data: bytes, start: int, end: int) -> None:
        if not header:
            header.extend([bytearray(), bytearray()])
        header[0] += data[start:end]

    def on_header_value(data: bytes, start: int, end: int) -> None:
        header[1] += data[start:end]

    def on_header_end() -> None:
        parts[-1][0].append((bytes(header[0]).lower(), bytes(header[1])))
        header.clear()

    def on_part_data(data: bytes, start: int, end: int) -> None:
        parts[-1][1].extend(data[start:end])

    parser = MultipartParser(
        boundary,
        {
            "on_part_begin": on_part_begin,
            "on_header_field": on_header_field,
            "on_header_value": on_header_value,
            "on_header_end": on_header_end,
            "on_part_data": on_part_data,
        },
    )
    size = 0
    while True:
        message = await receive()

        # ASGI servers should only send http.request during body reading
        if message["type"] == "http.request":  # pragma: no branch
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > max_size:
                raise BodyTooLarge(
                    f"Request body too large: {size} bytes exceeds limit "
                    f"of {max_size} bytes"
                )
            parser.write(chunk)
            if not message.get("more_body", False):
                break
    parser.finalize()
    if parser.state != MultipartState.END:
        raise ValueError("Multipart body ended before its closing boundary")

    result: dict[str, Any] = {}
    for headers, content in parts:
        disposition = dict(headers).get(b"content-disposition", b"")
        _, options = parse_options_header(disposition)
        if b"name" not in options:
            continue
        name = options[b"name"].decode("utf-8")
        value: str | Upload
        if b"filename" in options:
            content_type = dict(headers).get(b"content-type")
            value = Upload(
                filename=options[b"filename"].decode("utf-8"),
                content_type=None if content_type is None else content_type.decode(),
                data=bytes(content),
            )
        else:
            value = content.decode("utf-8")
        if name.endswith("]") and "[" in name:
            result.setdefault(name, []).append(value)
        else:
            result[name] = value
    return result


def split_path(path: str) -> tuple[list[str], str] | None:
    """The segments to traverse, and the extension that names the type.

    The extension comes off the last segment: /hello.json and /hello.txt are
    both root["hello"], and /todos.json is the todos, as data. A path ending
    in a slash is its container's index, as HTML -- /, or /todos/ -- which is
    for people in browsers: the container's "index" entry, or the container.
    Any other path without an extension is None.
    """
    if path.endswith("/"):
        return [*path.split("/")[1:-1], "index"], "html"
    segments = path.split("/")[1:]
    key, dot, extension = segments[-1].rpartition(".")
    if not dot or not key or not extension:
        return None
    return [*segments[:-1], key], extension


def with_content_type(message: dict[str, Any], content_type: str) -> dict[str, Any]:
    """A response start whose Content-Type is `content_type`, whatever it said."""
    headers = [
        (k, v) for k, v in message.get("headers", []) if k.lower() != b"content-type"
    ]
    headers.insert(0, (b"content-type", content_type.encode("utf8")))
    return {**message, "headers": headers}


# The script that keeps a page's data-live elements up to date, which the
# app serves at /mumulib/live.js when it is given changes
LIVE_SCRIPT = Path(__file__).parent / "live.js"

# The methods that change what is published
MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# What a browser may send from any page: everything else is checked for coming
# from this origin
SAFE = frozenset({"GET", "HEAD", "OPTIONS"})


def cross_origin(scope: Scope) -> bool:
    """Whether a browser sent this request from another origin: a page on
    another site posting a form here, say, with the visitor's cookies.

    Sec-Fetch-Site says so where a browser sends it, and same-origin or none
    -- the visitor's own doing, a bookmark -- is all that is from here. Where
    it does not, Origin says so: from here if its host is the request's
    Host, the scheme left aside, which a proxy in front may have changed.
    With neither, it is no browser's -- curl, a script -- and not a cross-
    origin request in the sense meant.
    """
    headers: dict[bytes, bytes] = {
        key.lower(): value for key, value in scope["headers"]
    }
    site = headers.get(b"sec-fetch-site")
    if site is not None:
        return site not in (b"same-origin", b"none")
    origin = headers.get(b"origin")
    if origin is None:
        return False
    host = headers.get(b"host")
    origin_host = parse.urlsplit(origin.decode("latin-1")).netloc
    return host is None or origin_host.lower() != host.decode("latin-1").lower()


def _announce_changes(send: Send, changes: EventSource, state: State) -> Send:
    """send, for a request that may change something: once its response has
    succeeded, the URL of the container it changed is put on changes.

    Success is any 2xx, or 303 See Other, a form post's. The container is
    the nearest Located object the request walked to or through -- a
    Resource, which is all of what it keeps -- whatever was written inside
    it: a POST to /todos.json and a PUT to /todos/items/0.json, items
    being a list of the Todos resource's own, both put /todos. A write with
    no Located object above it puts /. It is put as the final body is
    produced, before it is sent: the change is made whether or not this
    client stays to hear so.
    """
    status = 0

    async def announcing_send(message: Message) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]
        elif message["type"] == "http.response.body" and not message.get(
            "more_body", False
        ):
            # A 303 See Other is a form post's success, sending the
            # browser on: the change is made, as for any 2xx
            if 200 <= status < 300 or status == 303:
                changes.put(state.get("container", "/"))
        await send(message)

    return announcing_send


def _headers_only(send: Send) -> Send:
    """send for a HEAD: the response's start as it is, then an empty body
    that ends it at the first body message, and nothing after."""
    ended = False

    async def heading(message: Message) -> None:
        nonlocal ended
        if message["type"] == "http.response.start":
            await send(message)
        elif not ended:
            ended = True
            await send({"type": "http.response.body", "body": b"", "more_body": False})

    return heading


def _cache_headers(state: State, result: Any) -> list[tuple[bytes, bytes]] | None:
    """ETag and Cache-Control for a GET of something a file holds: a
    Persist, or below it, a Resource's state, or a built Vite page. None
    for anything else -- what is computed, or held in memory alone."""
    file: Path | None = state.get("etag_file") or file_of(result, state)
    if state.get("method") != "GET" or file is None or not file.exists():
        return None
    return cache_headers(file)


def _with_headers(send: Send, headers: list[tuple[bytes, bytes]]) -> Send:
    """send, with headers added to a 200's start."""

    async def adding_send(message: Message) -> None:
        if message["type"] == "http.response.start" and message["status"] == 200:
            message = {**message, "headers": [*message.get("headers", []), *headers]}
        await send(message)

    return adding_send


def consumers_app(
    root: Any,
    changes: EventSource | None = None,
    data: str | Path = "var/data",
    vite: str | Path | None = None,
) -> ASGIApp:
    """The ASGI app publishing root.

    vite is the directory Vite builds its pages into, for each Page in root
    and for /mumulib-vite/, which is then the app's own, ahead of anything in root:
    in production what Vite built is served from there. With
    MUMULIB_DEVELOPMENT=1 in the environment as the app is made, it is in
    development instead, and a Page is asked of Vite's dev server.

    data is the directory each Located object -- each Resource -- keeps its
    file in, named by its URL: var/data/editors/characters/c1.json. It is
    relative to the directory the app is made in, unless absolute.

    Given changes, an EventSource, every request that changes something --
    a POST, PUT, PATCH or DELETE answered with success -- puts the URL of
    the container it changed on it, without an extension: the nearest
    Located object, a Resource, at or above what was written, or else /.
    The app serves it itself, read-only, at /mumulib/changes.sse, with
    /mumulib/live.js, the script that keeps a page's data-live elements up
    to date by it -- a page made with tags.page(..., live=True) links it.
    """
    data_directory = Path(data).resolve()
    vite_directory = Path(vite).resolve() if vite is not None else None
    development = os.environ.get("MUMULIB_DEVELOPMENT") == "1"
    mumulib = (
        GetOnly({"changes": changes, "live": LIVE_SCRIPT})
        if changes is not None
        else None
    )

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            restore: Callable[[], None] | None = None
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    restore = _close_streams_on_signal(asyncio.get_running_loop())
                    await send({"type": "lifespan.startup.complete"})
                if message["type"] == "lifespan.shutdown":
                    if restore is not None:
                        restore()
                    await send({"type": "lifespan.shutdown.complete"})
                    return

        assert scope["type"] == "http"
        state = scope["state"]
        # HEAD is GET without the body: answered as GET by everything that
        # answers GET, with its status and headers, and only the body held back
        head = scope["method"] == "HEAD"
        if head:
            scope = {**scope, "method": "GET"}
            send = _headers_only(send)
        if scope["method"] not in SAFE and cross_origin(scope):
            await send_error_response(
                send,
                403,
                "Forbidden",
                f"A {scope['method']} from another origin is refused",
            )
            return
        if changes is not None and scope["method"] in MUTATING:
            send = _announce_changes(send, changes, state)

        state["url"] = scope["path"]
        state["method"] = scope["method"]
        state["vite"] = vite_directory
        state["development"] = development
        # Vite's URLs, not the tree's: no extension names their type
        if vite_directory is not None and scope["path"].startswith(VITE_BASE):
            await serve_vite(scope, send, receive, vite_directory, development)
            return
        parsed = split_path(scope["path"])
        content_type = content_type_for(parsed[1]) if parsed else None
        if parsed is None or content_type is None:
            await send_error_response(
                send,
                404,
                "Not Found",
                f"A URL names its type with an extension: {scope['path']}",
            )
            return
        segments, extension = parsed
        # One URL per type: an index is its slash, and never spelled out --
        # not index.html, and not index.json, even at the root
        if segments[-1] == "index" and not scope["path"].endswith("/"):
            await send_error_response(
                send,
                404,
                "Not Found",
                f"An index is its slash, not {scope['path']}",
            )
            return
        state["extension"] = extension
        # Every segment, as the path has them: what was walked to reach an
        # object is these less those remaining, and names its URL
        state["segments"] = segments
        state["data"] = data_directory
        state["content_type"] = content_type
        state["accept"] = [content_type.split(";")[0], "*/*"]

        try:
            for key, value in scope["headers"]:
                if key.lower() == b"content-type":
                    lowervalue = value.lower().split(b";")[0]
                    # How the body is read; what comes back is the URL's
                    if lowervalue == b"application/json":
                        state["parsed_body"] = await parse_json(receive)
                    elif lowervalue == b"application/x-www-form-urlencoded":
                        state["parsed_body"] = await parse_urlencoded(receive)
                    elif lowervalue == b"multipart/form-data":
                        _, options = parse_options_header(value)
                        if b"boundary" not in options:
                            raise ValueError("multipart/form-data with no boundary")
                        state["parsed_body"] = await parse_multipart(
                            receive, options[b"boundary"]
                        )
                    elif scope["method"] in MUTATING:
                        # A write whose body could not be read is refused,
                        # not handed on as though it had none
                        await send_error_response(
                            send,
                            415,
                            "Unsupported Media Type",
                            f"Cannot read a body of {value.decode('latin-1')}",
                        )
                        return
        except BodyTooLarge as exc:
            await send_error_response(send, 413, "Payload Too Large", str(exc))
            return
        except ValueError as exc:
            # Malformed JSON or multipart, or a body that is not UTF-8
            await send_error_response(send, 400, "Bad Request", str(exc))
            return

        try:
            # Given changes, /mumulib/ is the app's own: the change stream
            # and the script that follows it, ahead of anything in root
            if mumulib is not None and segments[0] == "mumulib":
                result = await consume(mumulib, segments[1:], state, send)
            else:
                result = await consume(root, segments, state, send)
        except Exception as exc:
            # Handle errors during request consumption/routing
            traceback.print_exc()
            await send_error_response(send, 500, "Internal Server Error", str(exc))
            return
        # A container's HTML is its slash alone: /todos/, not /todos.html
        if (
            result is not None
            and segments[-1] != "index"
            and content_type.startswith("text/html")
            and is_container(result)
        ):
            result = None
        if result is None:
            await send_error_response(
                send, 404, "Not Found", f"Resource not found: {scope['path']}"
            )
            return

        cache = _cache_headers(state, result)
        if cache is not None:
            if is_fresh(cache[0][1], scope["headers"]):
                await send(
                    {"type": "http.response.start", "status": 304, "headers": cache}
                )
                await send({"type": "http.response.body", "body": b""})
                return
            send = _with_headers(send, cache)

        if isinstance(result, SpecialResponse):
            await send(result.asgi_send_dict)
            result = result.leaf_object
        else:
            first_chunk = True
            try:
                async for chunk in produce(result, state):
                    if first_chunk:
                        if isinstance(chunk, SpecialResponse):
                            # A producer that starts the response itself still
                            # answers with the type the URL asked for
                            await send(
                                with_content_type(chunk.asgi_send_dict, content_type)
                            )
                            leaf = chunk.leaf_object
                            await send(
                                {
                                    "type": "http.response.body",
                                    "body": leaf
                                    if isinstance(leaf, bytes)
                                    else str(leaf).encode("utf8"),
                                    "more_body": True,
                                }
                            )
                            # An event stream's writer never ends by itself
                            if chunk.writer is not None and not head:
                                await chunk.writer(send, receive)
                        else:
                            await send(
                                {
                                    "type": "http.response.start",
                                    "status": 200,
                                    "headers": [
                                        (b"content-type", content_type.encode("utf8"))
                                    ],
                                }
                            )
                            # Handle both str and bytes chunks
                            chunk_bytes = (
                                chunk
                                if isinstance(chunk, bytes)
                                else str(chunk).encode("utf8")
                            )
                            await send(
                                {
                                    "type": "http.response.body",
                                    "body": chunk_bytes,
                                    "more_body": True,
                                }
                            )
                        first_chunk = False
                        if head:
                            # The headers are sent, and nothing after them is:
                            # a producer that never ends is not waited for
                            break
                    else:
                        # Handle both str and bytes chunks
                        chunk_bytes = (
                            chunk
                            if isinstance(chunk, bytes)
                            else str(chunk).encode("utf8")
                        )
                        await send(
                            {
                                "type": "http.response.body",
                                "body": chunk_bytes,
                                "more_body": True,
                            }
                        )
                result = "\n"
            except SpecialResponse as special:
                if first_chunk:
                    await send(special.asgi_send_dict)
                    first_chunk = False
                result = special.leaf_object
            except Exception as exc:
                traceback.print_exc()
                if first_chunk:
                    await send(
                        {
                            "type": "http.response.start",
                            "status": 500,
                            "headers": [
                                (b"content-type", b"application/json; charset=UTF-8")
                            ],
                        }
                    )
                    first_chunk = False
                result = json.dumps(
                    {"error": "Internal Server Error", "message": str(exc)}
                )

        # Ensure result is bytes
        if isinstance(result, str):
            result_bytes = result.encode("utf8")
        elif isinstance(result, bytes):
            result_bytes = result
        else:
            result_bytes = str(result).encode("utf8")

        await send(
            {
                "type": "http.response.body",
                "body": result_bytes,
                "more_body": False,
            }
        )

    return app


# Stands in a stream's buffer for "this stream is over": put when its
# client has fallen too far behind to catch up, or the server is stopping
_CLOSE = object()

# Every event stream open in the process, of every EventSource
_open_streams: set[asyncio.Queue[Any]] = set()


def _close(stream: asyncio.Queue[Any]) -> None:
    """Tell a stream to end: what it has not sent is dropped."""
    while not stream.empty():
        stream.get_nowait()
    stream.put_nowait(_CLOSE)


def _close_streams() -> None:
    """End every open event stream, as the server stops: an event stream
    never ends by itself, and a server waits for open responses to finish."""
    for stream in list(_open_streams):
        _open_streams.discard(stream)
        _close(stream)


def _close_streams_on_signal(loop: asyncio.AbstractEventLoop) -> Callable[[], None]:
    """Chain a SIGINT and SIGTERM handler before the server's own: it ends
    every event stream, then hands the signal on. Returns how to undo it.

    The server's handler -- uvicorn's, set just before the app starts --
    starts its shutdown, which waits for open responses to finish. Streams
    told to end first finish, and the wait is over at once. A signal only
    reaches the main thread, so from any other this does nothing.
    """
    if threading.current_thread() is not threading.main_thread():
        return lambda: None
    previous: dict[int, Any] = {}

    def handler(signum: int, frame: FrameType | None) -> None:
        # A signal handler runs between any two bytecodes, the loop's own
        # included: the streams are ended from the loop, not from here
        loop.call_soon_threadsafe(_close_streams)
        prior = previous[signum]
        if callable(prior):
            prior(signum, frame)
        elif prior != signal.SIG_IGN:
            # The default -- or a handler not set from Python, which is the
            # default's to answer -- for this signal as though we were not here
            signal.signal(signum, signal.SIG_DFL)
            signal.raise_signal(signum)

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous[signum] = signal.signal(signum, handler)

    def restore() -> None:
        for signum, prior in previous.items():
            # Only ours to undo: not if something has since set its own
            if signal.getsignal(signum) is handler:
                signal.signal(signum, prior)

    return restore


class EventSource:
    """Server-sent events, to every client listening: publish it at a .sse
    URL, and each item put on it goes, as JSON, to each stream open at that
    moment.

    Each stream has its own buffer, made when its client connects and dropped
    when it goes, so a client hears what is put after it connects and nothing
    from before. One that falls max_backlog items behind -- stalled, or gone
    without saying so -- is closed rather than buffered for without end; an
    EventSource client reconnects by itself.

    For events meant for one user, publish an EventSource of their own at a
    URL no one else can guess: {"events": {secrets.token_urlsafe(): ...}}.

    put is called from the event loop's thread, as asyncio's queues are.
    """

    def __init__(self, max_backlog: int = 1000) -> None:
        self.max_backlog = max_backlog
        self._streams: set[asyncio.Queue[Any]] = set()

    @property
    def listeners(self) -> int:
        """How many streams are open now."""
        return len(self._streams)

    def put(self, item: Any) -> None:
        """Send item to every stream open now, as JSON.

        A client reads each event's data with JSON.parse, whatever was put:
        a string arrives as a string, quotes and all, and a dict as an
        object. JSON has no raw newline, so an event is always one data:
        line. It is encoded once, here, however many are listening, and
        what has no JSON form raises TypeError here, as at a .json URL.
        """
        data = json.dumps(item, default=custom_serializer)
        for stream in list(self._streams):
            try:
                stream.put_nowait(data)
            except asyncio.QueueFull:
                # Too far behind to catch up: it is told to close
                self._streams.discard(stream)
                _open_streams.discard(stream)
                _close(stream)

    async def stream(self, send: Send, receive: Receive) -> None:
        """One client's stream: its buffer, sent until it goes."""
        buffer: asyncio.Queue[Any] = asyncio.Queue(maxsize=self.max_backlog)
        self._streams.add(buffer)
        _open_streams.add(buffer)
        # One receive for the whole stream, waiting for the client to go.
        # ASGI only promises an awaitable, so ensure_future.
        gone = asyncio.ensure_future(_disconnected(receive))
        item: asyncio.Future[Any] | None = None
        try:
            while True:
                item = asyncio.ensure_future(buffer.get())
                done, _ = await asyncio.wait(
                    {item, gone}, return_when=asyncio.FIRST_COMPLETED
                )
                if gone in done:
                    return
                event = item.result()
                if event is _CLOSE:
                    return
                await send(
                    {
                        "type": "http.response.body",
                        "body": f"data: {event}\n\n".encode(),
                        "more_body": True,
                    }
                )
        finally:
            # Gone, closed, or cancelled -- the server shutting down -- and
            # nothing of this stream's is left waiting
            self._streams.discard(buffer)
            _open_streams.discard(buffer)
            gone.cancel()
            if item is not None:
                item.cancel()


async def _disconnected(receive: Receive) -> None:
    """Returns when the client has gone: what it sends until then, if
    anything, is not for an event stream."""
    while (await receive())["type"] != "http.disconnect":
        pass


async def _produce_eventsource(
    thing: EventSource, state: State
) -> AsyncIterator[SpecialResponse]:
    yield SpecialResponse(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"text/event-stream; charset=UTF-8"),
                (b"cache-control", b"no-cache"),
            ],
        },
        b"event: ping\ndata: {}\n\n",
        thing.stream,
    )


# An event stream is one representation: at .sse, and not found as any other
add_producer(EventSource, _produce_eventsource, "text/event-stream")
