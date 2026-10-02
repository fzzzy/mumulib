# pyright: standard
import asyncio
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from types import MappingProxyType

from mumulib.persist import Persist
from mumulib.producers import add_json_form
from mumulib.resource import Resource
from mumulib.server import consumers_app
from mumulib.xml_producer import to_xml


def get(root, path, data):
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def go():
        scope = {"type": "http", "method": "GET", "path": path, "headers": []}
        await consumers_app(root, data=data)({**scope, "state": {}}, receive, send)

    asyncio.run(go())
    headers = dict(sent[0]["headers"])
    body = b"".join(m.get("body", b"") for m in sent[1:]).decode()
    return sent[0]["status"], headers.get(b"content-type", b""), body


class TestToXml(unittest.TestCase):
    def test_each_key_is_an_element_and_says_its_type(self):
        document = {"name": "Ada", "age": 3, "tags": ["a", "b"], "ok": True, "x": None}
        self.assertEqual(
            to_xml(document, "ada"),
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<ada type="object">\n'
            '  <name type="string">Ada</name>\n'
            '  <age type="number">3</age>\n'
            '  <tags type="array">\n'
            '    <item type="string">a</item>\n'
            '    <item type="string">b</item>\n'
            "  </tags>\n"
            '  <ok type="boolean">true</ok>\n'
            '  <x type="null"/>\n'
            "</ada>\n",
        )

    def test_a_key_that_is_no_name_is_an_entry(self):
        out = to_xml({"1st": 1, "a b": "<&>", "xmlish": False, "_ok-1.2": 0.5}, "d")
        self.assertIn('<entry key="1st" type="number">1</entry>', out)
        self.assertIn('<entry key="a b" type="string">&lt;&amp;&gt;</entry>', out)
        self.assertIn('<entry key="xmlish" type="boolean">false</entry>', out)
        self.assertIn('<_ok-1.2 type="number">0.5</_ok-1.2>', out)
        # And what it writes is XML a parser reads
        ElementTree.fromstring(out.encode())

    def test_nesting_empties_and_a_quote_in_a_key(self):
        out = to_xml(
            {"o": {}, "l": [], "t": (1, [2]), "m": MappingProxyType({'"q"': 1})},
            "d",
        )
        self.assertIn('<o type="object"/>', out)
        self.assertIn('<l type="array"/>', out)
        self.assertIn('<item type="array">', out)
        self.assertIn('<entry key=\'"q"\' type="number">1</entry>', out)
        ElementTree.fromstring(out.encode())

    def test_a_json_form_is_written_and_anything_else_refused(self):
        class Point:
            pass

        class Other:
            pass

        add_json_form(Point, lambda p: [1, 2])
        self.assertIn('<item type="number">2</item>', to_xml({"p": Point()}, "d"))
        with self.assertRaisesRegex(TypeError, "Other"):
            to_xml({"o": Other()}, "d")
        with self.assertRaisesRegex(ValueError, "XML cannot"):
            to_xml({"bell": "\x07"}, "d")


class TestOverHttp(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data = Path(directory.name).resolve()

    def test_a_plain_dict_is_xml_and_its_resources_are_urls(self):
        root = {"site": {"title": "T", "page": Resource({"a": 1})}}
        status, content_type, body = get(root, "/site.xml", self.data)
        self.assertEqual(status, 200)
        self.assertEqual(content_type, b"application/xml; charset=UTF-8")
        self.assertIn('<dict type="object">', body)
        self.assertIn('<page type="string">/site/page.xml</page>', body)

    def test_a_resource_and_a_persist_are_their_state_named_by_class(self):
        class Person(Resource):
            pass

        root = {"r": Person({"a": 1}), "p": Persist({"b": [True]}), "l": Persist([1])}
        body = get(root, "/r.xml", self.data)[2]
        # Named by what it is, not where it is
        self.assertIn('<Person type="object">', body)
        self.assertIn('<a type="number">1</a>', body)
        body = get(root, "/p.xml", self.data)[2]
        self.assertIn('<Persist type="object">', body)
        self.assertIn('<item type="boolean">true</item>', body)
        # Only a dict is XML
        self.assertEqual(get(root, "/l.xml", self.data)[0], 404)

    def test_only_a_dict_is_xml(self):
        root = {"items": [1, 2], "motto": "mumu", "n": 3}
        for path in ("/items.xml", "/motto.xml", "/n.xml"):
            with self.subTest(path=path):
                self.assertEqual(get(root, path, self.data)[0], 404)

    def test_xml_is_application_xml_whatever_mimetypes_has_read(self):
        import mimetypes

        mimetypes.init()
        status, content_type, _ = get({"d": {}}, "/d.xml", self.data)
        self.assertEqual(
            (status, content_type), (200, b"application/xml; charset=UTF-8")
        )
