# pyright: standard
import asyncio
import http.server
import os
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from websockets.asyncio.server import serve

from mumulib import static
from mumulib.server import consumers_app
from mumulib.static import Page

BASE = "/mumulib-vite/"
ASSET = f"{BASE}assets/main-1a2b.js"
PAGE = f"<!doctype html><script type=module src={ASSET}></script>".encode()


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

    def call(
        self,
        app,
        path,
        method="GET",
        match=None,
        host=None,
        root="",
        headers=None,
        body=None,
    ):
        """The status, headers and body of one request, made of an app
        mounted at root, if one is given, as Starlette's Mount makes it."""
        sent = []

        async def send(message):
            sent.append(message)

        pieces = list(body) if body else [b""]

        async def receive():
            if not pieces:
                # The body read, a server waits until the browser leaves
                await asyncio.Event().wait()
            piece = pieces.pop(0)
            return {"type": "http.request", "body": piece, "more_body": bool(pieces)}

        headers = list(headers or [])
        if match is not None:
            headers.append((b"if-none-match", match))
        if host is not None:
            headers.append((b"host", host.encode()))
        scope = {
            "type": "http",
            "method": method,
            "path": root + path,
            "raw_path": (root + path).encode(),
            "root_path": root,
            "headers": headers,
        }

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

    def test_a_page_not_built_or_with_nowhere_to_be_is_an_err(self):
        (self.vite / "notes" / "index.html").unlink()
        with self.assertLogs("mumulib.static", "ERROR") as logs:
            status, _, body = self.call(self.app(), "/")
        self.assertEqual(status, 500)
        self.assertIn(b"notes/index.html is not built", body)
        # Where it was looked for is logged, and not told to the client
        self.assertIn(str(self.vite), logs.output[0])
        self.assertNotIn(str(self.vite).encode(), body)
        status, _, body = self.call(self.app(vite=False), "/")
        self.assertEqual(status, 500)
        self.assertIn(b"no vite directory", body)

    def test_what_vite_built_is_served_under_vite(self):
        status, headers, body = self.call(self.app(), ASSET)
        self.assertEqual((status, body), (200, b"console.log(1)\n"))
        self.assertEqual(headers[b"content-type"], b"text/javascript; charset=UTF-8")
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        status, _, body = self.call(self.app(), ASSET, match=headers[b"etag"])
        self.assertEqual((status, body), (304, b""))

    def test_vite_types_by_the_file_and_knows_no_other(self):
        (self.vite / "assets" / "font.woff2").write_bytes(b"\0")
        (self.vite / "assets" / "blob.unknownext").write_bytes(b"\0")
        types = {
            path: self.call(self.app(), path)[1][b"content-type"]
            for path in (f"{BASE}assets/font.woff2", f"{BASE}assets/blob.unknownext")
        }
        self.assertEqual(
            types,
            {
                f"{BASE}assets/font.woff2": b"font/woff2",
                f"{BASE}assets/blob.unknownext": b"application/octet-stream",
            },
        )

    def test_vite_is_read_only_and_never_outside_the_build(self):
        (self.vite.parent / "secret.txt").write_text("no")
        self.addCleanup((self.vite.parent / "secret.txt").unlink)
        for path in (f"{BASE}missing.js", f"{BASE}assets", f"{BASE}../secret.txt"):
            with self.subTest(path=path):
                self.assertEqual(self.call(self.app(), path)[0], 404)
        status, headers, _ = self.call(self.app(), ASSET, "PUT")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, HEAD"))

    def test_without_a_vite_directory_vite_is_the_trees(self):
        app = self.app(vite=False, root={"mumulib-vite": {"x": "from the tree"}})
        self.assertEqual(self.call(app, f"{BASE}x.txt")[2].strip(), b"from the tree")


class TestMounted(StaticCase):
    def test_a_page_mounted_names_vite_below_its_prefix(self):
        status, _, body = self.call(self.app(), "/", root="/cb")
        self.assertEqual(status, 200)
        self.assertEqual(
            body.strip(), PAGE.replace(b"=/mumulib-vite/", b"=/cb/mumulib-vite/")
        )

    def test_what_vite_built_is_served_below_the_prefix(self):
        status, _, body = self.call(self.app(), ASSET, root="/cb")
        self.assertEqual((status, body), (200, b"console.log(1)\n"))

    def test_below_puts_each_quoted_or_bare_base_below_root(self):
        page = (
            b"""<a href="/mumulib-vite/a"><b src='/mumulib-vite/b'>"""
            b"url(/mumulib-vite/c)"
        )
        self.assertEqual(
            static._below(page, "/cb"),
            b"""<a href="/cb/mumulib-vite/a"><b src='/cb/mumulib-vite/b'>"""
            b"url(/cb/mumulib-vite/c)",
        )


