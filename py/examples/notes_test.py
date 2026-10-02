# pyright: standard
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from examples import notes
from mumulib.persist import Persist
from mumulib.server import consumers_app


class TestNotes(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        base = Path(directory.name).resolve()
        # A build of the page, as make pages makes one, and notes of the
        # test's own, kept in its own data directory
        self.vite = base / "build"
        (self.vite / "notes").mkdir(parents=True)
        (self.vite / "notes" / "index.html").write_text("<h1>Notes</h1>")
        self.notes = Persist(["One"])
        root = {"index": notes.app_root["index"], "notes": self.notes}
        with mock.patch.dict(os.environ):
            os.environ.pop("MUMULIB_DEVELOPMENT", None)
            self.app = consumers_app(root, data=base / "data", vite=self.vite)

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

    def test_the_page_is_the_built_entry(self):
        self.assertEqual(self.request("GET", "/"), (200, b"<h1>Notes</h1>\n"))

    def test_the_notes_are_added_and_removed_as_the_page_does(self):
        self.assertEqual(self.request("PUT", "/notes/last.json", "Two")[0], 201)
        self.assertEqual(self.request("DELETE", "/notes/0.json")[0], 204)
        _, body = self.request("GET", "/notes.json")
        self.assertEqual(json.loads(body), [None, "Two"])

    def test_the_app_serves_the_pages_from_ts_build(self):
        self.assertEqual(notes.PAGES.parts[-3:], ("ts", "build", "pages"))
