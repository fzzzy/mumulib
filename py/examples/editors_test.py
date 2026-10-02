# pyright: standard
import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import urlencode

from examples import editors
from mumulib.mumutypes import Message


class TestEditors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # An app of the tests' own, keeping its files where nothing else does
        cls.directory = tempfile.TemporaryDirectory()
        cls.data = Path(cls.directory.name).resolve()
        cls.app = editors.consumers_app(
            {"editors": editors.Site()}, changes=editors.changes, data=cls.data
        )

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        # Each test's writes undone after it: the states as they were
        self.saved = [
            (thing, copy.deepcopy(thing.state))
            for kind in (editors.characters, editors.parties, editors.deploys)
            for thing in kind.values()
        ]

    def tearDown(self):
        for thing, state in self.saved:
            thing.state.clear()
            thing.state.update(state)

    def request(self, path: str, method: str = "GET", form: Any = None):
        """The status, headers and body of one request, a form posted if given."""
        sent: list[Message] = []
        data = urlencode(form, doseq=True).encode() if form is not None else b""

        async def send(message: Message) -> None:
            sent.append(message)

        async def receive() -> Message:
            return {"type": "http.request", "body": data, "more_body": False}

        headers = (
            [(b"content-type", b"application/x-www-form-urlencoded")]
            if form is not None
            else []
        )

        async def go() -> None:
            scope = {"type": "http", "method": method, "path": path, "headers": headers}
            await type(self).app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        content = b"".join(m.get("body", b"") for m in sent[1:]).decode()
        return sent[0]["status"], dict(sent[0]["headers"]), content

    def page(self, path: str) -> str:
        status, _, content = self.request(path)
        self.assertEqual(status, 200, content)
        return content

    def post(self, path: str, form: Any) -> int:
        status, headers, _ = self.request(path, "POST", form)
        if status == 303:
            self.assertEqual(headers[b"location"], b"/editors/")
        return status

    def test_the_index_is_a_table_of_each_kind(self):
        index = self.page("/editors/")
        self.assertTrue(index.startswith("<!doctype html>"))
        for path in (
            "/editors/characters/c1.html",
            "/editors/parties/p2.html",
            "/editors/deploys/d1.html",
        ):
            self.assertIn(f'href="{path}"', index)
        # Ids shown by name: a party's members, a deploy's party
        self.assertIn("Code Reviewer, Researcher", index)
        self.assertIn("Operators", index)

    def test_every_page_links_the_stylesheet_it_is_served(self):
        for page in ("/editors/", "/editors/deploys/d1.html"):
            content = self.page(page)
            self.assertIn(
                '<link rel="stylesheet" href="/editors/style.css" />', content
            )
        status, headers, css = self.request("/editors/style.css")
        self.assertEqual(
            (status, headers[b"content-type"]), (200, b"text/css; charset=UTF-8")
        )
        self.assertIn("border-collapse", css)

    def test_every_page_is_live_by_mumulibs_script(self):
        index = self.page("/editors/")
        self.assertIn('<script src="/mumulib/live.js" defer>', index)
        # Each row watches its own object
        for kind, key in (("characters", "c1"), ("parties", "p2"), ("deploys", "d1")):
            self.assertIn(f'id="{kind}-{key}" data-live="/editors/{kind}/{key}"', index)
        # An edit page's heading watches the page's own URL: no value
        edit = self.page("/editors/characters/c1.html")
        self.assertIn('<script src="/mumulib/live.js" defer>', edit)
        self.assertIn('<h1 id="heading" data-slot="name" data-live>', edit)
        self.assertIn("Code Reviewer", edit)
        # consumers_app serves both, being given changes
        status, headers, js = self.request("/mumulib/live.js")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/javascript; charset=UTF-8")
        self.assertIn("new EventSource('/mumulib/changes.sse')", js)

    def test_each_kind_is_its_states_as_json(self):
        _, _, body = self.request("/editors/parties.json")
        self.assertEqual(json.loads(body)["p1"]["members"], ["c1", "c2"])
        _, _, body = self.request("/editors/deploys/d1.json")
        self.assertEqual(json.loads(body)["status"], "running")

    def test_an_edit_page_is_a_form_filled_from_the_state(self):
        form = self.page("/editors/characters/c2.html")
        self.assertIn('action="/editors/characters/c2.html"', form)
        self.assertIn('value="Researcher"', form)
        self.assertIn("You find sources", form)
        party = self.page("/editors/parties/p1.html")
        self.assertIn('<option value="c1" selected>', party)
        self.assertIn('<option value="c3">', party)
        deploy = self.page("/editors/deploys/d2.html")
        self.assertIn('<option value="p2" selected>', deploy)
        self.assertIn("stopped", deploy)

    def test_a_character_is_posted_and_kept(self):
        status = self.post(
            "/editors/characters/c1.html",
            {"name": "<Renamed>", "prompt": "p", "agent_args": "--x"},
        )
        self.assertEqual(status, 303)
        self.assertEqual(
            editors.characters["c1"].state,
            {"name": "<Renamed>", "prompt": "p", "agent_args": "--x"},
        )
        # Escaped on every page it is shown on
        self.assertIn("&lt;Renamed&gt;", self.page("/editors/"))
        # And saved, in a file named by its URL, for the next start
        saved = self.data / "editors" / "characters" / "c1.json"
        self.assertEqual(json.loads(saved.read_text())["name"], "<Renamed>")

    def test_a_new_start_begins_from_the_files(self):
        self.post("/editors/parties/p2.html", {"name": "Kept", "members[]": ["c1"]})
        # Another process: objects made as editors.py makes them, the same
        # data directory
        party = editors.Party({"name": "Operators", "members": ["c3"]})
        app = editors.consumers_app(
            {"editors": {"parties": {"p2": party}}}, data=self.data
        )

        async def go() -> None:
            async def receive() -> Message:
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message: Message) -> None:
                pass

            scope = {"type": "http", "method": "GET", "headers": []}
            path = "/editors/parties/p2.json"
            await app({**scope, "path": path, "state": {}}, receive, send)

        asyncio.run(go())
        self.assertEqual(party.state, {"name": "Kept", "members": ["c1"]})

    def test_a_partys_members_are_a_list_and_may_be_none(self):
        self.post("/editors/parties/p1.html", {"name": "R", "members[]": ["c1", "c3"]})
        self.assertEqual(editors.parties["p1"].state["members"], ["c1", "c3"])
        self.post("/editors/parties/p1.html", {"name": "R"})
        self.assertEqual(editors.parties["p1"].state["members"], [])

    def test_a_deploy_takes_a_name_and_a_party_and_never_a_status(self):
        status = self.post(
            "/editors/deploys/d1.html",
            {"name": "Weekly", "party": "p2", "status": "stopped"},
        )
        self.assertEqual(status, 303)
        self.assertEqual(
            editors.deploys["d1"].state,
            {"name": "Weekly", "party": "p2", "status": "running"},
        )

    def test_what_does_not_make_sense_is_refused_and_nothing_kept(self):
        for path, form in [
            ("/editors/characters/c1.html", {"name": " "}),
            ("/editors/parties/p1.html", {"name": "x", "members[]": ["c9"]}),
            ("/editors/parties/p1.html", {"members[]": ["c1"]}),
            ("/editors/deploys/d1.html", {"name": "x", "party": "nowhere"}),
            ("/editors/deploys/d1.html", {"party": "p1"}),
        ]:
            with self.subTest(path=path, form=form):
                self.assertEqual(self.post(path, form), 400)
        self.assertEqual(editors.characters["c1"].state["name"], "Code Reviewer")
        self.assertEqual(editors.deploys["d1"].state["name"], "Nightly review")

    def test_nothing_else_is_answered(self):
        self.assertEqual(self.request("/editors/characters/c9.html")[0], 404)
        self.assertEqual(self.request("/editors/characters/c1.html", "PUT")[0], 405)

    def test_each_post_that_changes_something_is_announced(self):
        with mock.patch.object(editors.changes, "put") as put:
            self.post("/editors/characters/c2.html", {"name": "x"})
            self.post("/editors/deploys/d2.html", {"name": "y", "party": "p1"})
            self.post("/editors/deploys/d2.html", {"name": "z", "party": "p9"})
        self.assertEqual(
            [call.args[0] for call in put.call_args_list],
            ["/editors/characters/c2", "/editors/deploys/d2"],
        )
