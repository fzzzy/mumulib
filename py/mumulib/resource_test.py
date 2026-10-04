# pyright: standard
import asyncio
import io
import json
import tempfile
import unittest
import unittest.mock
from pathlib import Path
from types import MappingProxyType

from mumulib import static
from mumulib.consumers import GetOnly, RefuseIndex
from mumulib.resource import Resource
from mumulib.server import consumers_app
from mumulib.tags import Markup, parse_template


def call(root, method, path, body=None, data: str | Path = "var/data"):
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
        await consumers_app(root, data=data)({**scope, "state": {}}, receive, send)

    asyncio.run(go())
    content = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], dict(sent[0]["headers"]), content.strip()


class Profile(Resource):
    template = "<h1>A profile</h1>"
    child_name = "Ada"


class Site(Resource):
    child_index = Markup("<h1>Home</h1>")
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
        # A template is HTML, and only HTML: as anything else, not found
        for path in ("/profile.txt", "/profile.css"):
            self.assertEqual(call(root, "GET", path)[0], 404)
        # As JSON it is its state: none, given none
        _, _, body = call(root, "GET", "/profile.json")
        self.assertEqual(json.loads(body), {})

    def test_render_sees_the_type_in_state(self):
        root = {"typed": Typed()}
        self.assertEqual(call(root, "GET", "/typed.txt")[2], b"as txt")
        _, _, body = call(root, "GET", "/typed.json")
        self.assertEqual(json.loads(body), {"type": "application/json; charset=UTF-8"})


class TestMethods(unittest.TestCase):
    def test_every_method_but_get_and_head_is_refused_by_default(self):
        root = Site()
        for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
            with self.subTest(method=method):
                status, headers, _ = call(root, method, "/profile.html", "x")
                self.assertEqual(status, 405)
                self.assertEqual(headers[b"allow"], b"GET, HEAD")

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
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, HEAD, POST"))

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
                    self.assertEqual((status, headers[b"allow"]), (405, b"GET, HEAD"))
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
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, HEAD"))
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

        self.assertEqual(call({"d": Deeper()}, "GET", "/d.html")[2], b"deeper")

    def test_a_template_of_anything_else_is_its_html(self):
        class Listed(Resource):
            template = {"a": 1}

        status, _, body = call({"l": Listed()}, "GET", "/l.html")
        self.assertEqual(status, 200)
        self.assertIn(b"<ul>", body)

    def test_resource_itself_is_registered(self):
        status, _, body = call({"r": Resource()}, "GET", "/r.html")
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
        # A dict as its listing -- its text linked as text -- and a resource
        # as its own page
        self.assertIn('<a href="/page/a.txt">a</a>', body)
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

    def test_a_slot_with_no_html_form_is_an_err(self):
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
        _, _, body = call(self.root, "GET", "/people/ada.json")
        self.assertEqual(json.loads(body)["name"], "Ada")
        # At its own URL, and nowhere else: no child state, nor below it
        for path in ("/people/ada/state.json", "/people/ada/state/name.txt"):
            with self.subTest(path=path):
                self.assertEqual(call(self.root, "GET", path)[0], 404)
        # Inside a plain container, the URL of its own, for a client to bind
        _, _, body = call(self.root, "GET", "/people.json")
        self.assertEqual(json.loads(body), {"ada": "/people/ada.json"})

    def test_a_plain_container_lists_each_resource_by_where_it_is(self):
        root = {"site": {"kept": [Person(), None], "deep": {"x": Person()}, "n": 1}}
        _, _, body = call(root, "GET", "/site.json")
        self.assertEqual(
            json.loads(body),
            {
                "kept": ["/site/kept/0.json", None],
                "deep": {"x": "/site/deep/x.json"},
                "n": 1,
            },
        )

    def test_its_state_holds_no_resource_or_persist(self):
        holder = Person({"friend": Person()})
        with unittest.mock.patch("traceback.print_exc"):
            status, _, _ = call({"h": holder}, "GET", "/h.json")
        self.assertEqual(status, 500)

    def test_the_state_is_written_by_its_handlers_alone(self):
        # Its own URL is its own to answer: refused, with no handler
        for method in ("PUT", "DELETE"):
            with self.subTest(method=method):
                status, headers, _ = call(self.root, method, "/people/ada.json", "Eve")
                self.assertEqual(status, 405)
                self.assertNotIn(b"PUT", headers[b"allow"])
        # And nothing below it is the state's
        status, _, _ = call(self.root, "PUT", "/people/ada/name.json", "Eve")
        self.assertEqual(status, 404)
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


