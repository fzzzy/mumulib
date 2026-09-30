# pyright: standard
import asyncio
import json
import unittest
from types import MappingProxyType
from urllib.parse import unquote

from mumulib.consumers import GetOnly, RefuseIndex
from mumulib.server import consumers_app


async def request(asgi_app, method, path, body):
    """
    Sends an HTTP request to an ASGI app without external dependencies.

    Args:
        asgi_app: The ASGI application to interact with.
        method (str): HTTP method (e.g., 'GET', 'POST').
        path (str): The request path.
        body (dict, optional): JSON-serializable body for the request.

    Returns:
        dict: A dictionary with 'status', 'headers', and 'body' keys.
    """
    # Create ASGI scope
    scope = {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "headers": [
            (b"content-type", b"application/json"),
            (b"host", b"testserver"),
        ],
        "query_string": b"",
        "state": {},
    }

    if body is not None:
        body_bytes = json.dumps(body).encode("utf-8")
        scope["headers"].append(
            (b"content-length", str(len(body_bytes)).encode("utf-8"))
        )
    else:
        body_bytes = b""

    # ASGI event queues
    receive_queue = [{"type": "http.request", "body": body_bytes, "more_body": False}]
    send_queue = []

    async def receive():
        return receive_queue.pop(0) if receive_queue else {"type": "http.disconnect"}

    async def send(event):
        send_queue.append(event)

    # Call the ASGI app
    await asgi_app(scope, receive, send)

    # Process the response
    response_start = next(
        event for event in send_queue if event["type"] == "http.response.start"
    )
    response_body = next(
        event for event in send_queue if event["type"] == "http.response.body"
    )

    decoded_body = response_body["body"].decode("utf-8")
    if decoded_body:
        try:
            decoded_body = json.loads(decoded_body)
        except json.decoder.JSONDecodeError:
            pass

    return {
        "status": response_start["status"],
        "headers": {k.decode(): v.decode() for k, v in response_start["headers"]},
        "body": decoded_body,
    }


class Foo:
    pass


# The root has no URL of its own for data -- no index.json -- so the tests
# read it here where they need all of it
ROOT = {
    "hello": "world",
    "tuple": ("this", "is", "a", "tuple"),
    "list": ["this", "is", "a", "list"],
    "immutable": MappingProxyType({"cannot": "touch this"}),
    "immutable_with_index": MappingProxyType(
        {"index": "index_value", "other": "other_value"}
    ),
    "not_found": Foo(),
    "nested_list": [["asdf"], ["qwer"]],
    "nested_dict": {"nested": {"again": "string"}},
}
ASGI_APP = consumers_app(ROOT)


