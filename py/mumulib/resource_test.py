# pyright: standard
import asyncio
import io
import json
import unittest
from types import MappingProxyType

from mumulib.consumers import GetOnly, RefuseIndex
from mumulib.resource import Resource
from mumulib.server import consumers_app
from mumulib.tags import parse_template


def call(root, method, path, body=None):
    """The status, headers and body of one request to root, published."""
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        data = json.dumps(body).encode() if body is not None else b""
        return {"type": "http.request", "body": data, "more_body": False}

    headers = [(b"content-type", b"application/json")] if body is not None else []
    scope = {"type": "http", "method": method, "path": path, "headers": headers}

    async def go():
        await consumers_app(root)({**scope, "state": {}}, receive, send)

    asyncio.run(go())
    content = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], dict(sent[0]["headers"]), content.strip()


class Profile(Resource):
    template = "<h1>A profile</h1>"
    child_name = "Ada"


class Site(Resource):
    child_index = "<h1>Home</h1>"
    child_profile = Profile()
    child_notes = {"a": 1}


class Typed(Resource):
    """Answers each type in its own way, from request."""

    async def handle_GET(self, request):
        if request["extension"] == "json":
            return {"type": request["content_type"]}
        return f"as {request['extension']}"


class Guestbook(Resource):
    """Takes POSTs, and nothing else but GET."""

    def __init__(self):
        super().__init__()
        self.entries = []

    async def handle_GET(self, request):
        return self.entries

    async def handle_POST(self, request):
        self.entries.append(request["parsed_body"])
        return {"count": len(self.entries)}


class TestChildren(unittest.TestCase):
    def test_children_are_child_attributes_walked_into(self):
        root = Site()
        self.assertEqual(call(root, "GET", "/")[2], b"<h1>Home</h1>")
        self.assertEqual(call(root, "GET", "/profile.html")[2], b"<h1>A profile</h1>")
        self.assertEqual(call(root, "GET", "/profile/name.txt")[2], b"Ada")
        # A child is anything publishable: here a dict
        self.assertEqual(json.loads(call(root, "GET", "/notes.json")[2]), {"a": 1})

    def test_only_child_attributes_are_children(self):
        root = Site()
        for path in ("/nothing.html", "/__class__.html", "/render.html", "/profile/"):
            with self.subTest(path=path):
                self.assertEqual(call(root, "GET", path)[0], 404)


class TestRender(unittest.TestCase):
    def test_get_renders_the_template_as_the_urls_type(self):
        root = {"profile": Profile()}
        status, headers, body = call(root, "GET", "/profile.html")
        self.assertEqual((status, body), (200, b"<h1>A profile</h1>"))
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        _, _, body = call(root, "GET", "/profile.json")
        self.assertEqual(json.loads(body), "<h1>A profile</h1>")
        # Its state is a child of its own: none, given none
        _, _, body = call(root, "GET", "/profile/state.json")
        self.assertEqual(json.loads(body), {})

    def test_render_sees_the_type_in_state(self):
        root = {"typed": Typed()}
        self.assertEqual(call(root, "GET", "/typed.txt")[2], b"as txt")
        _, _, body = call(root, "GET", "/typed.json")
        self.assertEqual(json.loads(body), {"type": "application/json; charset=UTF-8"})


