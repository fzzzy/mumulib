# pyright: standard
import asyncio
import io
import tempfile
import unittest
from pathlib import Path

from mumulib import producers, tags
from mumulib.tags import Stan, Template, parse_template
from mumulib.tags import every as t

HERE = Path(__file__).parent

ATTR_TEMPLATE = b"""<!DOCTYPE html>
<html>
<body>
    <a data-pat="link" data-attr="href=url,title=label" data-slot="label">x</a>
    <div data-pat="card">
        <span data-slot="title">untitled</span>
        <img data-attr="src=picture" />
    </div>
    <p data-slot="footer">footer</p>
</body>
</html>
"""


def render(node, accept=("*/*",)):
    async def collect():
        state = {"accept": list(accept)}
        return "".join([str(chunk) async for chunk in tags.produce_html(node, state)])

    return asyncio.run(collect())


class TestStanBuilding(unittest.TestCase):
    def test_tag_groups_expose_every_element(self):
        for name in tags.ALL_ELEMENTS:
            self.assertIsInstance(getattr(t, name), Stan)
        self.assertEqual(tags.forms.input.tagname, "input")
        self.assertEqual(tags.table_content.td.tagname, "td")

    def test_prototype_tags_are_cloned_not_mutated(self):
        div = t.div(id="x")
        self.assertIsNot(div, t.div)
        self.assertEqual(div.attributes, {"id": "x"})
        self.assertEqual(t.div.attributes, {})

        with_child = t.div["child"]
        self.assertEqual(with_child.children, ["child"])
        self.assertEqual(t.div.children, [])

    def test_call_merges_attributes_and_takes_indent(self):
        node = Stan("div", 0, klass="a")
        same = node(id="b", indent=3)
        self.assertIs(same, node)
        self.assertEqual(node.attributes, {"klass": "a", "id": "b"})
        self.assertEqual(node.indent, 3)

    def test_getitem_single_and_list(self):
        child = Stan("p", 0)
        parent = Stan("div", 2)[child]
        self.assertEqual(parent.children, [child])
        self.assertEqual(child.indent, 3)

        other = Stan("span", 0)
        parent[[other, "text"]]
        self.assertEqual(parent.children, [child, other, "text"])
        self.assertEqual(other.indent, 3)

    def test_copy_is_deep_for_stan_children_and_attributes(self):
        inner = Stan("span", 1)["text"]
        attr_value = Stan("b", 0)
        node = Stan("div", 0, inner, title=attr_value, id="x")
        copied = node.copy()

        self.assertEqual(copied.tagname, "div")
        self.assertIsNot(copied.children[0], inner)
        self.assertEqual(copied.children[0].children, ["text"])
        self.assertIsNot(copied.attributes["title"], attr_value)
        self.assertEqual(copied.attributes["id"], "x")

    def test_repr(self):
        node = t.div(id="x")[[t.p["hello"], "b"]]
        self.assertEqual(
            repr(node),
            "every.div(id='x')[\n    every.p[\n        'hello'\n    ],\n    'b'\n]",
        )
        self.assertEqual(repr(t.br), "every.br")
        self.assertEqual(repr(t.hr(a=1, b=2)), "every.hr(a=1, b=2)")

    def test_reindent_tree(self):
        leaf = Stan("i", 0)
        root = Stan("div", 0, Stan("p", 0, leaf, "text"))
        tags.reindent_tree(root, 2)
        self.assertEqual(root.indent, 2)
        self.assertEqual(root.children[0].indent, 3)
        self.assertEqual(leaf.indent, 4)


