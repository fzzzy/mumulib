import asyncio
import html
from collections.abc import AsyncIterator
from html.parser import HTMLParser
from typing import IO, TYPE_CHECKING, Any, cast

from mumulib import mumutypes, producers
from mumulib.mumutypes import State

# The public API: Building HTML, filling templates, and rendering them. Every
# tag is tags.every.<name>, and the groups hold them by kind. The element lists
# behind the groups are the module's own.
__all__ = [
    "Stan",
    "Template",
    "parse_template",
    "fill_slots",
    "clear_slots",
    "append_slots",
    "produce_html",
    "Markup",
    "page",
    "main_root",
    "document_metadata",
    "sectioning_root",
    "content_sectioning",
    "text_content",
    "inline_text_semantics",
    "image_and_multimedia",
    "embedded_content",
    "svg_and_mathml",
    "scripting",
    "demarcating_edits",
    "table_content",
    "forms",
    "interactive_elements",
    "web_components",
    "every",
]

# From MDN reference
VOID_ELEMENTS: list[str] = [
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
]


VOID_ELEMENTS_SET: set[str] = set(VOID_ELEMENTS)


MAIN_ROOT: list[str] = ["html"]


DOCUMENT_METADATA: list[str] = ["base", "head", "link", "meta", "style", "title"]


SECTIONING_ROOT: list[str] = ["body"]


CONTENT_SECTIONING: list[str] = [
    "address",
    "article",
    "aside",
    "footer",
    "header",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hgroup",
    "main",
    "nav",
    "section",
    "search",
]


TEXT_CONTENT: list[str] = [
    "blockquote",
    "dd",
    "div",
    "dl",
    "dt",
    "figcaption",
    "figure",
    "hr",
    "li",
    "menu",
    "ol",
    "p",
    "pre",
    "ul",
]


INLINE_TEXT_SEMANTICS: list[str] = [
    "a",
    "abbr",
    "b",
    "bdi",
    "bdo",
    "br",
    "cite",
    "code",
    "data",
    "dfn",
    "em",
    "i",
    "kbd",
    "mark",
    "q",
    "rp",
    "rt",
    "ruby",
    "s",
    "samp",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "time",
    "u",
    "var",
    "wbr",
]


IMAGE_AND_MULTIMEDIA: list[str] = ["area", "audio", "img", "map", "track", "video"]


EMBEDDED_CONTENT: list[str] = [
    "embed",
    "fencedframe",
    "iframe",
    "object",
    "picture",
    "source",
]


SVG_AND_MATHML: list[str] = ["svg", "math"]


SCRIPTING: list[str] = ["canvas", "noscript", "script"]


DEMARCATING_EDITS: list[str] = ["del", "ins"]


TABLE_CONTENT: list[str] = [
    "caption",
    "col",
    "colgroup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
]


FORMS: list[str] = [
    "button",
    "datalist",
    "fieldset",
    "form",
    "input",
    "label",
    "legend",
    "meter",
    "optgroup",
    "option",
    "output",
    "progress",
    "select",
    "textarea",
]


# menu is text content, as MDN has it, and listed there alone
INTERACTIVE_ELEMENTS: list[str] = ["details", "dialog", "summary"]


WEB_COMPONENTS: list[str] = ["slot", "template"]


ALL_ELEMENTS: list[str] = MAIN_ROOT + DOCUMENT_METADATA

ALL_ELEMENTS.extend(SECTIONING_ROOT + CONTENT_SECTIONING)

ALL_ELEMENTS.extend(TEXT_CONTENT + INLINE_TEXT_SEMANTICS)

ALL_ELEMENTS.extend(IMAGE_AND_MULTIMEDIA + EMBEDDED_CONTENT)

ALL_ELEMENTS.extend(SVG_AND_MATHML + SCRIPTING)

ALL_ELEMENTS.extend(DEMARCATING_EDITS + TABLE_CONTENT)