class TestMethods(unittest.TestCase):
    def test_every_method_but_get_is_refused_by_default(self):
        root = Site()
        for method in ("HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                status, headers, _ = call(root, method, "/profile.html", "x")
                self.assertEqual(status, 405)
                self.assertEqual(headers[b"allow"], b"GET")

    def test_a_handler_is_called_with_the_request_and_allowed(self):
        book = Guestbook()
        root = Site()
        root.child_book = book  # type: ignore[attr-defined]
        status, _, body = call(root, "POST", "/book.json", {"name": "Ada"})
        self.assertEqual((status, json.loads(body)), (200, {"count": 1}))
        self.assertEqual(book.entries, [{"name": "Ada"}])
        _, _, body = call(root, "GET", "/book.json")
        self.assertEqual(json.loads(body), [{"name": "Ada"}])
        status, headers, _ = call(root, "DELETE", "/book.json")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, POST"))

    def test_a_put_under_a_resource_is_the_resources(self):
        root = Site()
        self.assertEqual(call(root, "PUT", "/profile.html", "x")[0], 405)
        self.assertIsInstance(root.child_profile, Profile)


class Box(Resource):
    """Holds one value, and answers every write to it itself."""

    def __init__(self):
        super().__init__()
        self.value = "empty"
        self.seen = []

    async def handle_GET(self, request):
        return self.value

    async def handle_PUT(self, request):
        self.seen.append("PUT")
        self.value = request["parsed_body"]
        return {"now": self.value}

    async def handle_DELETE(self, request):
        self.seen.append("DELETE")
        self.value = "empty"
        return {"now": self.value}

    async def handle_POST(self, request):
        self.seen.append("POST")
        return {"posted": request["parsed_body"]}

    async def handle_PATCH(self, request):
        self.seen.append("PATCH")
        return {"patched": request["parsed_body"]}


class TestInContainers(unittest.TestCase):
    """A container hands a resource every method at its URL, and writes
    nothing itself: the resource is still there after a PUT or a DELETE."""

    def places(self):
        """(container, root, the resource's URL in it, a way to get it back),
        each with a resource of its own"""
        dict_root = {"box": Box()}
        list_root = {"boxes": ["plain", Box()]}
        tuple_root = {"boxes": ("plain", Box())}
        proxy_root = MappingProxyType({"box": Box()})
        index_root = {"index": Box()}
        return [
            ("dict", dict_root, "/box.json", lambda: dict_root["box"]),
            ("list", list_root, "/boxes/1.json", lambda: list_root["boxes"][1]),
            ("tuple", tuple_root, "/boxes/1.json", lambda: tuple_root["boxes"][1]),
            ("proxy", proxy_root, "/box.json", lambda: proxy_root["box"]),
            # The slash is the index entry, as HTML
            ("index", index_root, "/", lambda: index_root["index"]),
        ]

    def test_every_method_reaches_the_resource(self):
        for name, root, url, entry in self.places():
            box = entry()
            with self.subTest(container=name):
                for method in ("PUT", "POST", "PATCH", "DELETE"):
                    self.assertEqual(call(root, method, url, "full")[0], 200)
                self.assertIs(entry(), box)
                self.assertEqual(box.seen, ["PUT", "POST", "PATCH", "DELETE"])

    def test_the_resource_answers_what_comes_back(self):
        root = {"boxes": [Box()]}
        status, _, body = call(root, "PUT", "/boxes/0.json", "full")
        self.assertEqual((status, json.loads(body)), (200, {"now": "full"}))
        self.assertEqual(json.loads(call(root, "GET", "/boxes/0.json")[2]), "full")
        status, _, body = call(root, "DELETE", "/boxes/0.json")
        self.assertEqual((status, json.loads(body)), (200, {"now": "empty"}))

    def test_what_a_resource_does_not_handle_it_refuses(self):
        root = {"profile": Profile(), "list": [Profile()]}
        for url in ("/profile.json", "/list/0.json"):
            for method in ("PUT", "DELETE"):
                with self.subTest(url=url, method=method):
                    status, headers, _ = call(root, method, url, "replaced")
                    self.assertEqual((status, headers[b"allow"]), (405, b"GET"))
        self.assertIsInstance(root["profile"], Profile)
        self.assertIsInstance(root["list"][0], Profile)

    def test_plain_entries_beside_it_are_still_the_containers(self):
        root = {"box": Box(), "plain": "old", "list": ["a"]}
        self.assertEqual(call(root, "PUT", "/plain.json", "new")[0], 204)
        self.assertEqual(call(root, "PUT", "/list/last.json", "b")[0], 201)
        self.assertEqual(call(root, "PUT", "/fresh.json", "x")[0], 201)
        self.assertEqual(call(root, "DELETE", "/fresh.json")[0], 204)
        self.assertEqual(root["plain"], "new")
        self.assertEqual(root["list"], ["a", "b"])

    def test_a_guard_above_it_still_narrows(self):
        box = Box()
        root = GetOnly({"box": box})
        status, headers, _ = call(root, "PUT", "/box.json", "full")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET"))
        self.assertEqual((box.value, box.seen), ("empty", []))
        # RefuseIndex lets a write through to it, but no container body
        root = RefuseIndex({"box": box})
        self.assertEqual(call(root, "PUT", "/box.json", "full")[0], 200)
        self.assertEqual(call(root, "PUT", "/box.json", {"a": 1})[0], 404)
        self.assertEqual((box.value, box.seen), ("full", ["PUT"]))


class TestRegistration(unittest.TestCase):
    def test_every_subclass_is_registered_as_it_is_defined(self):
        class Deeper(Profile):
            template = "deeper"

        self.assertEqual(call({"d": Deeper()}, "GET", "/d.txt")[2], b"deeper")

    def test_resource_itself_is_registered(self):
        status, _, body = call({"r": Resource()}, "GET", "/r.txt")
        self.assertEqual((status, body), (200, b""))


PAGE = parse_template(
    io.BytesIO(
        b"""<html><body>
<h1 data-slot="title">A title</h1>
<p data-slot="greeting">Hello</p>
<p data-slot="kept">The template's own</p>
<p data-slot="gone">Emptied</p>
<a data-attr="href=link" data-slot="label">a link</a>
<ul data-slot="items"><li data-pat="item"><span data-slot="name">x</span></li></ul>
<div data-slot="listing"></div>
<div data-slot="inner"></div>
</body></html>"""
    )
)


class Card(Resource):
    template = "<b>a card</b>"


class Filled(Resource):
    """A template filled from slot_ methods and values, every kind."""

    template = PAGE
    slot_title = "Slots"

    def __init__(self, names):
        super().__init__()
        self.names = names
        self.called = []

    def slot_greeting(self, request):
        self.called.append("greeting")
        return f"Hello, {request.get('parsed_body') or 'you'}"

    async def slot_label(self, request):
        await asyncio.sleep(0)
        return "<go>"

    def slot_link(self, request):
        return "/elsewhere?a=1&b=2"

    def slot_gone(self, request):
        return None

    def slot_items(self, request):
        return [self.pattern("item", name=name) for name in self.names]

    def slot_name(self, request):
        # Inside the pattern: the pattern's, never the page's
        self.called.append("name")
        return "never"

    def slot_listing(self, request):
        return {"a": 1}

    def slot_inner(self, request):
        return Card()


class TestSlots(unittest.TestCase):
    def setUp(self):
        self.page = Filled(["Ada", "<Bob>"])
        self.root = {"page": self.page}

    def body(self):
        status, _, body = call(self.root, "GET", "/page.html")
        self.assertEqual(status, 200)
        return body.decode()

    def test_each_slot_is_filled_from_its_slot_method_or_value(self):
        body = self.body()
        self.assertIn("Slots", body)
        self.assertIn("Hello, you", body)
        self.assertNotIn("A title", body)

    def test_an_async_slot_is_awaited_and_its_text_escaped(self):
        self.assertIn("&lt;go&gt;", self.body())

    def test_an_attribute_slot_is_filled_and_escaped(self):
        self.assertIn('href="/elsewhere?a=1&amp;b=2"', self.body())

    def test_a_slot_with_no_slot_method_keeps_the_templates(self):
        self.assertIn("The template's own", self.body())

    def test_none_empties_a_slot(self):
        self.assertNotIn("Emptied", self.body())

    def test_a_list_of_pattern_copies_fills_a_slot(self):
        body = self.body()
        self.assertEqual(body.count('data-pat="item"'), 2)
        self.assertIn("Ada", body)
        self.assertIn("&lt;Bob&gt;", body)
        self.assertNotIn("never", body)
        self.assertNotIn("name", self.page.called)

    def test_anything_else_is_the_html_a_producer_makes_of_it(self):
        body = self.body()
        # A dict as its listing, a resource as its own page
        self.assertIn('<a href="/page/a.html">a</a>', body)
        self.assertIn("<b>a card</b>", body)

    def test_a_slot_sees_the_request(self):
        root = {"page": Filled([])}
        Filled.handle_POST = Resource.handle_GET  # type: ignore[method-assign]
        try:
            _, _, body = call(root, "POST", "/page.html", "Ada")
        finally:
            del Filled.handle_POST
        self.assertIn(b"Hello, Ada", body)

    def test_the_template_itself_is_left_as_it_was(self):
        self.body()
        self.body()
        self.assertEqual(self.page.called, ["greeting", "greeting"])
        assert PAGE is not None
        self.assertIn("A title", repr(PAGE))
        self.assertNotIn("Slots", repr(PAGE))

    def test_a_slot_with_no_html_form_is_an_error(self):
        class Broken(Resource):
            template = PAGE

            def slot_title(self, request):
                return object()

        status, _, _ = call({"b": Broken()}, "GET", "/b.html")
        self.assertEqual(status, 500)

    def test_a_pattern_must_be_in_a_parsed_template(self):
        with self.assertRaises(TypeError):
            Card().pattern("item")
        with self.assertRaises(ValueError):
            self.page.pattern("missing")


class TestAsyncHandlers(unittest.TestCase):
    def test_a_handler_may_be_async(self):
        class Later(Resource):
            async def handle_GET(self, request):
                await asyncio.sleep(0)
                return {"later": True}

        _, _, body = call({"l": Later()}, "GET", "/l.json")
        self.assertEqual(json.loads(body), {"later": True})


STATE_PAGE = parse_template(
    io.BytesIO(
        b"""<html><body>
<h1 data-slot="name">A name</h1>
<p data-slot="mood">A mood</p>
<a data-attr="href=link">a link</a>
</body></html>"""
    )
)


class Person(Resource):
    """Filled from its state, but for what a slot_ says instead."""

    template = STATE_PAGE

    def slot_mood(self, request):
        return f"{self.state['name']} is {self.state['mood']}"

    async def handle_POST(self, request):
        self.state.update(request["parsed_body"])
        self.see_other("/people/")


class TestState(unittest.TestCase):
    def setUp(self):
        self.ada = Person({"name": "Ada", "mood": "busy", "link": "/ada?a=1&b=2"})
        self.root = {"people": {"ada": self.ada}}

    def test_a_resource_is_its_state_as_json(self):
        _, _, body = call(self.root, "GET", "/people/ada/state.json")
        self.assertEqual(json.loads(body)["name"], "Ada")
        self.assertEqual(
            call(self.root, "GET", "/people/ada/state/name.txt")[2], b"Ada"
        )
        # And inside other JSON too
        _, _, body = call(self.root, "GET", "/people.json")
        self.assertEqual(json.loads(body), {"ada": self.ada.state})

    def test_the_state_is_read_only_at_every_depth(self):
        for method, path in [
            ("PUT", "/people/ada/state.json"),
            ("DELETE", "/people/ada/state.json"),
            ("PUT", "/people/ada/state/name.json"),
            ("POST", "/people/ada/state/name.json"),
        ]:
            with self.subTest(method=method, path=path):
                status, headers, _ = call(self.root, method, path, "Eve")
                self.assertEqual((status, headers[b"allow"]), (405, b"GET"))
        self.assertEqual(self.ada.state["name"], "Ada")

    def test_a_child_state_of_its_own_is_a_childs(self):
        class Own(Resource):
            child_state = "mine"

        _, _, body = call({"o": Own({"a": 1})}, "GET", "/o/state.txt")
        self.assertEqual(body, b"mine")

    def test_a_slot_is_filled_from_the_state_unless_a_slot_method_says(self):
        _, _, body = call(self.root, "GET", "/people/ada.html")
        self.assertIn(b"Ada", body)
        self.assertIn(b"Ada is busy", body)
        self.assertIn(b'href="/ada?a=1&amp;b=2"', body)

    def test_with_no_state_the_template_keeps_its_own(self):
        class Bare(Resource):
            template = STATE_PAGE

        _, _, body = call({"p": Bare()}, "GET", "/p.html")
        self.assertIn(b"A name", body)

    def test_see_other_answers_a_post_with_where_to_go(self):
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"mood=done", "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/people/ada.html",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "state": {},
        }

        async def go():
            await consumers_app(self.root)(scope, receive, send)

        asyncio.run(go())
        self.assertEqual(sent[0]["status"], 303)
        self.assertEqual(dict(sent[0]["headers"])[b"location"], b"/people/")
        self.assertEqual(self.ada.state["mood"], "done")