class TestSlotsAndPatterns(unittest.TestCase):
    def make_tree(self):
        return Stan(
            "div",
            0,
            Stan("h1", 1, "old title", **{"data-slot": "title"}),
            "loose text",
            Stan(
                "ul",
                1,
                Stan("li", 2, "item", **{"data-pat": "item", "data-slot": "items"}),
                **{"data-slot": "list"},
            ),
            Stan("a", 1, **{"data-attr": "href=url,title=label"}),
        )

    def test_clone_pat(self):
        tree = self.make_tree()
        item = tree.clone_pat("item", items="filled")
        self.assertIsNotNone(item)
        assert item is not None
        self.assertEqual(item.tagname, "li")
        self.assertEqual(item.indent, 0)
        # The original tree is untouched.
        self.assertEqual(tree.children[2].children[0].children, ["item"])
        self.assertIsNone(tree.clone_pat("missing"))

    def test_clone_pat_on_the_pattern_itself(self):
        pat = Stan("li", 3, Stan("b", 4, **{"data-slot": "x"}), **{"data-pat": "p"})
        clone = pat.clone_pat("p", x="value")
        assert clone is not None
        self.assertEqual(clone.indent, 0)
        self.assertEqual(clone.children[0].children, ["value"])

    def test_fill_slots_with_scalar(self):
        tree = self.make_tree()
        tags.fill_slots(tree, "title", "new title")
        self.assertEqual(tree.children[0].children, ["new title"])

    def test_fill_slots_with_stan_replaces_the_slot_node(self):
        tree = self.make_tree()
        replacement = Stan("h2", 0, "replaced")
        tree.fill_slots("title", replacement)
        self.assertEqual(tree.children[0].tagname, "h2")
        self.assertIsNot(tree.children[0], replacement)
        self.assertEqual(tree.children[0].indent, 1)

    def test_fill_slots_with_list(self):
        tree = self.make_tree()
        tree.fill_slots("list", [Stan("li", 0, "one"), "two"])
        ul = tree.children[2]
        self.assertEqual(len(ul.children), 2)
        self.assertEqual(ul.children[0].tagname, "li")
        self.assertEqual(ul.children[0].indent, 1)
        self.assertEqual(ul.children[1], "two")

    def test_fill_slots_recurses_with_stan_value(self):
        tree = self.make_tree()
        tree.fill_slots("items", Stan("li", 0, "deep"))
        ul = tree.children[2]
        self.assertEqual(ul.children[0].children, ["deep"])

    def test_fill_slots_sets_attribute_slots(self):
        tree = self.make_tree()
        tree.fill_slots("url", "https://example.com")
        tree.fill_slots("label", "Example")
        link = tree.children[3]
        self.assertEqual(link.attributes["href"], "https://example.com")
        self.assertEqual(link.attributes["title"], "Example")

    def test_clear_slots(self):
        tree = self.make_tree()
        tags.clear_slots(tree, "items")
        self.assertEqual(tree.children[2].children[0].children, [])
        tree.clear_slots("title")
        self.assertEqual(tree.children[0].children, [])

    def test_append_slots(self):
        tree = self.make_tree()
        tags.append_slots(tree, "title", " more")
        self.assertEqual(tree.children[0].children, ["old title", " more"])

        extra = Stan("em", 0)
        tree.append_slots("title", extra)
        self.assertEqual(tree.children[0].children[2].tagname, "em")
        self.assertIsNot(tree.children[0].children[2], extra)

        tree.append_slots("list", [Stan("li", 0, "x"), "y"])
        ul = tree.children[2]
        self.assertEqual(len(ul.children), 3)
        self.assertEqual(ul.children[1].children, ["x"])
        self.assertEqual(ul.children[2], "y")

        tree.append_slots("url", "/appended")
        self.assertEqual(tree.children[3].attributes["href"], "/appended")


