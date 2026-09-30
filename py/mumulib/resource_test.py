# pyright: standard
import asyncio
import json
import unittest

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

    def test_a_put_is_the_resources_under_a_resource_and_the_dicts_under_a_dict(self):
        # Under a resource, the resource answers: here it refuses
        root = Site()
        self.assertEqual(call(root, "PUT", "/profile.html", "x")[0], 405)
        self.assertIsInstance(root.child_profile, Profile)
        # A dict answers for its own entries, and replaces this one
        root = {"profile": Profile()}
        self.assertEqual(call(root, "PUT", "/profile.json", "replaced")[0], 201)
        self.assertEqual(root, {"profile": "replaced"})


class TestRegistration(unittest.TestCase):
    def test_every_subclass_is_registered_as_it_is_defined(self):
        class Deeper(Profile):
            template = "deeper"

        self.assertEqual(call({"d": Deeper()}, "GET", "/d.txt")[2], b"deeper")

    def test_resource_itself_is_registered(self):
        status, _, body = call({"r": Resource()}, "GET", "/r.txt")
        self.assertEqual((status, body), (200, b""))
