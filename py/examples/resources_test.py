# pyright: standard
import asyncio
import json
import unittest
from typing import Any
from unittest import mock

from examples import resources
from mumulib.mumutypes import Message


class TestResources(unittest.TestCase):
    def setUp(self):
        # A site of its own for each test, so writes do not leak between them
        self.site = resources.Site()
        self.changes = resources.EventSource()
        self.app = resources.consumers_app(self.site, changes=self.changes)

    def request(
        self, path: str, method: str = "GET", body: object = None, form: bytes = b""
    ) -> tuple[int, dict[bytes, bytes], bytes]:
        """The status, headers and body of one request to the example."""
        sent: list[Message] = []

        async def send(message: Message) -> None:
            sent.append(message)

        if form:
            data, content_type = form, b"application/x-www-form-urlencoded"
        elif body is not None:
            data, content_type = json.dumps(body).encode(), b"application/json"
        else:
            data, content_type = b"", b""

        async def receive() -> Message:
            return {"type": "http.request", "body": data, "more_body": False}

        headers = [(b"content-type", content_type)] if content_type else []

        async def go() -> None:
            scope = {"type": "http", "method": method, "path": path, "headers": headers}
            await self.app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        content = b"".join(m.get("body", b"") for m in sent[1:])
        return sent[0]["status"], dict(sent[0]["headers"]), content.strip()

    def json(self, path: str, method: str = "GET", body: object = None) -> Any:
        status, _, content = self.request(path, method, body)
        self.assertEqual(status, 200, content)
        return json.loads(content)

    def test_the_page_is_the_roots_child_index(self):
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        self.assertIn(b'action="/todos.html"', body)

    def test_a_template_is_all_about_needs(self):
        status, _, body = self.request("/about.txt")
        self.assertEqual(
            (status, body), (200, b"A to-do list, published as resources.")
        )
        status, headers, _ = self.request("/about.txt", "POST", "x")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET"))

    def test_the_list_answers_by_the_urls_type(self):
        self.assertEqual(
            self.json("/todos.json"),
            [
                {
                    "text": "Write the example",
                    "done": False,
                    "url": "/todos/items/0.json",
                },
                {"text": "Test it", "done": False, "url": "/todos/items/1.json"},
            ],
        )
        _, _, body = self.request("/todos.html")
        # The page's pattern, filled once for each item, and nothing else
        self.assertEqual(body.count(b'data-pat="item"'), 2)
        self.assertIn(b'href="/todos/items/1.html"', body)
        self.assertIn(b"Test it", body)
        self.assertNotIn(b"An item", body)

    def test_each_item_has_a_checkbox_for_its_own_url(self):
        self.request("/todos/items/1.json", "PUT", {"done": True})
        _, _, body = self.request("/todos.html")
        # checked when done, and left out when not
        self.assertIn(b'data-url="/todos/items/0.json" />', body)
        self.assertIn(b'data-url="/todos/items/1.json" checked />', body)
        # And the page's script to PUT what it is set to
        self.assertIn(b'method: "PUT"', body)

    def test_the_template_is_filled_afresh_each_time(self):
        self.request("/todos.html")
        self.request("/todos.json", "POST", {"text": "Milk"})
        _, _, body = self.request("/todos.html")
        self.assertEqual(body.count(b'data-pat="item"'), 3)
        # An empty list is an empty <ul>
        site = resources.Site()
        site.child_todos = resources.Todos()
        self.app = resources.consumers_app(site)
        _, _, body = self.request("/todos.html")
        self.assertIn(b'<ul id="items" data-live="/todos" data-slot="items">', body)
        self.assertNotIn(b"<li", body)

    def test_post_adds_one_and_says_where(self):
        self.assertEqual(
            self.json("/todos.json", "POST", {"text": "Milk"}),
            {"url": "/todos/items/2.json"},
        )
        self.assertEqual(
            self.json("/todos/items/2.json"), {"text": "Milk", "done": False}
        )

    def test_the_form_posts_and_gets_the_list_back(self):
        status, _, body = self.request("/todos.html", "POST", form=b"text=%3Cb%3E")
        self.assertEqual(status, 200)
        # Escaped: what a visitor sends is never markup
        self.assertIn(b"&lt;b&gt;", body)
        self.assertNotIn(b"<b>", body)

    def test_a_put_is_the_items_own_and_changes_it_in_place(self):
        # The site at hand, to see the Todo object is changed, not replaced
        site = resources.Site()
        self.app = resources.consumers_app(site)
        todo = site.child_todos.child_items[0]
        self.assertEqual(
            self.json("/todos/items/0.json", "PUT", {"done": True}),
            {"text": "Write the example", "done": True},
        )
        self.assertIs(site.child_todos.child_items[0], todo)
        self.assertTrue(todo.done)

    def test_an_item_checks_what_it_is_sent(self):
        for body in ({}, {"done": "yes"}, {"text": 3}, "replaced", ["x"]):
            with self.subTest(body=body):
                status, _, _ = self.request("/todos/items/0.json", "PUT", body)
                self.assertEqual(status, 400)
        self.assertEqual(
            self.json("/todos/items/0.json"),
            {"text": "Write the example", "done": False},
        )

    def test_an_item_cannot_be_removed(self):
        status, headers, _ = self.request("/todos/items/0.json", "DELETE")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, PUT"))
        self.assertEqual(len(self.json("/todos.json")), 2)

    def test_the_items_are_listed_at_their_slash(self):
        status, _, body = self.request("/todos/items/")
        self.assertEqual(status, 200)
        self.assertIn(b'<a href="/todos/items/0.html">0</a>', body)
        status, _, body = self.request("/todos/items/0.html")
        self.assertEqual((status, body), (200, b"<p>Write the example (to do)</p>"))

    def test_a_post_without_text_is_refused(self):
        for body in ({}, {"text": ""}, {"text": 1}):
            with self.subTest(body=body):
                self.assertEqual(self.request("/todos.json", "POST", body)[0], 400)
        self.assertEqual(len(self.json("/todos.json")), 2)

    def test_every_change_is_put_on_the_sites_changes(self):
        with mock.patch.object(self.changes, "put") as put:
            self.request("/todos/items/1.json", "PUT", {"done": True})
            self.request("/todos.json", "POST", {"text": "Milk"})
            self.request("/todos.html", "POST", form=b"text=Eggs")
            # And nothing for what changed nothing
            self.request("/todos/items/0.json", "DELETE")
            self.request("/todos/items/0.json", "PUT", "replaced")
            self.request("/todos.json")
        heard = [call.args[0] for call in put.call_args_list]
        self.assertEqual(heard, ["/todos/items/1", "/todos", "/todos"])

    def test_the_list_and_each_item_are_live(self):
        _, _, body = self.request("/todos.html")
        self.assertIn(b'<script src="/mumulib/live.js" defer="defer">', body)
        # The list watches /todos, which adding announces; each item its own
        self.assertIn(b'<ul id="items" data-live="/todos"', body)
        self.assertIn(b'id="item-1" data-live="/todos/items/1"', body)
        # And consumers_app serves both, being given changes
        self.assertEqual(self.request("/mumulib/live.js")[0], 200)
        self.assertEqual(self.request("/changes.sse")[0], 404)