class TestDevelopment(StaticCase):
    def test_a_page_is_asked_of_vites_dev_server(self):
        with mock.patch.object(static, "_fetch", return_value=b"<p>dev</p>") as fetch:
            status, headers, body = self.call(self.app(development=True), "/")
        fetch.assert_called_once_with(
            "http://127.0.0.1:5757/mumulib-vite/notes/index.html"
        )
        self.assertEqual((status, body.strip()), (200, b"<p>dev</p>"))
        # What Vite answers with is its own to cache, not a file's
        self.assertNotIn(b"etag", headers)

    def test_a_page_is_served_as_vite_made_it(self):
        # Its URLs under the base, which this server passes on: one origin,
        # whatever host the page was asked of
        vite_page = b'<script src="/mumulib-vite/a.js">'
        with mock.patch.object(static, "_fetch", return_value=vite_page):
            _, _, body = self.call(
                self.app(development=True), "/", host="10.0.0.5:9870"
            )
        self.assertEqual(body.strip(), vite_page)

    def test_vite_not_answering_is_a_502(self):
        failure = urllib.error.URLError("refused")
        with mock.patch.object(static, "_fetch", side_effect=failure):
            status, _, body = self.call(self.app(development=True), "/")
        self.assertEqual(status, 502)
        self.assertIn(b"did not answer", body)

    def test_development_given_outweighs_the_environment(self):
        with mock.patch.dict(os.environ, {"MUMULIB_DEVELOPMENT": "1"}):
            app = consumers_app(self.root, vite=self.vite, development=False)
        status, _, body = self.call(app, "/")
        self.assertEqual((status, body.strip()), (200, PAGE))

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
        url = f"http://127.0.0.1:{server.server_address[1]}/mumulib-vite/a.html"
        self.assertEqual(static._fetch(url), b"<p>/mumulib-vite/a.html</p>")


class EchoingVite(http.server.BaseHTTPRequestHandler):
    """Vite's dev server, as far as these tests need it: what it was asked."""

    def do_GET(self):
        body = f"{self.command} {self.path} cookie={self.headers.get('cookie')}"
        self.send_response(200)
        self.send_header("content-type", "text/javascript")
        self.end_headers()
        self.wfile.write(body.encode())

    def do_POST(self):
        sent = self.rfile.read(int(self.headers["content-length"]))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"POST " + sent)

    def log_message(self, format, *args):
        pass