class Signup(Resource):
    """A form posting to its own page, read with form()."""

    template = parse_template(
        io.BytesIO(
            b"""<html><body><form data-attr="action=url" method="post">
<input name="name"></form></body></html>"""
        )
    )

    async def handle_POST(self, request):
        form = self.form(request)
        self.state.update(name=form.text("name"), tags=form.texts("tags"))
        self.see_other("/done")


class TestForms(unittest.TestCase):
    def test_a_form_posts_to_its_own_page_by_the_url_slot(self):
        _, _, body = call({"signup": Signup()}, "GET", "/signup.html")
        self.assertIn(b'action="/signup.html"', body)

    def test_a_subclass_url_slot_is_its_own(self):
        class Elsewhere(Signup):
            def slot_url(self, request):
                return "/other"

        _, _, body = call({"s": Elsewhere()}, "GET", "/s.html")
        self.assertIn(b'action="/other"', body)

    def test_form_reads_text_and_lists_by_name(self):
        form = Resource().form(
            {
                "parsed_body": {
                    "name": "  Ada ",
                    "tags[]": ["a", "b"],
                    "one": "x",
                    "n": 3,
                }
            }
        )
        self.assertEqual(form.text("name"), "Ada")
        self.assertEqual(form.text("missing"), "")
        self.assertEqual(form.text("n"), "")
        self.assertEqual(form.texts("tags"), ["a", "b"])
        self.assertEqual(form.texts("one"), ["x"])
        self.assertEqual(form.texts("none"), [])
        # Nothing posted, or not an object, is an empty form
        self.assertEqual(Resource().form({}).text("name"), "")
        self.assertEqual(Resource().form({"parsed_body": [1]}).texts("x"), [])


class TestItsUrl(unittest.TestCase):
    def test_a_resource_learns_its_url_when_first_reached(self):
        profile, home = Profile(), Resource()
        root = {"people": {"ada": profile}, "home": {"index": home}}
        self.assertIsNone(profile.url)
        call(root, "GET", "/people/ada.html")
        self.assertEqual(profile.url, "/people/ada")
        # Every type of it, and below it, is the same URL
        for path in ("/people/ada.html", "/people/ada.json"):
            self.assertEqual(call(root, "GET", path)[0], 200)
        call(root, "PUT", "/people/ada.json", {})
        self.assertEqual(profile.url, "/people/ada")
        # An index is its container's slash
        call(root, "GET", "/home/")
        self.assertEqual(home.url, "/home/")

    def test_a_resource_walked_through_is_where_it_is_too(self):
        root = Site()
        call(root, "GET", "/profile/name.txt")
        self.assertEqual(root.url, "/")
        self.assertEqual(Site.child_profile.url, "/profile")

    def test_one_resource_has_one_url(self):
        ada = Profile()
        root = {"a": ada, "b": ada}
        self.assertEqual(call(root, "GET", "/a.html")[0], 200)
        with self.assertLogs("mumulib.server", "ERROR") as logs:
            status, _, body = call(root, "GET", "/b.html")
        self.assertEqual(status, 500)
        # Logged with both URLs, and the client told only the status
        self.assertIn("Profile at /a was reached as /b", logs.output[0])
        self.assertNotIn(b"/a", body)
        self.assertEqual(ada.url, "/a")


class Named(Resource):
    """Renamed by a POST, which it saves."""

    async def handle_POST(self, request):
        self.state["name"] = request["parsed_body"]
        await self.save()
        return self.state


