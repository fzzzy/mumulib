# pyright: standard
import asyncio
import json
import unittest

from examples.functions import app, greet
from mumulib.mumutypes import Message


def request(
    path: str, method: str = "GET", body: bytes = b"", content_type: bytes = b""
) -> tuple[int, bytes, bytes]:
    """The status, Content-Type and body of one request to the example."""
    sent: list[Message] = []

    async def send(message: Message) -> None:
        sent.append(message)

    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    headers = [(b"content-type", content_type)] if content_type else []

    async def go() -> None:
        scope = {"type": "http", "method": method, "path": path, "headers": headers}
        await app({**scope, "state": {}}, receive, send)

    asyncio.run(go())
    content = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], dict(sent[0]["headers"])[b"content-type"], content.strip()


class TestFunctions(unittest.TestCase):
    def test_the_page_is_a_form_that_posts_to_the_function(self):
        status, _, body = request("/")
        self.assertEqual(status, 200)
        self.assertIn(b'action="/greet.html"', body)

    def test_get_calls_it_and_the_url_names_the_type(self):
        self.assertEqual(
            request("/greet.txt"), (200, b"text/plain; charset=UTF-8", b"Hello, world!")
        )
        status, content_type, body = request("/greet.json")
        self.assertEqual(content_type, b"application/json; charset=UTF-8")
        self.assertEqual(json.loads(body), {"greeting": "Hello, world!"})

    def test_post_hands_it_the_body(self):
        _, _, body = request(
            "/greet.json", "POST", b'{"name": "Ada"}', b"application/json"
        )
        self.assertEqual(json.loads(body), {"greeting": "Hello, Ada!"})
        _, _, body = request(
            "/greet.html",
            "POST",
            b"name=Ada",
            b"application/x-www-form-urlencoded",
        )
        self.assertEqual(body, b"<p>Hello, Ada!</p>")

    def test_what_a_visitor_sends_is_escaped_in_html(self):
        _, _, body = request(
            "/greet.html",
            "POST",
            b"name=%3Cscript%3E",
            b"application/x-www-form-urlencoded",
        )
        self.assertEqual(body, b"<p>Hello, &lt;script&gt;!</p>")

    def test_it_is_a_leaf(self):
        self.assertEqual(request("/greet/")[0], 404)
        self.assertEqual(request("/greet/more.txt")[0], 404)

    def test_it_cannot_be_replaced_or_removed(self):
        for method in ("PUT", "DELETE"):
            with self.subTest(method=method):
                status, _, _ = request(
                    "/greet.txt", method, b'"x"', b"application/json"
                )
                self.assertEqual(status, 405)
        self.assertEqual(request("/greet.txt")[2], b"Hello, world!")

    def test_it_is_called_with_the_request(self):
        async def first() -> object:
            async for chunk in greet({"extension": "txt"}):
                return chunk

        self.assertEqual(asyncio.run(first()), "Hello, world!")
