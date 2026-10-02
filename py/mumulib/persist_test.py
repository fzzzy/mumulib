# pyright: standard
import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mumulib import persist, static
from mumulib.persist import Persist
from mumulib.server import EventSource, consumers_app
from mumulib.static import is_fresh as _is_fresh


class PersistCase(unittest.TestCase):
    """A persist, its root and its data directory, and a request to them."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data = Path(directory.name).resolve()
        self.people = Persist({"ada": {"name": "Ada"}, "list": [1, 2]})
        self.root = {"people": self.people}

    def call(self, method, path, body=None, root=None, changes=None, match=None):
        """The status, headers, body messages and body of one request."""
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            data = json.dumps(body).encode() if body is not None else b""
            return {"type": "http.request", "body": data, "more_body": False}

        headers = [(b"content-type", b"application/json")] if body is not None else []
        if match is not None:
            headers.append((b"if-none-match", match))
        scope = {"type": "http", "method": method, "path": path, "headers": headers}
        app = consumers_app(
            self.root if root is None else root, changes=changes, data=self.data
        )

        async def go():
            await app({**scope, "state": {}}, receive, send)

        asyncio.run(go())
        bodies = [m["body"] for m in sent[1:]]
        return sent[0]["status"], dict(sent[0]["headers"]), bodies, b"".join(bodies)

    def saved(self):
        return json.loads((self.data / "people.json").read_text())


class TestPersist(PersistCase):
    def test_its_first_request_writes_what_it_was_made_with(self):
        self.assertFalse((self.data / "people.json").exists())
        self.call("GET", "/people/ada/name.txt")
        self.assertEqual(self.people.file, self.data / "people.json")
        self.assertEqual(self.saved(), {"ada": {"name": "Ada"}, "list": [1, 2]})

    def test_an_existing_file_wins(self):
        (self.data / "people.json").write_text('{"grace": {"name": "Grace"}}')
        _, _, _, body = self.call("GET", "/people/grace/name.txt")
        self.assertEqual(body.strip(), b"Grace")
        self.assertEqual(self.people.document, {"grace": {"name": "Grace"}})

    def test_get_is_the_file_streamed_as_it_is_on_disk(self):
        self.call("GET", "/people/ada.json")
        # Written by hand: what is served is the file's bytes, not the
        # document's JSON made again
        (self.data / "people.json").write_text('{"spaced" :  1}')
        with mock.patch.object(static, "CHUNK_SIZE", 4):
            status, headers, bodies, body = self.call("GET", "/people.json")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"application/json; charset=UTF-8")
        self.assertEqual(body.strip(), b'{"spaced" :  1}')
        self.assertIn(b'{"sp', bodies)

    def test_a_write_below_it_sets_the_document_and_writes_the_file(self):
        status = self.call("PUT", "/people/ada/name.json", "Augusta")[0]
        self.assertEqual(status, 204)
        self.assertEqual(self.saved()["ada"], {"name": "Augusta"})
        self.assertEqual(self.call("PUT", "/people/list/last.json", 3)[0], 201)
        self.assertEqual(self.call("DELETE", "/people/ada.json")[0], 204)
        self.assertEqual(self.saved(), {"list": [1, 2, 3]})
        self.assertEqual(self.people.document, self.saved())

    def test_what_fails_writes_nothing(self):
        self.call("GET", "/people.json")
        before = (self.data / "people.json").stat().st_mtime_ns
        for method, path in [
            ("DELETE", "/people/missing.json"),
            ("PUT", "/people/list/9.json"),
            ("GET", "/people/ada.json"),
        ]:
            with self.subTest(method=method, path=path):
                self.call(method, path, "x" if method == "PUT" else None)
                self.assertEqual((self.data / "people.json").stat().st_mtime_ns, before)

    def test_a_put_to_it_replaces_the_document(self):
        self.assertEqual(self.call("PUT", "/people.json", {"new": True})[0], 204)
        self.assertEqual(self.saved(), {"new": True})
        self.assertIs(self.root["people"], self.people)
        status, headers, _, _ = self.call("DELETE", "/people.json")
        self.assertEqual((status, headers[b"allow"]), (405, b"GET, PUT"))

    def test_in_a_plain_dict_it_is_linked_as_its_json(self):
        _, _, _, body = self.call("GET", "/all/", root={"all": {"p": self.people}})
        self.assertIn(b'<a href="/all/p.json">p</a>', body)

    def test_its_xml_is_read_alone(self):
        status, headers, _, _ = self.call("PUT", "/people.xml", {"a": 1})
        self.assertEqual((status, headers[b"allow"]), (405, b"GET"))

    def test_only_json_for_now(self):
        self.assertEqual(self.call("GET", "/people.html")[0], 404)
        self.assertEqual(self.call("GET", "/people.txt")[0], 404)

    def test_a_write_inside_it_announces_it(self):
        changes = EventSource()
        with mock.patch.object(changes, "put") as put:
            self.call("PUT", "/people/ada/name.json", "A", changes=changes)
            self.call("PUT", "/people.json", {}, changes=changes)
        self.assertEqual([c.args[0] for c in put.call_args_list], ["/people"] * 2)

    def test_inside_a_plain_container_it_is_its_url(self):
        _, _, _, body = self.call("GET", "/all.json", root={"all": {"p": self.people}})
        self.assertEqual(json.loads(body), {"p": "/all/p.json"})

    def test_its_document_holds_no_resource_or_persist(self):
        inner = Persist()
        nested = Persist({"a": [inner]})
        with mock.patch("traceback.print_exc"):
            status = self.call("GET", "/n.json", root={"n": nested})[0]
        self.assertEqual(status, 500)
        with self.assertRaisesRegex(TypeError, "/n/a/0 is a Persist"):
            nested.write()

    def test_with_no_data_directory_it_is_kept_in_memory(self):
        thing = Persist()
        self.assertIsNone(thing.file)
        asyncio.run(thing.load())
        thing.write()

        async def go():
            # Asked for with no file: the document, made into JSON
            return [c async for c in persist._produce_persist_json(thing, {})]

        self.assertEqual(asyncio.run(go()), ["{}"])


class TestCaching(PersistCase):
    def etag(self, path):
        status, headers, _, _ = self.call("GET", path)
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        return headers[b"etag"]

    def test_it_and_everything_below_it_have_its_files_etag(self):
        etag = self.etag("/people.json")
        stat = (self.data / "people.json").stat()
        self.assertEqual(etag, f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"'.encode())
        self.assertEqual(self.etag("/people/ada/name.txt"), etag)
        self.assertEqual(self.etag("/people/list.json"), etag)

    def test_if_none_match_it_is_a_304_with_nothing_in_it(self):
        etag = self.etag("/people.json")
        for match in (etag, b"W/" + etag, b'"other", ' + etag, b"*"):
            with self.subTest(match=match):
                status, headers, _, body = self.call(
                    "GET", "/people/ada.json", match=match
                )
                self.assertEqual((status, body), (304, b""))
                self.assertEqual(headers[b"etag"], etag)
        status, _, _, body = self.call("GET", "/people.json", match=b'"other"')
        self.assertEqual(status, 200)
        self.assertTrue(body)

    def test_a_write_is_a_new_etag(self):
        etag = self.etag("/people.json")
        status, headers, _, _ = self.call("PUT", "/people/ada/name.json", "Ada L")
        # A write's own answer is not cached
        self.assertEqual(status, 204)
        self.assertNotIn(b"etag", headers)
        self.assertNotEqual(self.etag("/people.json"), etag)
        status, _, _, _ = self.call("GET", "/people.json", match=etag)
        self.assertEqual(status, 200)

    def test_what_is_in_memory_alone_has_no_etag(self):
        root = {"plain": {"a": 1}}
        _, headers, _, _ = self.call("GET", "/plain.json", root=root)
        self.assertNotIn(b"etag", headers)
        self.assertNotIn(b"cache-control", headers)

    def test_if_none_match_is_found_among_the_headers(self):
        headers = [(b"accept", b"*/*"), (b"If-None-Match", b'"a"')]
        self.assertTrue(_is_fresh(b'"a"', headers))
        self.assertFalse(_is_fresh(b'"b"', headers))
        self.assertFalse(_is_fresh(b'"a"', headers[:1]))
