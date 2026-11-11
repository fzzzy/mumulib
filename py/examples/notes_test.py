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
        self.notes = Persist({"one": {"text": "One", "order": "a"}})
        self.presence = notes.Presence()
        root = {
            "index": notes.app_root["index"],
            "notes": self.notes,
            "presence": self.presence,
        }
        with mock.patch.dict(os.environ):
            os.environ.pop("MUMULIB_DEVELOPMENT", None)
            self.app = consumers_app(root, data=base / "data", vite=self.vite)

    def request(self, method, path, body=None, key=None):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            data = json.dumps(body).encode() if body is not None else b""
            return {"type": "http.request", "body": data, "more_body": False}

        headers = [(b"content-type", b"application/json")] if body is not None else []
        if key is not None:
            headers.append((b"authorization", f"Bearer {key}".encode()))
        scope = {"type": "http", "method": method, "path": path, "headers": headers}

        async def go():
            await self.app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        return sent[0]["status"], b"".join(m.get("body", b"") for m in sent[1:])

    def test_the_page_is_the_built_entry(self):
        self.assertEqual(self.request("GET", "/"), (200, b"<h1>Notes</h1>\n"))

    def test_the_notes_are_added_moved_edited_and_removed_as_the_page_does(self):
        two = {"text": "Two", "order": "b"}
        self.assertEqual(self.request("PUT", "/notes/two.json", two)[0], 201)
        # Moved: its order alone written, and no other note touched
        self.assertEqual(self.request("PUT", "/notes/two/order.json", "0V")[0], 204)
        self.assertEqual(self.request("PUT", "/notes/two/text.json", "2")[0], 204)
        self.assertEqual(self.request("DELETE", "/notes/one.json")[0], 204)
        _, body = self.request("GET", "/notes.json")
        self.assertEqual(json.loads(body), {"two": {"text": "2", "order": "0V"}})

    def put(self, player, body, key: str | None = "k"):
        status, answered = self.request(
            "PUT", f"/presence/{player}.json", body, key=key
        )
        return status, json.loads(answered) if status == 200 else answered

    def everyone(self):
        return json.loads(self.request("GET", "/presence.json")[1])

    def test_a_player_is_here_as_the_server_saw_it(self):
        otter = {"name": "Otter", "color": "teal", "focus": "one", "seen": 0}
        with mock.patch("time.time", return_value=100.0):
            status, here = self.put("p7", otter)
        self.assertEqual(status, 200)
        # Seen by the server's clock, whatever the page says; its key not shown
        seen = {"name": "Otter", "color": "teal", "focus": "one", "seen": 100_000}
        self.assertEqual(here, seen)
        self.assertEqual(self.everyone(), {"p7": seen})

    def test_only_its_key_moves_or_removes_a_player(self):
        otter = {"name": "Otter", "color": "teal"}
        self.assertEqual(self.put("p7", otter, key="mine")[0], 200)
        self.assertEqual(self.put("p7", otter, key="mine")[0], 200)
        self.assertEqual(self.put("p7", {**otter, "name": "X"}, key="yours")[0], 403)
        self.assertEqual(self.put("q2", otter, key=None)[0], 401)
        delete = "DELETE", "/presence/p7.json"
        self.assertEqual(self.request(*delete, key="yours")[0], 403)
        self.assertEqual(self.everyone()["p7"]["name"], "Otter")
        self.assertEqual(self.request(*delete, key="mine")[0], 204)
        self.assertEqual(self.request(*delete, key="mine")[0], 404)
        self.assertEqual(self.everyone(), {})

    def test_a_quiet_player_is_forgotten_and_its_key_with_it(self):
        with mock.patch("time.time", return_value=100.0):
            self.put("p7", {"name": "Otter", "color": "teal"}, key="old")
        # A minute on, the otter has gone quiet: forgotten as anyone puts,
        # and its id free for a key of another
        with mock.patch("time.time", return_value=160.0):
            self.put("q2", {"name": "Heron", "color": "coral"})
            self.assertEqual(list(self.everyone()), ["q2"])
            self.assertEqual(
                self.put("p7", {"name": "Wren", "color": "red"}, key="new")[0], 200
            )

    def test_a_player_without_its_parts_is_refused(self):
        self.assertEqual(self.put("p7", {"name": "Otter"})[0], 400)
        self.assertEqual(self.everyone(), {})

    def test_the_app_serves_the_pages_from_ts_build(self):
        self.assertEqual(notes.PAGES.parts[-3:], ("ts", "build", "pages"))
