import mimetypes
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

# The public API: The ASGI shapes mumulib's signatures use, the responses a
# consumer or producer can return or raise, and the extension-to-type rule.
__all__ = [
    "Message",
    "Scope",
    "Receive",
    "Send",
    "ASGIApp",
    "State",
    "Writer",
    "Chunk",
    "Consumer",
    "Producer",
    "SpecialResponse",
    "HTTPResponse",
    "BadRequestResponse",
    "NotFoundResponse",
    "MethodNotAllowedResponse",
    "CreatedResponse",
    "SeeOtherResponse",
    "CONTENT_TYPES",
    "content_type_for",
]

# ASGI, as far as mumulib uses it. Messages and scopes are plain dicts whose
# keys depend on their "type", so their values stay Any.
type Message = dict[str, Any]
type Scope = dict[str, Any]
type Receive = Callable[[], Awaitable[Message]]
type Send = Callable[[Message], Awaitable[None]]
type ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

# Per-request state shared by the consumers and producers: "method", "url",
# "accept", "parsed_body", "remaining".
type State = dict[str, Any]

# Streams the rest of a response after a SpecialResponse has started it.
type Writer = Callable[[Send, Receive], Awaitable[None]]


# What a producer yields: text, raw bytes, or a SpecialResponse that sets the
# status and headers itself.
type Chunk = str | bytes | SpecialResponse

# A consumer resolves one step of a path: (parent, segments, state, send).
type Consumer = Callable[[Any, list[str], State, Send], Awaitable[Any]]

# A producer renders an object as a stream of chunks: (thing, state).
type Producer = Callable[[Any, State], AsyncIterator[Chunk]]


class SpecialResponse(Exception):
    def __init__(
        self,
        asgi_send_dict: dict[str, Any],
        leaf_object: Any,
        writer: Writer | None = None,
    ) -> None:
        self.asgi_send_dict: dict[str, Any] = asgi_send_dict
        self.leaf_object: Any = leaf_object
        self.writer: Writer | None = writer


class HTTPResponse(SpecialResponse):
    def __init__(self, code: int, body: str) -> None:
        SpecialResponse.__init__(
            self,
            {
                "type": "http.response.start",
                "status": code,
                "headers": [
                    (b"content-type", b"text/plain"),
                ],
            },
            body,
        )


class BadRequestResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 400, "Bad Request")


class NotFoundResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 404, "Not Found")


class MethodNotAllowedResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 405, "Method Not Allowed")


class CreatedResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 201, "Created")


class SeeOtherResponse(SpecialResponse):
    def __init__(self, redirect_to: str) -> None:
        SpecialResponse.__init__(
            self,
            {
                "type": "http.response.start",
                "status": 303,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"location", redirect_to.encode("utf8")),
                ],
            },
            "",
        )


# The type of every response is the one its URL's extension names, and
# nothing else: not the request's headers, so no response varies by them.
# These are the extensions mumulib's producers speak; any other goes through
# mimetypes, and one with no type there is not found.
CONTENT_TYPES = {
    "json": "application/json",
    "html": "text/html",
    "txt": "text/plain",
    "sse": "text/event-stream",
}


def content_type_for(extension: str) -> str | None:
    """The Content-Type an extension names, charset and all, or None."""
    extension = extension.lower()
    mime = CONTENT_TYPES.get(extension) or mimetypes.types_map.get(f".{extension}")
    if mime is None:
        return None
    if mime.startswith("text/") or mime in ("application/json", "text/javascript"):
        return f"{mime}; charset=UTF-8"
    return mime
