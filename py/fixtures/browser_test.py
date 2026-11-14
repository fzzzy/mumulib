# pyright: standard
import asyncio
import unittest

from fixtures.browser import app


def get(path: str) -> tuple[int, bytes]:
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": "GET", "path": path, "headers": []}
    asyncio.run(app({**scope, "state": {}}, receive, send))
    return sent[0]["status"], b"".join(m.get("body", b"") for m in sent[1:])


class TestBrowser(unittest.TestCase):
    def test_the_page_imports_the_library_from_the_server(self):
        status, page = get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'from "/mumulib/browser/mumulib.mjs"', page)

    def test_the_page_is_the_only_thing_of_its_own(self):
        self.assertEqual(get("/other.html")[0], 404)