ALL_ELEMENTS.extend(FORMS + INTERACTIVE_ELEMENTS + WEB_COMPONENTS)


def attr_slots(node: Stan) -> list[tuple[str, str]]:
    """An element's own attribute slots, from its data-attr: "id=row_id,
    title=hint" is [("id", "row_id"), ("title", "hint")]. The one reading of
    data-attr: a pair without both a name and a slot is no slot, and only the
    first = divides one."""
    mapping = str(node.attributes.get("data-attr", ""))
    pairs = (pair.partition("=") for pair in mapping.split(",") if pair)
    return [(name, slot) for name, eq, slot in pairs if eq and name and slot]


class Stan:
    def __init__(self, tagname: str, *args: Any, **kwargs: Any) -> None:
        self.clone: bool = False
        self.tagname: str = tagname
        self.attributes: dict[str, Any] = dict(kwargs)
        self.children: list[Any] = list(args)

    def __call__(self, **kwargs: Any) -> Stan:
        if self.clone:
            self = self.copy()
        # Short names for mumulib's own attributes, none of them HTML's, so
        # they shadow nothing: pat="row" is data-pat="row", slt="name" is
        # data-slot="name" -- slot itself is HTML's, for shadow DOM --
        # attr="href=url" or attr={"href": "url"} is data-attr="href=url",
        # and live=True is data-live
        if "pat" in kwargs:
            kwargs["data-pat"] = kwargs.pop("pat")
        if "slt" in kwargs:
            kwargs["data-slot"] = kwargs.pop("slt")
        # live=True is data-live: an element mumulib's live.js keeps up to date
        if "live" in kwargs:
            kwargs["data-live"] = kwargs.pop("live")
        if "attr" in kwargs:
            mapping = kwargs.pop("attr")
            if isinstance(mapping, dict):
                pairs = cast(dict[str, str], mapping).items()
                mapping = ",".join(f"{name}={slot}" for name, slot in pairs)
            kwargs["data-attr"] = mapping
        self.attributes = self.attributes | kwargs
        return self

    def __getitem__(self, item: Any) -> Stan:
        if self.clone:
            self = self.copy()
        # t.p["a", t.b["b"]] is two children, as t.p[["a", t.b["b"]]] is
        if isinstance(item, (list, tuple)):
            self.children.extend(cast(list[Any] | tuple[Any, ...], item))
        else:
            self.children.append(item)
        return self

    def copy(self) -> Stan:
        children = [getattr(child, "copy", lambda: child)() for child in self.children]
        attributes = {
            k: getattr(v, "copy", lambda: v)() for k, v in self.attributes.items()
        }
        result = Stan(self.tagname, *children, **attributes)
        return result

    def clone_pat(self, patname: str, **slots: Any) -> Stan | None:
        if self.attributes.get("data-pat") == patname:
            copy = self.copy()

            for k, v in slots.items():
                copy.fill_slots(k, v)
            # fill_slots fills what is below an element: the pattern's own
            # attribute slots, data-attr on the pattern itself, are filled here
            for attrname, slotname in attr_slots(copy):
                if slotname in slots:
                    copy.attributes[attrname] = slots[slotname]
            return copy
        for child in self.children:
            if isinstance(child, Stan):
                result = child.clone_pat(patname, **slots)
                if result:
                    return result
        return None

    def clear_slots(self, slotname: str) -> None:
        for child in self.children:
            if not isinstance(child, Stan):
                continue
            if child.attributes.get("data-slot") != slotname:
                child.clear_slots(slotname)
                continue
            child.children = []

    def fill_slots(self, slotname: str, value: Any) -> None:
        for i, child in enumerate(self.children):
            if not isinstance(child, Stan):
                continue
            for attrname, attrslotname in attr_slots(child):
                if attrslotname == slotname:
                    child.attributes[attrname] = value
            if child.attributes.get("data-slot") != slotname:
                child.fill_slots(slotname, value)
                continue
            if isinstance(value, Stan):
                self.children[i] = value.copy()
            elif isinstance(value, list):
                child.children = []
                for node in cast(list[Any], value):
                    if isinstance(node, Stan):
                        child.children.append(node.copy())
                    else:
                        child.children.append(node)
            else:
                child.children = [value]

    def append_slots(self, slotname: str, value: Any) -> None:
        for child in self.children:
            if not isinstance(child, Stan):
                continue
            for attrname, attrslotname in attr_slots(child):
                if attrslotname == slotname:
                    child.attributes[attrname] = value
            if child.attributes.get("data-slot") != slotname:
                child.append_slots(slotname, value)
                continue
            if isinstance(value, Stan):
                node = value.copy()
                child.children.append(node)
            elif isinstance(value, list):
                for node in cast(list[Any], value):
                    if isinstance(node, Stan):
                        child.children.append(node.copy())
                    else:
                        child.children.append(node)
            else:
                child.children.append(value)

    def __repr__(self) -> str:
        return self.nested_repr(0)

    def nested_repr(self, depth: int) -> str:
        """Its repr, as Python that would make it, its children indented
        below it as deep as depth says it is."""
        result = f"every.{self.tagname}"
        if self.attributes:
            result += "("
            for x in self.attributes:
                result += f"{x}={repr(self.attributes[x])}, "
            result = result[:-2] + ")"
        if self.children:
            indent = "    " * (depth + 1)
            children = [
                x.nested_repr(depth + 1) if isinstance(x, Stan) else repr(x)
                for x in self.children
            ]
            result += "[\n" + indent + (",\n" + indent).join(children)
            result += "\n" + "    " * depth + "]"

        return result


