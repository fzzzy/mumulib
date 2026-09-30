# pyright: standard
import asyncio
import json
import unittest

from examples.hello import app
from mumulib.mumutypes import Message


def get(path: str, method: str = "GET") -> tuple[int, bytes, bytes]:
    """The status, Content-Type and body of one request to the example."""
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    async def receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def request() -> None:
        scope = {"type": "http", "method": method, "path": path, "headers": []}
        await app({**scope, "state": {}}, receive, send)

    asyncio.run(request())
    headers = dict(sent[0]["headers"])
    body = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], headers[b"content-type"], body.strip()


class TestHello(unittest.TestCase):
    def test_the_site_is_the_string(self):
        self.assertEqual(get("/"), (200, b"text/html; charset=UTF-8", b"Hello, world!"))

    def test_the_extension_is_the_type(self):
        self.assertEqual(
            get("/index.txt"), (200, b"text/plain; charset=UTF-8", b"Hello, world!")
        )
        status, content_type, body = get("/index.json")
        self.assertEqual(
            (status, content_type), (200, b"application/json; charset=UTF-8")
        )
        self.assertEqual(json.loads(body), "Hello, world!")

    def test_there_is_nothing_else(self):
        self.assertEqual(get("/other.html")[0], 404)
        self.assertEqual(get("/index")[0], 404)

    def test_nothing_but_get_gets_in(self):
        for method in ("PUT", "DELETE", "POST", "PATCH", "HEAD"):
            with self.subTest(method=method):
                status, _, body = get("/index.json", method)
                self.assertEqual((status, body), (405, b"Only GET"))
        # and nothing was changed on the way
        self.assertEqual(get("/")[2], b"Hello, world!")
