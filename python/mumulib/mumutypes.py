from typing import Any, Callable, Optional


class SpecialResponse(Exception):
    def __init__(self, asgi_send_dict: dict[str, Any], leaf_object: Any, writer: Optional[Callable[..., Any]] = None) -> None:
        self.asgi_send_dict: dict[str, Any] = asgi_send_dict
        self.leaf_object: Any = leaf_object
        self.writer: Optional[Callable[..., Any]] = writer



class HTTPResponse(SpecialResponse):
    def __init__(self, code: int, body: str) -> None:
        SpecialResponse.__init__(self, {
                    'type': 'http.response.start',
                    'status': code,
                    'headers': [
                        (b'content-type', b'text/plain'),
                    ],
        }, body)


class BadRequestResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 400, 'Bad Request')


class NotFoundResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 404, 'Not Found')


class MethodNotAllowedResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 405, 'Method Not Allowed')


class CreatedResponse(HTTPResponse):
    def __init__(self) -> None:
        HTTPResponse.__init__(self, 201, 'Created')


class SeeOtherResponse(SpecialResponse):
    def __init__(self, redirect_to: str) -> None:
        SpecialResponse.__init__(self, {
                    'type': 'http.response.start',
                    'status': 303,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'location', redirect_to.encode('utf8')),
                    ],
        }, '')

