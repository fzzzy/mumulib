from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

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
