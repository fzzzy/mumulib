# pyright: standard
import asyncio
import http.server
import os
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from mumulib import static
from mumulib.server import consumers_app
from mumulib.static import Page

PAGE = b"<!doctype html><script type=module src=/vite/assets/main-1a2b.js></script>"


class StaticCase(unittest.TestCase):
    """A Vite build directory with a page and an asset, and requests to it."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.vite = Path(directory.name).resolve()
        (self.vite / "notes").mkdir()
        (self.vite / "notes" / "index.html").write_bytes(PAGE)
        (self.vite / "assets").mkdir()
        (self.vite / "assets" / "main-1a2b.js").write_text("console.log(1)\n")
        self.root = {
            "index": Page("notes/index.html"),
            "page": Page("notes/index.html"),
        }

    def app(self, development=False, vite=True, root=None):
        """An app made with MUMULIB_DEVELOPMENT=1, or without it."""
        with mock.patch.dict(os.environ):
            os.environ.pop("MUMULIB_DEVELOPMENT", None)
            if development:
                os.environ["MUMULIB_DEVELOPMENT"] = "1"
            return consumers_app(
                self.root if root is None else root, vite=self.vite if vite else None
            )

    def call(self, app, path, method="GET", match=None):
        """The status, headers and body of one request."""
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        headers = [(b"if-none-match", match)] if match is not None else []
        scope = {"type": "http", "method": method, "path": path, "headers": headers}

        async def go():
            await app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        body = b"".join(m.get("body", b"") for m in sent[1:])
        return sent[0]["status"], dict(sent[0]["headers"]), body


class TestProduction(StaticCase):
    def test_a_page_is_vites_build_of_it_as_it_is(self):
        status, headers, body = self.call(self.app(), "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        self.assertEqual(body.strip(), PAGE)
        self.assertEqual(self.call(self.app(), "/page.html")[2].strip(), PAGE)

    def test_a_page_is_cached_by_its_file(self):
        _, headers, _ = self.call(self.app(), "/")
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        etag = headers[b"etag"]
        self.assertEqual(etag, static.file_etag(self.vite / "notes" / "index.html"))
        status, _, body = self.call(self.app(), "/", match=etag)
        self.assertEqual((status, body), (304, b""))

    def test_a_page_is_html_alone(self):
        self.assertEqual(self.call(self.app(), "/page.json")[0], 404)

    def test_a_page_not_built_or_with_nowhere_to_be_is_an_error(self):
        (self.vite / "notes" / "index.html").unlink()
        status, _, body = self.call(self.app(), "/")
        self.assertEqual(status, 500)
        self.assertIn(b"notes/index.html is not built", body)
        status, _, body = self.call(self.app(vite=False), "/")
        self.assertEqual(status, 500)
        self.assertIn(b"no vite directory", body)

    def test_what_vite_built_is_served_under_vite(self):
        status, headers, body = self.call(self.app(), "/vite/assets/main-1a2b.js")
        self.assertEqual((status, body), (200, b"console.log(1)\n"))
        self.assertEqual(headers[b"content-type"], b"text/javascript; charset=UTF-8")
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        status, _, body = self.call(
            self.app(), "/vite/assets/main-1a2b.js", match=headers[b"etag"]
        )
        self.assertEqual((status, body), (304, b""))

    def test_vite_types_by_the_file_and_knows_no_other(self):
        (self.vite / "assets" / "font.woff2").write_bytes(b"\0")
        (self.vite / "assets" / "blob.unknownext").write_bytes(b"\0")
        types = {
            path: self.call(self.app(), path)[1][b"content-type"]
            for path in ("/vite/assets/font.woff2", "/vite/assets/blob.unknownext")
        }
        self.assertEqual(
            types,
            {
                "/vite/assets/font.woff2": b"font/woff2",
                "/vite/assets/blob.unknownext": b"application/octet-stream",
            },
        )

    def test_vite_is_read_only_and_never_outside_the_build(self):
        (self.vite.parent / "secret.txt").write_text("no")
        self.addCleanup((self.vite.parent / "secret.txt").unlink)
        for path in ("/vite/missing.js", "/vite/assets", "/vite/../secret.txt"):
            with self.subTest(path=path):
                self.assertEqual(self.call(self.app(), path)[0], 404)
        status, headers, _ = self.call(self.app(), "/vite/assets/main-1a2b.js", "PUT")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET"))

    def test_without_a_vite_directory_vite_is_the_trees(self):
        app = self.app(vite=False, root={"vite": {"x": "from the tree"}})
        self.assertEqual(self.call(app, "/vite/x.txt")[2].strip(), b"from the tree")


class TestDevelopment(StaticCase):
    def test_a_page_is_asked_of_vites_dev_server(self):
        with mock.patch.object(static, "_fetch", return_value=b"<p>dev</p>") as fetch:
            status, headers, body = self.call(self.app(development=True), "/")
        fetch.assert_called_once_with("http://127.0.0.1:5757/vite/notes/index.html")
        self.assertEqual((status, body.strip()), (200, b"<p>dev</p>"))
        # What Vite answers with is its own to cache, not a file's
        self.assertNotIn(b"etag", headers)

    def test_vite_not_answering_is_a_502(self):
        failure = urllib.error.URLError("refused")
        with mock.patch.object(static, "_fetch", side_effect=failure):
            status, _, body = self.call(self.app(development=True), "/")
        self.assertEqual(status, 502)
        self.assertIn(b"did not answer", body)

    def test_vite_is_not_pythons_in_development(self):
        status, _, body = self.call(
            self.app(development=True), "/vite/assets/main-1a2b.js"
        )
        self.assertEqual(status, 404)
        self.assertIn(b"http://127.0.0.1:5757", body)

    def test_fetch_reads_what_a_server_answers(self):
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<p>" + self.path.encode() + b"</p>")

            def log_message(self, format, *args):
                pass

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        url = f"http://127.0.0.1:{server.server_address[1]}/vite/a.html"
        self.assertEqual(static._fetch(url), b"<p>/vite/a.html</p>")
