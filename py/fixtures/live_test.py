# pyright: standard
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from fixtures import live
from mumulib.persist import Persist
from mumulib.server import EventSource, consumers_app


class TestLive(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        # Counters and a title of the test's own, the page reading them
        self.counters = {"apples": Persist({"count": 0})}
        root = {"index": live.page, "title": "Fruit", "counters": self.counters}
        self.data = Path(directory.name) / "data"
        self.changes = EventSource()
        self.announced: list[str] = []
        self.changes.put = self.announced.append  # type: ignore[method-assign]
        self.app = consumers_app(root, changes=self.changes, data=self.data)
        # The page asks its counters of the app: this one
        patched = {"root": root, "counters": self.counters, "app": self.app}
        for name, value in patched.items():
            original = getattr(live, name)
            setattr(live, name, value)
            self.addCleanup(setattr, live, name, original)

    def request(self, method, path, body=None):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            data = json.dumps(body).encode() if body is not None else b""
            return {"type": "http.request", "body": data, "more_body": False}

        headers = [(b"content-type", b"application/json")] if body is not None else []
        scope = {"type": "http", "method": method, "path": path, "headers": headers}

        async def go():
            await self.app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        return sent[0]["status"], b"".join(m.get("body", b"") for m in sent[1:])

    def test_each_row_watches_its_counter_and_the_heading_the_page(self):
        status, page = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'<h1 id="title" data-live>', page)
        self.assertIn(b'<li id="apples" data-live="/counters/apples">', page)
        self.assertIn(b'data-url="/counters/apples/count.json" data-value="1"', page)
        self.assertIn(b'<script src="/mumulib/live.js" defer>', page)

    def test_a_counter_is_announced_by_its_own_url(self):
        self.assertEqual(self.request("PUT", "/counters/apples/count.json", 4)[0], 204)
        self.assertEqual(self.announced, ["/counters/apples"])
        self.assertIn(b"<output>4</output>", self.request("GET", "/")[1])

    def test_the_title_is_announced_as_the_root(self):
        self.assertEqual(self.request("PUT", "/title.json", "Veg")[0], 204)
        self.assertEqual(self.announced, ["/"])
        self.assertIn(b"Veg", self.request("GET", "/")[1])

    def test_a_counter_is_read_from_its_file_before_anything_reaches_it(self):
        # As after a restart: a file written by the last run, and a counter
        # no request has reached yet
        (self.data / "counters").mkdir(parents=True)
        (self.data / "counters" / "apples.json").write_text('{"count": 7}')
        self.assertEqual(self.counters["apples"].document, {"count": 0})
        self.assertIn(b"<output>7</output>", self.request("GET", "/")[1])

    def test_the_script_is_served(self):
        status, script = self.request("GET", "/mumulib/live.js")
        self.assertEqual(status, 200)
        self.assertIn(b"data-live", script)