class TestPersistence(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data = Path(directory.name).resolve()

    def call(self, root, method, path, body=None):
        return call(root, method, path, body, data=self.data)

    def test_with_no_file_it_answers_from_memory_and_writes_nothing(self):
        ada = Named({"name": "Ada"})
        status, _, body = self.call({"people": {"ada": ada}}, "GET", "/people/ada.json")
        self.assertEqual((status, json.loads(body)), (200, {"name": "Ada"}))
        self.assertEqual(ada.file, self.data / "people" / "ada.json")
        self.assertEqual(list(self.data.iterdir()), [])

    def test_save_writes_the_state_as_state_json_answers_it(self):
        ada = Named({"name": "Ada", "seen": MappingProxyType({"a": 1})})
        root = {"people": {"ada": ada}}
        self.assertEqual(self.call(root, "POST", "/people/ada.json", "Grace")[0], 200)
        saved = json.loads((self.data / "people" / "ada.json").read_text())
        self.assertEqual(saved, {"name": "Grace", "seen": {"a": 1}})
        self.assertEqual(
            json.loads(self.call(root, "GET", "/people/ada.json")[2]), saved
        )
        # Nothing left beside it: the temporary file was renamed into place
        self.assertEqual(list((self.data / "people").iterdir()), [ada.file])

    def test_an_existing_file_wins_over_the_constructors_state(self):
        (self.data / "people").mkdir()
        (self.data / "people" / "ada.json").write_text('{"name": "Saved"}')
        ada = Named({"name": "Constructed"})
        body = self.call({"people": {"ada": ada}}, "GET", "/people/ada.json")[2]
        self.assertEqual(json.loads(body), {"name": "Saved"})
        self.assertEqual(ada.state, {"name": "Saved"})

    def test_it_is_loaded_once_and_its_memory_is_what_answers_after(self):
        ada = Named({"name": "Ada"})
        root = {"ada": ada}
        self.call(root, "POST", "/ada.json", "Grace")
        # The file changed underneath is not read again
        (self.data / "ada.json").write_text('{"name": "Elsewhere"}')
        self.assertEqual(
            json.loads(self.call(root, "GET", "/ada.json")[2])["name"], "Grace"
        )
        # And a new process -- a new object -- starts from the file
        fresh = Named({"name": "Ada"})
        body = self.call({"ada": fresh}, "GET", "/ada.json")[2]
        self.assertEqual(json.loads(body), {"name": "Elsewhere"})

    def test_an_index_keeps_index_json(self):
        home, top = Named(), Named()
        self.call({"home": {"index": home}}, "POST", "/home/", "Home")
        self.assertEqual(home.file, self.data / "home" / "index.json")
        self.call({"index": top}, "POST", "/", "Top")
        self.assertEqual(top.file, self.data / "index.json")
        self.assertEqual(
            json.loads((self.data / "index.json").read_text()), {"name": "Top"}
        )

    def test_a_resource_no_request_has_reached_cannot_be_saved(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(Named().save())

    def test_a_failed_write_leaves_the_file_as_it_was(self):
        ada = Named({"name": "Ada"})
        root = {"ada": ada}
        self.call(root, "POST", "/ada.json", "Grace")
        with unittest.mock.patch("os.replace", side_effect=OSError("disk full")):
            with unittest.mock.patch("traceback.print_exc"):
                status = self.call(root, "POST", "/ada.json", "Lost")[0]
        self.assertEqual(status, 500)
        self.assertEqual(
            json.loads((self.data / "ada.json").read_text()), {"name": "Grace"}
        )
        self.assertEqual(list(self.data.iterdir()), [ada.file])

    def test_its_state_is_cached_by_its_file_and_its_answers_are_not(self):
        ada = Named({"name": "Ada"})
        root = {"ada": ada}
        # No file yet: nothing to say whether a copy is fresh
        self.assertNotIn(b"etag", self.call(root, "GET", "/ada.json")[1])
        self.call(root, "POST", "/ada.json", "Grace")
        _, headers, _ = self.call(root, "GET", "/ada.json")
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        self.assertEqual(headers[b"etag"], static.file_etag(self.data / "ada.json"))
        # Its page is computed, and not the file's to vouch for
        self.assertNotIn(b"etag", self.call(root, "GET", "/ada.html")[1])

    def test_json_of_its_own_is_not_cached_by_the_file(self):
        class Computed(Named):
            async def handle_GET(self, request):
                return {"computed": True}

        thing = Computed({"name": "Ada"})
        self.call({"c": thing}, "POST", "/c.json", "Grace")
        _, headers, body = self.call({"c": thing}, "GET", "/c.json")
        self.assertEqual(json.loads(body), {"computed": True})
        self.assertNotIn(b"etag", headers)
