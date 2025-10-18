from typing import Any, Callable

class SpecialResponse(Exception):
    asgi_send_dict: dict[str, Any]
    leaf_object: Any
    writer: Callable[..., Any] | None
    def __init__(self, asgi_send_dict: dict[str, Any], leaf_object: Any, writer: Callable[..., Any] | None = None) -> None: ...

class HTTPResponse(SpecialResponse):
    def __init__(self, code: int, body: str) -> None: ...

class BadRequestResponse(HTTPResponse):
    def __init__(self) -> None: ...

class NotFoundResponse(HTTPResponse):
    def __init__(self) -> None: ...

class MethodNotAllowedResponse(HTTPResponse):
    def __init__(self) -> None: ...

class CreatedResponse(HTTPResponse):
    def __init__(self) -> None: ...

class SeeOtherResponse(SpecialResponse):
    def __init__(self, redirect_to: str) -> None: ...
