# pyright: standard
import asyncio
import json
import unittest
from types import MappingProxyType

from mumulib.consumers import GetOnly, RefuseIndex
from mumulib.resource import Resource
from mumulib.server import consumers_app


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
    """Answers each type in its own way, from state."""

    def handle_GET(self, state):
        if state["extension"] == "json":
            return {"type": state["content_type"]}
        return f"as {state['extension']}"


class Guestbook(Resource):
    """Takes POSTs, and nothing else but GET."""

    def __init__(self):
        self.entries = []

    def handle_GET(self, state):
        return self.entries

    def handle_POST(self, state):
        self.entries.append(state["parsed_body"])
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
        self.value = "empty"
        self.seen = []

    def handle_GET(self, state):
        return self.value

    def handle_PUT(self, state):
        self.seen.append("PUT")
        self.value = state["parsed_body"]
        return {"now": self.value}

    def handle_DELETE(self, state):
        self.seen.append("DELETE")
        self.value = "empty"
        return {"now": self.value}

    def handle_POST(self, state):
        self.seen.append("POST")
        return {"posted": state["parsed_body"]}

    def handle_PATCH(self, state):
        self.seen.append("PATCH")
        return {"patched": state["parsed_body"]}


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
