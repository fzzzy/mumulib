# pyright: standard
import asyncio
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

    def test_the_root_has_no_other_name(self):
        # Its slash is its one URL; index spelled out is no name at all
        for path in ("/index.html", "/index.txt", "/index.json"):
            with self.subTest(path=path):
                self.assertEqual(get(path)[0], 404)

    def test_there_is_nothing_else(self):
        self.assertEqual(get("/other.html")[0], 404)
        self.assertEqual(get("/index")[0], 404)
        self.assertEqual(get("/other.json")[0], 404)

    def test_nothing_but_get_gets_in(self):
        for method in ("PUT", "DELETE", "POST", "PATCH", "HEAD"):
            with self.subTest(method=method):
                status, _, body = get("/", method)
                self.assertEqual((status, body), (405, b"Only GET"))
        # and nothing was changed on the way
        self.assertEqual(get("/")[2], b"Hello, world!")
