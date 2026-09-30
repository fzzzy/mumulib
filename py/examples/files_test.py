# pyright: standard
import asyncio
import unittest

from examples.files import SITE, app
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
    return sent[0]["status"], headers[b"content-type"], body


class TestFiles(unittest.TestCase):
    def test_the_index_is_the_open_file(self):
        status, content_type, body = get("/")
        self.assertEqual((status, content_type), (200, b"text/html; charset=UTF-8"))
        self.assertTrue(body.startswith((SITE / "index.html").read_bytes()))

    def test_the_directory_serves_its_files_as_their_bytes(self):
        for path, content_type in [
            ("/static/style.css", b"text/css; charset=UTF-8"),
            ("/static/hello.txt", b"text/plain; charset=UTF-8"),
            ("/static/pixel.png", b"image/png"),
        ]:
            with self.subTest(path=path):
                status, got_type, body = get(path)
                self.assertEqual((status, got_type), (200, content_type))
                on_disk = (SITE / path.removeprefix("/")).read_bytes()
                self.assertTrue(body.startswith(on_disk))

    def test_every_link_on_the_page_is_there(self):
        page = (SITE / "index.html").read_text()
        for link in ("/static/style.css", "/static/hello.txt", "/static/pixel.png"):
            with self.subTest(link=link):
                self.assertIn(link, page)
                self.assertEqual(get(link)[0], 200)

    def test_the_directory_lists_itself(self):
        status, content_type, body = get("/static/")
        self.assertEqual((status, content_type), (200, b"text/html; charset=UTF-8"))
        for name in ("hello.txt", "pixel.png", "style.css"):
            self.assertIn(f'<a href="/static/{name}">{name}</a>'.encode(), body)

    def test_nothing_outside_the_directory(self):
        self.assertEqual(get("/static/../files.py")[0], 404)

    def test_nothing_but_get(self):
        self.assertEqual(get("/static/hello.txt", "PUT")[0], 405)
        self.assertEqual(get("/", "DELETE")[0], 405)