class TagGroup:
    def __init__(self, *tags: str) -> None:
        for tag in tags:
            newtag = Stan(tag)
            newtag.clone = True
            setattr(self, tag, newtag)

    if TYPE_CHECKING:
        # The tags are set with setattr, so declare them for type checkers:
        # tags.every.div is a Stan. Not defined at runtime, so a misspelt tag
        # still raises AttributeError.
        def __getattr__(self, name: str) -> Stan: ...


main_root = TagGroup(*MAIN_ROOT)
document_metadata = TagGroup(*DOCUMENT_METADATA)
sectioning_root = TagGroup(*SECTIONING_ROOT)
content_sectioning = TagGroup(*CONTENT_SECTIONING)
text_content = TagGroup(*TEXT_CONTENT)
inline_text_semantics = TagGroup(*INLINE_TEXT_SEMANTICS)
image_and_multimedia = TagGroup(*IMAGE_AND_MULTIMEDIA)
embedded_content = TagGroup(*EMBEDDED_CONTENT)
svg_and_mathml = TagGroup(*SVG_AND_MATHML)
scripting = TagGroup(*SCRIPTING)
demarcating_edits = TagGroup(*DEMARCATING_EDITS)
table_content = TagGroup(*TABLE_CONTENT)
forms = TagGroup(*FORMS)
interactive_elements = TagGroup(*INTERACTIVE_ELEMENTS)
web_components = TagGroup(*WEB_COMPONENTS)
every = TagGroup(*ALL_ELEMENTS)