class TestTemplates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.attr_path = Path(self.tmp.name) / "attrs.html"
        self.attr_path.write_bytes(ATTR_TEMPLATE)

    def tearDown(self):
        self.tmp.cleanup()

    def test_parse_template(self):
        root = parse_template(io.BytesIO(ATTR_TEMPLATE))
        assert root is not None
        self.assertEqual(root.tagname, "html")
        body = root.children[0]
        self.assertEqual(body.tagname, "body")
        self.assertEqual([c.tagname for c in body.children], ["a", "div", "p"])
        self.assertEqual(body.children[0].children, ["x"])

    def test_parse_template_keeps_tail_text(self):
        root = parse_template(io.BytesIO(b"<div><b>bold</b> tail</div>"))
        assert root is not None
        div = root.children[0].children[0]
        self.assertEqual(div.tagname, "div")
        self.assertEqual(div.children[0].tagname, "b")
        # The tail is kept, though today it lands inside <b> rather than
        # after it in <div>.
        self.assertIn(" tail", repr(div))

    def test_parse_template_without_elements(self):
        self.assertIsNone(parse_template(io.BytesIO(b" ")))

    def test_template_clone_pat_fills_slots(self):
        template = Template(str(HERE / "templates.html"))
        person = template.clone_pat("person", name="Bob", age=40)
        self.assertTrue(template.loaded)
        rendered = render(person)
        self.assertIn("Bob", rendered)
        self.assertIn("40", rendered)
        self.assertIn("red", rendered)

    def test_template_clone_pat_slot_and_attr_on_pattern_root(self):
        template = Template(str(self.attr_path))
        link = template.clone_pat("link", url="/home", label="Home")
        self.assertEqual(link.attributes["href"], "/home")
        self.assertEqual(link.attributes["title"], "Home")
        self.assertEqual(link.children, ["Home"])

        replacement = Stan("strong", 0, "bold")
        replaced = template.clone_pat("link", label=replacement)
        self.assertIs(replaced, replacement)

    def test_template_clone_pat_nested_attr_slot(self):
        template = Template(str(self.attr_path))
        card = template.clone_pat("card", title="Hello", picture="/cat.png")
        self.assertEqual(card.children[0].children, ["Hello"])
        self.assertEqual(card.children[1].attributes["src"], "/cat.png")

    def test_template_clone_pat_skips_text_children(self):
        template = Template("unused.html")
        template.loaded = True
        template.template = Stan(
            "html", 0, "stray text", Stan("p", 1, **{"data-pat": "para"})
        )
        self.assertEqual(template.clone_pat("para").tagname, "p")

    def test_template_clone_pat_missing(self):
        template = Template(str(self.attr_path))
        with self.assertRaises(ValueError):
            template.clone_pat("nope")

    def test_template_that_failed_to_load(self):
        empty = Path(self.tmp.name) / "empty.html"
        empty.write_bytes(b" ")
        template = Template(str(empty))
        with self.assertRaises(ValueError):
            template.clone_pat("link")
        # Slot operations on an unloaded root are no-ops.
        template.fill_slots("footer", "x")
        template.clear_slots("footer")
        template.append_slots("footer", "x")
        self.assertIsNone(template.root)

    def test_template_slot_operations(self):
        template = Template(str(self.attr_path))
        template.fill_slots("footer", "filled")
        assert template.root is not None
        footer = template.root.children[0].children[2]
        self.assertEqual(footer.children, ["filled"])

        other = Template(str(self.attr_path))
        other.append_slots("footer", "!")
        assert other.root is not None
        self.assertEqual(other.root.children[0].children[2].children, ["footer", "!"])

        cleared = Template(str(self.attr_path))
        cleared.clear_slots("footer")
        assert cleared.root is not None
        self.assertEqual(cleared.root.children[0].children[2].children, [])

    def test_load_returns_self(self):
        template = Template(str(self.attr_path))
        self.assertIs(template.load(), template)
        self.assertIsNotNone(template.template)
        self.assertIsNot(template.root, template.template)


class TestProduceHtml(unittest.TestCase):
    def test_nested_render(self):
        node = t.div(id="x")[[t.p["hello"], "b"]]
        self.assertEqual(
            render(node),
            '<div id="x">\n    <p>\nhello\n    </p>\nb\n</div>\n',
        )

    def test_void_element_and_attribute_quoting(self):
        self.assertEqual(
            render(t.br(title='say "hi"')), '<br title="say &quot;hi&quot;" />\n'
        )

    def test_empty_element(self):
        self.assertEqual(render(t.p), "<p>\n\n</p>\n")

    def test_an_attribute_that_is_not_text_is_refused(self):
        with self.assertRaisesRegex(TypeError, "attribute 'title' produced bytes"):
            render(t.br(title=b"raw"))

    def test_attribute_values_go_through_producers(self):
        rendered = render(t.div(data=[1, 2]), accept=("application/json", "*/*"))
        self.assertIn('data="[1, 2]"', rendered)

    def test_registered_as_producer(self):
        async def collect():
            state = {"accept": ["*/*"]}
            return [chunk async for chunk in producers.produce(t.hr, state)]

        self.assertEqual(asyncio.run(collect()), ["<hr", " />\n"])


class TestEvery(unittest.TestCase):
    def test_every_tag_is_in_every(self):
        self.assertIsInstance(tags.every.div, Stan)

    def test_there_is_no_tags_all(self):
        # Renamed to every in 2.0: all shadowed the builtin under import *
        self.assertFalse(hasattr(tags, "all"))