class TestASGIApp(unittest.IsolatedAsyncioTestCase):
    async def test_basic(self):
        # The root's HTML is its slash; it has no name for data
        response = await request(ASGI_APP, "GET", "/", None)
        self.assertEqual(response["status"], 200)
        response = await request(ASGI_APP, "GET", "/index.json", None)
        self.assertEqual(response["status"], 404)
        # Each entry is its own name
        response = await request(ASGI_APP, "GET", "/nested_dict.json", None)
        self.assertEqual(response["body"], {"nested": {"again": "string"}})

    async def test_basic_put_delete(self):
        # Test GET /hello
        response = await request(ASGI_APP, "GET", "/hello.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "world")

        # Test PUT /hello
        response = await request(ASGI_APP, "PUT", "/hello.json", "newworld")
        self.assertEqual(response["status"], 201)

        # Verify GET /hello after PUT
        response = await request(ASGI_APP, "GET", "/hello.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "newworld")

        # Test DELETE /hello
        response = await request(ASGI_APP, "DELETE", "/hello.json", None)
        self.assertEqual(response["status"], 200)

        # DELETE of a key that is not there is still OK
        response = await request(ASGI_APP, "DELETE", "/hello.json", None)
        self.assertEqual(response["status"], 200)

        # After DELETE /hello, it is gone from the root and nothing else is
        self.assertNotIn("hello", ROOT)
        self.assertEqual(
            set(ROOT),
            {
                "tuple",
                "list",
                "immutable",
                "immutable_with_index",
                "not_found",
                "nested_list",
                "nested_dict",
            },
        )

    async def test_tuple(self):
        # Test GET /tuple and /tuple/2
        response = await request(ASGI_APP, "GET", "/tuple.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "is", "a", "tuple"])

        response = await request(ASGI_APP, "GET", "/tuple/2.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "a")

        # Test PUT and DELETE on /tuple/2
        response = await request(ASGI_APP, "PUT", "/tuple/2.json", "change")
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "DELETE", "/tuple/2.json", None)
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "GET", "/tuple/asdf.json", None)
        self.assertEqual(response["status"], 404)

    async def test_list(self):
        # Test GET /list and /list/1
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "is", "a", "list"])

        response = await request(ASGI_APP, "GET", "/list/1.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "is")

        # Test PUT /list/1
        response = await request(ASGI_APP, "PUT", "/list/1.json", "modified")
        self.assertEqual(response["status"], 201)

        # Verify GET /list after PUT /list/1
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "modified", "a", "list"])

        # Test PUT /list/555 fails
        response = await request(
            ASGI_APP, "PUT", "/list/555.json", json.dumps("notappended")
        )
        self.assertEqual(response["status"], 403)

        # Test PUT /list/asdf fails
        response = await request(
            ASGI_APP, "PUT", "/list/asdf.json", json.dumps("notappended")
        )
        self.assertEqual(response["status"], 405)

        # Test GET /list/asdf fails
        response = await request(ASGI_APP, "GET", "/list/asdf.json", None)
        self.assertEqual(response["status"], 404)

        # Test PUT /list/last
        response = await request(ASGI_APP, "PUT", "/list/last.json", "appended")
        self.assertEqual(response["status"], 201)
        # The new element's own URL, extension and all
        self.assertEqual(response["headers"]["location"], "/list/4.json")

        # Verify GET /list after PUT /list/last
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"], ["this", "modified", "a", "list", "appended"]
        )

        # Test DELETE /list/1
        response = await request(ASGI_APP, "DELETE", "/list/1.json", None)
        self.assertEqual(response["status"], 200)

        # Verify GET /list after DELETE /list/1
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "a", "list", "appended"])

        # Test DELETE /list/555
        response = await request(ASGI_APP, "DELETE", "/list/555.json", None)
        self.assertEqual(response["status"], 200)

        # Test DELETE /list/asdf
        response = await request(ASGI_APP, "DELETE", "/list/asdf.json", None)
        self.assertEqual(response["status"], 200)

    async def test_nested_list(self):
        response = await request(ASGI_APP, "GET", "/nested_list/0/0.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "asdf")

    async def test_nested_dict(self):
        response = await request(
            ASGI_APP, "GET", "/nested_dict/nested/again.json", None
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "string")

    async def test_immutable(self):
        # Test GET /immutable
        response = await request(ASGI_APP, "GET", "/immutable.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"cannot": "touch this"})

        # Test PUT and DELETE on /immutable/cannot
        response = await request(
            ASGI_APP, "PUT", "/immutable/cannot.json", json.dumps("attempted change")
        )
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "DELETE", "/immutable/cannot.json", None)
        self.assertEqual(response["status"], 405)

        # Verify GET /immutable after PUT and DELETE
        response = await request(ASGI_APP, "GET", "/immutable.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"cannot": "touch this"})

    async def test_immutable_with_index(self):
        # As data, its name is the whole dict, "index" entry and all
        response = await request(ASGI_APP, "GET", "/immutable_with_index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"], {"index": "index_value", "other": "other_value"}
        )

        # Its slash is the "index" entry, as HTML; spelled out, it is no name
        response = await request(ASGI_APP, "GET", "/immutable_with_index/", None)
        self.assertEqual((response["status"], response["body"]), (200, "index_value"))
        response = await request(
            ASGI_APP, "GET", "/immutable_with_index/index.json", None
        )
        self.assertEqual(response["status"], 404)

        # Test GET /immutable_with_index/other - should return the "other" value
        response = await request(
            ASGI_APP, "GET", "/immutable_with_index/other.json", None
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "other_value")

    async def test_not_found(self):
        # Test GET /not_found/foo fails
        response = await request(ASGI_APP, "GET", "/not_found/foo.json", None)
        self.assertEqual(response["status"], 404)

        # Test GET /asdfasdfasdfasdf fails
        response = await request(ASGI_APP, "GET", "/asdfasdfasdfasdf.json", None)
        self.assertEqual(response["status"], 404)


class TestSecurityValidation(unittest.IsolatedAsyncioTestCase):
    """Test security validation for index and key sanitization."""

    async def test_list_index_out_of_bounds(self):
        # Test with extremely large index
        response = await request(ASGI_APP, "GET", f"/list/{2**62}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_list_negative_index_out_of_bounds(self):
        # Test with extremely negative index
        response = await request(ASGI_APP, "GET", f"/list/{-(2**62)}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_key_too_long(self):
        # Test with key longer than MAX_KEY_LENGTH (1000 chars)
        long_key = "a" * 1001
        response = await request(ASGI_APP, "GET", f"/nested_dict/{long_key}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_key_with_null_byte(self):
        # Test with key containing null byte
        # URL encoding for null byte is %00
        response = await request(ASGI_APP, "GET", "/nested_dict/test\x00key.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_put_key_too_long(self):
        # Test PUT with key longer than MAX_KEY_LENGTH
        long_key = "b" * 1001
        response = await request(
            ASGI_APP, "PUT", f"/nested_dict/{long_key}.json", "value"
        )
        self.assertEqual(response["status"], 404)

    async def test_dict_put_key_with_null_byte(self):
        # Test PUT with key containing null byte
        response = await request(
            ASGI_APP, "PUT", "/nested_dict/bad\x00key.json", "value"
        )
        self.assertEqual(response["status"], 404)

    async def test_tuple_index_out_of_bounds(self):
        # Test tuple access with extremely large index
        response = await request(ASGI_APP, "GET", f"/tuple/{2**62}.json", None)
        self.assertEqual(response["status"], 404)


def call(root, method, path, body=None):
    """The status, headers and body of one request to root, published."""
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        data = json.dumps(body).encode() if body is not None else b""
        return {"type": "http.request", "body": data, "more_body": False}

    headers = [(b"content-type", b"application/json")] if body is not None else []
    # An ASGI server hands the app its path percent-decoded
    scope = {
        "type": "http",
        "method": method,
        "path": unquote(path),
        "headers": headers,
    }

    async def go():
        await consumers_app(root)({**scope, "state": {}}, receive, send)

    asyncio.run(go())
    content = b"".join(m.get("body", b"") for m in sent[1:])
    return sent[0]["status"], dict(sent[0]["headers"]), content


class TestGetOnly(unittest.TestCase):
    """GetOnly hands GET on to what it wraps, and refuses anything else."""

    def test_get_goes_through_at_any_depth(self):
        root = GetOnly({"index": "home", "notes": {"a": "first"}})
        status, _, body = call(root, "GET", "/")
        self.assertEqual((status, body.strip()), (200, b"home"))
        status, _, body = call(root, "GET", "/notes/a.json")
        self.assertEqual((status, json.loads(body)), (200, "first"))

    def test_anything_else_is_refused_at_any_depth_and_changes_nothing(self):
        data = {"index": "home", "notes": {"a": "first"}, "items": [1, 2]}
        root = GetOnly(data)
        for method, path in [
            ("PUT", "/"),
            ("DELETE", "/"),
            ("PUT", "/notes.json"),
            ("PUT", "/notes/a.json"),
            ("DELETE", "/notes/a.json"),
            ("PUT", "/items/last.json"),
            ("POST", "/notes/a.json"),
            ("HEAD", "/"),
        ]:
            with self.subTest(method=method, path=path):
                status, headers, body = call(root, method, path, "changed")
                self.assertEqual((status, body), (405, b"Only GET\n"))
                self.assertEqual(headers[b"allow"], b"GET")
        self.assertEqual(
            data, {"index": "home", "notes": {"a": "first"}, "items": [1, 2]}
        )

    def test_a_guarded_entry_is_what_it_wraps(self):
        root = {"about": GetOnly({"name": "mumulib"}), "motto": GetOnly("mumu")}
        status, _, body = call(root, "GET", "/about.json")
        self.assertEqual((status, json.loads(body)), (200, {"name": "mumulib"}))
        status, _, body = call(root, "GET", "/motto.json")
        self.assertEqual((status, json.loads(body)), (200, "mumu"))
        # A guarded container is still a container: its HTML is its slash
        self.assertEqual(call(root, "GET", "/about.html")[0], 404)
        status, _, _ = call(root, "PUT", "/about/name.json", "changed")
        self.assertEqual(status, 405)

    def test_it_guards_what_is_below_it_not_its_place_in_the_parent(self):
        # The unguarded dict answers for its own entries, this one included
        guarded = GetOnly({"name": "mumulib"})
        root = {"about": guarded}
        status, _, _ = call(root, "PUT", "/about.json", "replaced")
        self.assertEqual(status, 201)
        self.assertEqual(root, {"about": "replaced"})
        self.assertEqual(guarded.wrapped, {"name": "mumulib"})


class DirectorySite(unittest.TestCase):
    """A directory to serve, with things in it that must not be served."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.site = base / "site"
        (self.site / "sub").mkdir(parents=True)
        (self.site / "style.css").write_text("p { color: red }")
        (self.site / "app.min.js").write_text("run()")
        (self.site / "sub" / "note.txt").write_text("nested")
        (self.site / "sub" / "index.html").write_text("<p>sub index</p>")
        (self.site / ".env").write_text("SECRET=1")
        (self.site / "pixel.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\xff")
        (self.site / "README").write_text("no extension, so no URL")
        (self.site / "a b&c.txt").write_text("escaped")
        (self.site / "data.json").write_text('{"from": "a file"}')
        (base / "outside.txt").write_text("outside")
        (self.site / "escape.txt").symlink_to(base / "outside.txt")
        self.root = {"static": self.site}

    def tearDown(self):
        self.tmp.cleanup()


class TestDirectory(DirectorySite):
    """A Path to a directory serves what is in it, and nothing outside it."""

    def test_a_file_is_its_bytes_with_the_urls_type(self):
        status, headers, body = call(self.root, "GET", "/static/style.css")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/css; charset=UTF-8")
        self.assertEqual(body.strip(), b"p { color: red }")
        status, headers, body = call(self.root, "GET", "/static/pixel.png")
        self.assertEqual(headers[b"content-type"], b"image/png")
        self.assertTrue(body.startswith(b"\x89PNG\r\n\x1a\n\x00\xff"))

    def test_names_with_dots_and_nested_directories(self):
        self.assertEqual(
            call(self.root, "GET", "/static/app.min.js")[2].strip(), b"run()"
        )
        self.assertEqual(
            call(self.root, "GET", "/static/sub/note.txt")[2].strip(), b"nested"
        )

    def test_the_index_file_wins_over_a_listing(self):
        status, _, body = call(self.root, "GET", "/static/sub/")
        self.assertEqual((status, body.strip()), (200, b"<p>sub index</p>"))

    def test_a_directory_as_html_is_a_list_of_links(self):
        status, headers, body = call(self.root, "GET", "/static/")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        self.assertEqual(
            body.decode().strip(),
            "<ul>\n"
            '  <li><a href="/static/a%20b%26c.txt">a b&amp;c.txt</a></li>\n'
            '  <li><a href="/static/app.min.js">app.min.js</a></li>\n'
            '  <li><a href="/static/data.json">data.json</a></li>\n'
            '  <li><a href="/static/pixel.png">pixel.png</a></li>\n'
            '  <li><a href="/static/style.css">style.css</a></li>\n'
            '  <li><a href="/static/sub/">sub</a></li>\n'
            "</ul>",
        )

    def test_a_directory_as_json_is_names_to_urls(self):
        expected = {
            "a b&c.txt": "/static/a%20b%26c.txt",
            "app.min.js": "/static/app.min.js",
            "data.json": "/static/data.json",
            "pixel.png": "/static/pixel.png",
            "style.css": "/static/style.css",
            "sub": "/static/sub.json",
        }
        status, headers, body = call(self.root, "GET", "/static.json")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"application/json; charset=UTF-8")
        self.assertEqual(json.loads(body), expected)

    def test_a_directory_has_one_url_per_type(self):
        # Its HTML is its slash, its data its name; index spelled out is none
        for path in ("/static.html", "/static/index.html", "/static/index.json"):
            with self.subTest(path=path):
                self.assertEqual(call(self.root, "GET", path)[0], 404)
        # A subdirectory's too: its own index.html at its slash, and only there
        self.assertEqual(call(self.root, "GET", "/static/sub/")[0], 200)
        self.assertEqual(call(self.root, "GET", "/static/sub/index.html")[0], 404)
        status, _, body = call(self.root, "GET", "/static/sub.json")
        self.assertEqual(
            (status, json.loads(body)),
            (
                200,
                {
                    "index.html": "/static/sub/index.html",
                    "note.txt": "/static/sub/note.txt",
                },
            ),
        )

    def test_every_listed_url_is_served(self):
        _, _, body = call(self.root, "GET", "/static.json")
        for name, url in json.loads(body).items():
            with self.subTest(name=name):
                self.assertEqual(call(self.root, "GET", url)[0], 200)

    def test_a_json_file_is_its_bytes_not_a_listing(self):
        status, _, body = call(self.root, "GET", "/static/data.json")
        self.assertEqual((status, json.loads(body)), (200, {"from": "a file"}))

    def test_a_directory_is_listed_only_as_html_or_json(self):
        self.assertEqual(call(self.root, "GET", "/static.txt")[0], 404)

    def test_nothing_outside_or_hidden_is_found(self):
        for path in [
            "/static/missing.txt",
            "/static/../outside.txt",
            "/static/.env",
            "/static/escape.txt",
            "/static/style.json",
            "/static/sub.html",
            "/static/README.txt",
            "/static/style.css/more.txt",
        ]:
            with self.subTest(path=path):
                self.assertEqual(call(self.root, "GET", path)[0], 404)

    def test_a_directory_is_never_written(self):
        for method in ("PUT", "DELETE", "POST"):
            with self.subTest(method=method):
                status, headers, _ = call(self.root, method, "/static/new.txt", "x")
                self.assertEqual((status, headers[b"allow"]), (405, b"GET"))
        self.assertFalse((self.site / "new.txt").exists())


class TestRefuseIndex(DirectorySite):
    """RefuseIndex: an index is not found, at any depth; the rest is served."""

    def setUp(self):
        super().setUp()
        self.root = {"static": RefuseIndex(self.site)}

    def test_the_index_is_not_found_at_any_depth(self):
        for path in [
            "/static/",
            "/static/index.html",
            "/static/index.json",
            "/static/sub/",
            "/static/sub.json",
            "/static.html",
            "/static.json",
        ]:
            with self.subTest(path=path):
                self.assertEqual(call(self.root, "GET", path)[0], 404)

    def test_everything_else_is_still_served(self):
        self.assertEqual(call(self.root, "GET", "/static/style.css")[0], 200)
        self.assertEqual(call(self.root, "GET", "/static/sub/note.txt")[0], 200)

    def test_a_guarded_leaf_is_what_it_wraps(self):
        root = {"motto": RefuseIndex("mumu")}
        status, _, body = call(root, "GET", "/motto.json")
        self.assertEqual((status, json.loads(body)), (200, "mumu"))

    def test_it_guards_a_dict_too(self):
        root = RefuseIndex({"index": "home", "a": 1})
        self.assertEqual(call(root, "GET", "/")[0], 404)
        self.assertEqual(call(root, "GET", "/a.json")[2], b"1\n")