class _TemplateParser(HTMLParser):
    """A template's elements as Stan, as the standard library's parser reads
    them: character references decoded, in text and attribute values alike;
    comments and the doctype passed over; text that is only whitespace
    dropped, and any other kept where it is."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.top: list[Any] = []
        self.open: list[Stan] = []

    def _add(self, child: Any) -> None:
        (self.open[-1].children if self.open else self.top).append(child)

    def _element(self, tag: str, attrs: list[tuple[str, str | None]]) -> Stan:
        # An attribute with no value, disabled, is its own name, as HTML has it
        node = Stan(tag, **{k: k if v is None else v for k, v in attrs})
        self._add(node)
        return node

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = self._element(tag, attrs)
        # A void element, <img>, has no end tag, and nothing inside it
        if tag not in VOID_ELEMENTS_SET:
            self.open.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._element(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        # The element it names closes, and any left open inside it; an end
        # tag with nothing of its name open is passed over
        for depth in range(len(self.open) - 1, -1, -1):
            if self.open[depth].tagname == tag:
                del self.open[depth:]
                return

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._add(data)


def parse_template(source: IO[bytes]) -> Stan | None:
    """A template, read as UTF-8 HTML, as a tree of Stan: a whole page as
    its <html>, and a fragment put in a <body> in one, as a browser would.
    None if it has no element at all."""
    parser = _TemplateParser()
    parser.feed(source.read().decode("utf-8"))
    parser.close()
    if not any(isinstance(child, Stan) for child in parser.top):
        return None
    first = parser.top[0]
    if len(parser.top) == 1 and isinstance(first, Stan) and first.tagname == "html":
        root = first
    else:
        root = Stan("html", Stan("body", *parser.top))
    return root


def _parse_file(filename: str) -> Stan | None:
    with open(filename, "rb") as source:
        return parse_template(source)


class Template:
    def __init__(self, filename: str) -> None:
        self.filename: str = filename
        self.loaded: bool = False
        self.template: Stan | None = None
        self.root: Stan | None = None

    async def load(self) -> Template:
        """Its file, read and parsed in a thread, so the event loop is not
        kept waiting on the disk: template = await Template(path).load().
        What is done with it after is done in memory, and needs no await."""
        self.template = await asyncio.to_thread(_parse_file, self.filename)
        self.root = self.template.copy() if self.template else None
        self.loaded = True
        return self

    def _check_loaded(self) -> None:
        if not self.loaded:
            raise RuntimeError(
                f"Template {self.filename} is not loaded: await its load() first"
            )

    def clone_pat(self, patname: str, **slots: Any) -> Stan:
        self._check_loaded()
        current = self.template
        if not current:
            raise ValueError("Template failed to load")
        for child in current.children:
            if not isinstance(child, Stan):
                continue
            result = child.clone_pat(patname, **slots)
            if result:
                attrslots = attr_slots(result)
                for k, v in slots.items():
                    if result.attributes.get("data-slot") == k:
                        if isinstance(v, Stan):
                            result = v
                        else:
                            result.children = [v]
                    for attrname, attrslotname in attrslots:
                        if attrslotname == k:
                            result.attributes[attrname] = v
                return result
        else:
            raise ValueError(f"Pattern {patname} not found in template.")

    def fill_slots(self, slotname: str, value: Any) -> None:
        self._check_loaded()
        if self.root:
            self.root.fill_slots(slotname, value)

    def clear_slots(self, slotname: str) -> None:
        self._check_loaded()
        if self.root:
            self.root.clear_slots(slotname)

    def append_slots(self, slotname: str, value: Any) -> None:
        self._check_loaded()
        if self.root:
            self.root.append_slots(slotname, value)


def clear_slots(node: Stan, slotname: str) -> None:
    return node.clear_slots(slotname)


def fill_slots(node: Stan, slotname: str, value: Any) -> None:
    return node.fill_slots(slotname, value)


def append_slots(node: Stan, slotname: str, value: Any) -> None:
    return node.append_slots(slotname, value)


# Where consumers_app, given changes=, serves the change stream and the
# script that keeps a page's data-live elements up to date by it
LIVE_SCRIPT_URL = "/mumulib/live.js"


def page(
    title: str,
    *content: Any,
    stylesheets: tuple[str, ...] | list[str] = (),
    scripts: tuple[str, ...] | list[str] = (),
    live: bool = False,
) -> Stan:
    """A whole page: the doctype, a UTF-8 charset and a viewport, its title,
    a <link> for each stylesheet and a deferred <script> for each script in
    its <head>, and content as its <body>. With live, mumulib's live.js too,
    which keeps the page's data-live elements up to date (consumers_app,
    given changes=, serves it).
    """
    sources = [*scripts, *([LIVE_SCRIPT_URL] if live else [])]
    head: list[Any] = [
        every.meta(charset="utf-8"),
        every.meta(name="viewport", content="width=device-width, initial-scale=1"),
        every.title[title],
        *(every.link(rel="stylesheet", href=href) for href in stylesheets),
        *(every.script(src=src, defer=True) for src in sources),
    ]
    return every.html[every.head[head], every.body[list(content)]]


class Markup(str):
    """Text that is HTML already, written out as it is rather than escaped:
    for markup you wrote, never for anything a visitor sent."""


# Elements whose content a browser reads as raw text, not as HTML: escaping
# it would put a literal &amp; in a script. Nothing here escapes it, so what
# goes in one must be safe there already.
RAW_TEXT_ELEMENTS = frozenset({"script", "style"})


# Elements whose whitespace is part of what is in them: a textarea's value,
# a pre's text. The newlines and indents that lay out the rest of a page
# would be added to it, so nothing is added inside one, at any depth
PREFORMATTED_ELEMENTS = frozenset({"pre", "textarea", "listing"})

# Elements that sit in a line of text: a newline or an indent beside one, or
# in it, is a space in the line -- "Hello <b>world</b>!" laid out would say
# "Hello world !" -- so each is written compact, nothing added in or around
# it, at any depth
INLINE_ELEMENTS = frozenset(
    INLINE_TEXT_SEMANTICS
    + DEMARCATING_EDITS
    + ["img", "picture"]
    + ["button", "input", "label", "meter", "output", "progress", "select"]
)


# What a tree holds as text: escaped, and numbers as their digits
TEXT_TYPES = (str, int, float)


def escape_text(child: Any, tagname: str) -> str:
    """A text child as HTML: escaped, unless it is Markup or in a script or
    style, which are written as they are."""
    text = str(child)
    if isinstance(child, Markup) or tagname in RAW_TEXT_ELEMENTS:
        return text
    return html.escape(text, quote=False)


async def produce_child(child: Any, state: State) -> AsyncIterator[str]:
    """A child that is neither text nor a tree, as HTML: what a producer
    makes of it -- a dict its listing, a Resource its page. With no HTML of
    its own, it is an error naming its type, as in JSON; not its repr."""
    try:
        # A fragment of this page, not a page of its own: a listing is its
        # links alone, and no doctype or heading of its own
        async for chunk in producers.produce(child, {**state, "fragment": True}):
            if not isinstance(chunk, str):
                raise TypeError(f"a {type(child).__name__} produced no HTML")
            yield chunk
    except mumutypes.NotFoundResponse:
        raise TypeError(f"a {type(child).__name__} has no HTML form") from None


class Line:
    """Whether what has been written of a page so far ends a line: one for
    the whole page, shared by every element in it, so a block's tags go on
    lines of their own, with no blank line between."""

    def __init__(self) -> None:
        self.at_start = True

    def wrote(self, chunk: str) -> str:
        """chunk, noted as written."""
        if chunk:
            self.at_start = chunk.endswith("\n")
        return chunk


# What the state carries down a page, element to element, as it is written:
# how deep the element is, whether it is in an inline or preformatted one,
# and the page's Line
DEPTH = "html_depth"
COMPACT = "html_compact"
LINE = "html_line"

# One level of a page's indent
INDENT = "    "


async def produce_html(thing: Stan, state: State) -> AsyncIterator[str]:
    """thing as HTML, laid out: a block on lines of its own, as deep as it
    is, and what it holds on lines indented below it -- except where
    whitespace would show: in and around an INLINE_ELEMENTS element, and in a
    PREFORMATTED_ELEMENTS element, where nothing is added. The depth, the
    compactness and the Line come from the element it is in, in the state."""
    line = state.get(LINE)
    if not isinstance(line, Line):
        line = Line()
        state = {**state, LINE: line}
    depth = int(state.get(DEPTH, 0))
    compact = bool(state.get(COMPACT, False))
    # A whole page says it is HTML: without the doctype, a browser renders it
    # in quirks mode. parse_template drops a template's own, as it reads it.
    if thing.tagname == "html":
        yield line.wrote("<!doctype html>\n")
    preformatted = thing.tagname in PREFORMATTED_ELEMENTS
    # An inline element is compact around itself, too; a pre, a block, is
    # laid out as any other, outside it
    flat = compact or thing.tagname in INLINE_ELEMENTS
    indent = INDENT * depth
    before = "" if flat else ("" if line.at_start else "\n") + indent
    yield line.wrote(f"{before}<{thing.tagname}")
    if thing.attributes:
        for k, v in thing.attributes.items():
            # A boolean attribute is so by being there at all: True writes
            # its name, and False or None leaves it out
            if v is True:
                yield line.wrote(f" {k}")
                continue
            if v is False or v is None:
                continue
            attrpartchunks: list[str] = []
            # An attribute is text, whatever type the page is asked for as:
            # produced as text/plain, not as the URL's HTML or JSON
            as_text = {**state, "accept": ["text/plain", "*/*"]}
            try:
                async for chunk in producers.produce(v, as_text):
                    # An attribute is text: bytes or a SpecialResponse here is
                    # a mistake to report, not something to write as its repr.
                    if not isinstance(chunk, str):
                        raise TypeError(
                            f"attribute {k!r} produced {type(chunk).__name__}, not str"
                        )
                    attrpartchunks.append(chunk)
            except mumutypes.NotFoundResponse:
                raise TypeError(
                    f"attribute {k!r} is a {type(v).__name__}, which has no text"
                ) from None
            # Escaped whole, quotes and all: an attribute is never markup
            attrpartval = html.escape("".join(attrpartchunks), quote=True)
            yield line.wrote(f' {k}="{attrpartval}"')
    if thing.tagname in VOID_ELEMENTS_SET:
        yield line.wrote(" />" if flat else " />\n")
        return
    # A newline straight after a pre or textarea's start tag is dropped as
    # the page is read, so one is always written: then what is in it keeps
    # its own, if it begins with one
    yield line.wrote(">\n" if preformatted or not flat else ">")
    inner = {**state, DEPTH: depth + 1, COMPACT: flat or preformatted}
    for child in thing.children:
        if isinstance(child, Stan) and not (
            inner[COMPACT] or child.tagname in INLINE_ELEMENTS
        ):
            # A block lays itself out
            async for chunk in produce_html(child, inner):
                yield chunk
            continue
        # Text, an inline element, or what a producer makes of a child: a
        # line of a block begins with its indent, which a browser ignores
        if not inner[COMPACT] and line.at_start:
            yield line.wrote(INDENT * (depth + 1))
        if isinstance(child, Stan):
            async for chunk in produce_html(child, inner):
                yield chunk
        elif isinstance(child, TEXT_TYPES) and not isinstance(child, bool):
            # Text is text: a visitor's < is shown, not obeyed
            yield line.wrote(escape_text(child, thing.tagname))
        else:
            async for chunk in produce_child(child, inner):
                yield line.wrote(chunk)
    if flat:
        yield line.wrote(f"</{thing.tagname}>")
    elif preformatted:
        yield line.wrote(f"</{thing.tagname}>\n")
    else:
        yield line.wrote(
            ("" if line.at_start else "\n") + f"{indent}</{thing.tagname}>\n"
        )


producers.add_producer(Stan, produce_html)


async def produce_markup(thing: Markup, state: State) -> AsyncIterator[str]:
    """Markup at .html: HTML already, written out as it is."""
    yield str(thing)


# HTML of your own, and only as HTML: a plain string is text, never markup
producers.add_producer(Markup, produce_markup, "text/html")