class TestEscaping(unittest.TestCase):
    """What a tree holds as text is written out as text, never as markup."""

    def test_text_is_escaped(self):
        out = render(t.p["<script>alert(1)</script> & more"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; more", out)
        self.assertNotIn("<script>", out)

    def test_a_slot_filled_with_text_is_escaped(self):
        page = parse_template(io.BytesIO(b'<p data-slot="name">placeholder</p>'))
        assert page is not None
        page.fill_slots("name", '<img src=x onerror="steal()">')
        out = render(page)
        self.assertIn('&lt;img src=x onerror="steal()"&gt;', out)
        self.assertNotIn("<img", out)

    def test_attributes_are_escaped_whole(self):
        out = render(t.a(href="/x?a=1&b=2", title='<it\'s "quoted">'))
        self.assertIn('href="/x?a=1&amp;b=2"', out)
        self.assertIn('title="&lt;it&#x27;s &quot;quoted&quot;&gt;"', out)

    def test_numbers_are_text(self):
        self.assertIn("\n3\n", render(t.p[3]))

    def test_trees_and_markup_are_markup(self):
        out = render(t.div[[t.b["bold"], tags.Markup("<i>mine</i>")]])
        self.assertIn("<b>", out)
        self.assertIn("<i>mine</i>", out)

    def test_script_and_style_are_raw_text(self):
        out = render(t.div[[t.script["if (a < b && c) go()"], t.style["a > b {}"]]])
        self.assertIn("if (a < b && c) go()", out)
        self.assertIn("a > b {}", out)

    def test_an_entity_in_a_template_comes_back_an_entity(self):
        # lxml reads &amp; as &; written out, it is &amp; again
        page = parse_template(io.BytesIO(b"<p>Fish &amp; chips &lt;3</p>"))
        self.assertIn("Fish &amp; chips &lt;3", render(page))

    def test_anything_else_is_the_html_a_producer_makes_of_it(self):
        # A container's listing is registered by consumers, which a real app
        # always has, through the server
        import mumulib.consumers  # noqa: F401

        out = render(t.div[{"a": 1}], accept=("text/html", "*/*"))
        self.assertIn('<a href="/a.html">a</a>', out)

    def test_what_has_no_html_is_an_error_naming_its_type(self):
        for child, words in [(object(), "has no HTML form"), (b"raw", "no HTML")]:
            with self.subTest(child=child):
                with self.assertRaisesRegex(TypeError, words):
                    render(t.p[child], accept=("text/html", "*/*"))

    def test_several_children_are_each_a_child(self):
        out = render(t.p["a ", t.b["b"], " c"])
        self.assertIn("<b>", out)
        self.assertNotIn("every.b", out)

    def test_a_page_is_written_with_its_doctype(self):
        self.assertTrue(
            render(t.html[t.body["hi"]]).startswith("<!doctype html>\n<html>")
        )
        self.assertNotIn("doctype", render(t.div["a fragment"]))

    def test_pat_is_data_pat(self):
        row = t.tr(pat="row")[t.td["x"]]
        self.assertEqual(row.attributes, {"data-pat": "row"})
        self.assertIn('<tr data-pat="row">', render(row))
        # And a pattern so made is found as one
        table = t.table[t.tbody(**{"data-slot": "rows"})[row]]
        copy = table.clone_pat("row")
        assert copy is not None
        self.assertEqual(copy.tagname, "tr")

    def test_slt_is_data_slot_and_attr_is_data_attr(self):
        link = t.a(slt="label", attr="href=url")["x"]
        self.assertEqual(
            link.attributes, {"data-slot": "label", "data-attr": "href=url"}
        )
        both = t.input(attr={"value": "name", "title": "hint"})
        self.assertEqual(both.attributes, {"data-attr": "value=name,title=hint"})
        # And they are slots as any other: filled, here, in a copy
        page = t.div[t.a(slt="label", attr={"href": "url"})["x"], both]
        page.fill_slots("label", "Ada")
        page.fill_slots("url", "/ada")
        page.fill_slots("name", "Ada")
        out = render(page)
        self.assertIn('href="/ada"', out)
        self.assertIn('value="Ada"', out)
        self.assertIn("\nAda\n", out)

    def test_slot_is_left_as_htmls_own(self):
        self.assertEqual(t.span(slot="title").attributes, {"slot": "title"})
