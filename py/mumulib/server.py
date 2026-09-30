import asyncio
import json
import traceback
from collections.abc import AsyncIterator, Callable
from typing import Any
from urllib import parse

from mumulib.consumers import consume, is_container
from mumulib.mumutypes import (
    ASGIApp,
    Receive,
    Scope,
    Send,
    SpecialResponse,
    State,
    content_type_for,
)
from mumulib.producers import produce

# The public API: Publishing an object, and streaming events from it. The body
# parsers and path helpers are the app's own.
__all__ = [
    "consumers_app",
    "EventSource",
]

# Default max request body size: 10MB
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


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
                raise ValueError(
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
                raise ValueError(
                    f"Request body too large: {len(body)} bytes exceeds limit "
                    f"of {max_size} bytes"
                )

            # Check if this is the last body chunk
            if not message.get("more_body", False):
                break
    result: dict[str, Any] = {}
    for k, v in parse.parse_qsl(body.decode("utf-8")):
        k = parse.unquote(k)
        v = parse.unquote(v)
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
                raise ValueError(
                    f"Request body too large: {len(body)} bytes exceeds limit "
                    f"of {max_size} bytes"
                )

            # Check if this is the last body chunk
            if not message.get("more_body", False):
                break
    result: dict[str, Any] = {}
    for part in body.split(boundary):
        if not part or part.strip() == b"--":
            continue
        headers_bytes, content = part.split(b"\r\n\r\n", 1)
        headers = headers_bytes.split(b"\r\n")
        name: bytes | None = None
        for header in headers:
            if header.startswith(b"Content-Disposition:"):
                name = header.split(b";")[1].split(b"=")[1][1:-1]
        if name:
            # Strip trailing \r\n-- or \r\n from content
            stripped_content = content.rstrip(b"-").rstrip(b"\r\n")
            for x in headers:
                if b"Content-Type" in x:
                    result[name.decode("utf-8")] = stripped_content
                    break
            else:
                result[name.decode("utf-8")] = stripped_content.decode("utf-8")
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


def consumers_app(root: Any) -> ASGIApp:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                if message["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return

        assert scope["type"] == "http"

        state = scope["state"]
        state["url"] = scope["path"]
        state["method"] = scope["method"]
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
                        boundary = b"--" + value[len(lowervalue) + 11 :]
                        state["parsed_body"] = await parse_multipart(receive, boundary)
                    else:
                        print(f"Unknown content type: {value}")
        except ValueError as exc:
            # Handle request body size limit errors
            await send_error_response(send, 413, "Payload Too Large", str(exc))
            return

        try:
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
                            if chunk.writer is not None:
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


def EventSource(
    output_queue: asyncio.Queue[Any],
) -> Callable[[State], AsyncIterator[SpecialResponse]]:
    """A function to publish: its URL streams output_queue as server-sent
    events, one for each item put on it, until the client goes."""

    async def handle_eventsource(state: State) -> AsyncIterator[SpecialResponse]:
        async def writer(send: Send, receive: Receive) -> None:
            while True:
                # Create tasks for the ASGI receive and the queue. ASGI only
                # promises an awaitable, so ensure_future rather than
                # create_task, which wants a coroutine.
                task_receive = asyncio.ensure_future(receive())
                task_queue = asyncio.create_task(output_queue.get())

                try:
                    done, _ = await asyncio.wait(
                        {task_receive, task_queue}, return_when=asyncio.FIRST_COMPLETED
                    )
                except asyncio.CancelledError:
                    break
                if task_queue in done:
                    result = done.pop().result()
                    await send(
                        {
                            "type": "http.response.body",
                            "body": f"data: {result}\n\n".encode(),
                            "more_body": True,
                        }
                    )
                else:
                    task_queue.cancel()
                    break

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
            writer,
        )

    return handle_eventsource