class TestDevelopmentPassesViteOn(StaticCase):
    """In development, what is under /mumulib-vite/ is Vite's, passed on."""

    def setUp(self):
        super().setUp()
        # The client is made on the loop it is first used on: each test's own
        static._client = None
        self.addCleanup(setattr, static, "_client", None)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), EchoingVite)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        vite = f"http://127.0.0.1:{server.server_address[1]}"
        patched = mock.patch.object(static, "VITE_DEV_SERVER", vite)
        patched.start()
        self.addCleanup(patched.stop)

    def test_what_is_under_the_base_is_vites(self):
        status, headers, body = self.call(
            self.app(development=True), f"{ASSET}?v=1", headers=[(b"cookie", b"a=1")]
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/javascript")
        # The path and query as they came; the browser's cookie kept from it
        self.assertEqual(body, f"GET {ASSET}?v=1 cookie=None".encode())

    def test_a_body_in_pieces_is_passed_on_whole(self):
        status, _, body = self.call(
            self.app(development=True), ASSET, "POST", body=[b"one, ", b"two"]
        )
        self.assertEqual((status, body), (200, b"POST one, two"))

    def test_without_a_build_directory_too(self):
        status, _, body = self.call(self.app(development=True, vite=False), ASSET)
        self.assertEqual((status, body), (200, f"GET {ASSET} cookie=None".encode()))

    def test_mounted_below_a_prefix_vite_is_asked_below_none(self):
        status, _, body = self.call(self.app(development=True), ASSET, root="/cb")
        self.assertEqual((status, body), (200, f"GET {ASSET} cookie=None".encode()))

    def test_vite_not_answering_is_a_502(self):
        with mock.patch.object(static, "VITE_DEV_SERVER", "http://127.0.0.1:9"):
            status, _, body = self.call(self.app(development=True), ASSET)
        self.assertEqual(status, 502)
        self.assertIn(b"did not answer", body)

    def websocket(self, app, path, says=("hello",), vite=None, root=""):
        """What the app sends a websocket that says each of says, in turn,
        to a Vite that answers each, until it is answered, closed or
        refused. vite: what Vite does with a connection, else echo."""
        sent = []
        incoming: asyncio.Queue = asyncio.Queue()
        left = list(says)

        async def receive():
            return await incoming.get()

        async def say_next():
            if left:
                said = left.pop(0)
                kind = "bytes" if isinstance(said, bytes) else "text"
                await incoming.put({"type": "websocket.receive", kind: said})
            elif says:
                # All said and answered: gone. With nothing to say, it
                # waits for Vite to close it
                await incoming.put({"type": "websocket.disconnect", "code": 1000})

        async def send(message):
            sent.append(message)
            if message["type"] in ("websocket.accept", "websocket.send"):
                await say_next()
            elif message["type"] == "websocket.close" and sent[0]["type"] != (
                "websocket.close"
            ):
                await incoming.put({"type": "websocket.disconnect", "code": 1000})

        async def echo(connection):
            async for message in connection:
                if isinstance(message, bytes):
                    await connection.send(b"vite heard " + message)
                else:
                    await connection.send("vite heard " + message)

        async def go():
            async with serve(vite or echo, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                with mock.patch.object(
                    static, "VITE_DEV_SERVER", f"http://127.0.0.1:{port}"
                ):
                    await incoming.put({"type": "websocket.connect"})
                    scope = {
                        "type": "websocket",
                        "path": root + path,
                        "raw_path": (root + path).encode(),
                        "root_path": root,
                        "headers": [],
                    }
                    await asyncio.wait_for(app(scope, receive, send), 5)

        asyncio.run(go())
        return sent

    def test_hot_reloading_is_passed_on_both_ways(self):
        sent = self.websocket(self.app(development=True), f"{BASE}?token=t")
        self.assertEqual(sent[0]["type"], "websocket.accept")
        self.assertIn({"type": "websocket.send", "text": "vite heard hello"}, sent)

    def test_a_websocket_is_refused_but_in_development(self):
        for app, path in (
            (self.app(), f"{BASE}?token=t"),
            (self.app(development=True), "/elsewhere"),
        ):
            with self.subTest(path=path):
                self.assertEqual(
                    self.websocket(app, path),
                    [{"type": "websocket.close", "code": 1008}],
                )

    def test_text_and_bytes_each_way_below_a_prefix(self):
        sent = self.websocket(
            self.app(development=True), f"{BASE}?token=t", ("hi", b"\x01"), root="/cb"
        )
        self.assertEqual(sent[0]["type"], "websocket.accept")
        self.assertIn({"type": "websocket.send", "text": "vite heard hi"}, sent)
        self.assertIn({"type": "websocket.send", "bytes": b"vite heard \x01"}, sent)

    def test_vite_closing_closes_it(self):
        async def hangs_up(connection):
            await connection.close()

        sent = self.websocket(self.app(development=True), BASE, (), vite=hangs_up)
        self.assertEqual(sent[-1], {"type": "websocket.close", "code": 1000})

    def test_vite_gone_as_it_is_spoken_to(self):
        # Vite hangs up at once; the browser says nothing, then too late
        async def hangs_up(connection):
            await connection.close()

        sent = []

        async def go():
            async with serve(hangs_up, "127.0.0.1", 0) as server:
                port = server.sockets[0].getsockname()[1]
                said = [
                    {"type": "websocket.connect"},
                    {"type": "websocket.receive"},
                    {"type": "websocket.receive", "text": "too late"},
                    {"type": "websocket.disconnect", "code": 1000},
                ]

                async def receive():
                    if said[0]["type"] == "websocket.receive" and "text" in said[0]:
                        await asyncio.sleep(0.3)
                    return said.pop(0)

                async def send(message):
                    sent.append(message)

                with mock.patch.object(
                    static, "VITE_DEV_SERVER", f"http://127.0.0.1:{port}"
                ):
                    scope = {"type": "websocket", "path": BASE, "headers": []}
                    await asyncio.wait_for(
                        static.forward_websocket(scope, receive, send), 5
                    )

        asyncio.run(go())
        self.assertEqual(sent[0]["type"], "websocket.accept")
        self.assertIn({"type": "websocket.close", "code": 1000}, sent)

    def test_vite_not_there_closes_it(self):
        with mock.patch.object(static, "_on_vite", return_value="ws://127.0.0.1:9/"):
            sent = self.websocket(self.app(development=True), BASE)
        self.assertEqual(sent, [{"type": "websocket.close", "code": 1011}])


class EndlessVite(http.server.BaseHTTPRequestHandler):
    """A response that never ends; and whether its reader has left."""

    protocol_version = "HTTP/1.1"
    left = threading.Event()

    def do_GET(self):
        self.send_response(200)
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        try:
            while True:
                self.wfile.write(b"5\r\nchunk\r\n")
                self.wfile.flush()
                time.sleep(0.05)
        except BrokenPipeError, ConnectionResetError:
            EndlessVite.left.set()

    def log_message(self, format, *args):
        pass


class TestBrowserGone(StaticCase):
    def test_vite_is_let_go_of_when_the_browser_leaves_mid_stream(self):
        static._client = None
        self.addCleanup(setattr, static, "_client", None)
        EndlessVite.left.clear()
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), EndlessVite)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        sent = []

        async def go():
            asked = asyncio.Event()

            async def receive():
                if not asked.is_set():
                    asked.set()
                    return {"type": "http.request", "body": b"", "more_body": False}
                # Some of it read, then the browser is gone
                await asyncio.sleep(0.3)
                return {"type": "http.disconnect"}

            async def send(message):
                sent.append(message)

            scope = {"type": "http", "method": "GET", "path": ASSET, "headers": []}
            with mock.patch.object(
                static,
                "VITE_DEV_SERVER",
                f"http://127.0.0.1:{server.server_address[1]}",
            ):
                await asyncio.wait_for(static.forward_http(scope, receive, send), 3)

        asyncio.run(go())
        # Some was relayed, and then Vite was hung up on
        self.assertGreater(sum(1 for m in sent if m.get("body")), 0)
        self.assertTrue(EndlessVite.left.wait(3), "Vite was still being read")
