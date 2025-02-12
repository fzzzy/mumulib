

from mumulib import producers

from lxml import etree


# From MDN reference
VOID_ELEMENTS = [
    'area',
    'base',
    'br',
    'col',
    'embed',
    'hr',
    'img',
    'input',
    'link',
    'meta',
    'source',
    'track',
    'wbr'
]


VOID_ELEMENTS_SET = set(VOID_ELEMENTS)


MAIN_ROOT = [
    'html'
]


DOCUMENT_METADATA = [
    'base',
    'head',
    'link',
    'meta',
    'style',
    'title'
]


SECTIONING_ROOT = [
    'body'
]


CONTENT_SECTIONING = [
    'address',
    'article',
    'aside',
    'footer',
    'header',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hgroup',
    'main',
    'nav',
    'section',
    'search'
]


TEXT_CONTENT = [
    'blockquote',
    'dd',
    'div',
    'dl',
    'dt',
    'figcaption',
    'figure',
    'hr',
    'li',
    'menu',
    'ol',
    'p',
    'pre',
    'ul'
]


INLINE_TEXT_SEMANTICS = [
    'a',
    'abbr',
    'b',
    'bdi',
    'bdo',
    'br',
    'cite',
    'code',
    'data',
    'dfn',
    'em',
    'i',
    'kbd',
    'mark',
    'q',
    'rp',
    'rt',
    'ruby',
    's',
    'samp',
    'small',
    'span',
    'strong',
    'sub',
    'sup',
    'time',
    'u',
    'var',
    'wbr'
]


IMAGE_AND_MULTIMEDIA = [
    'area',
    'audio',
    'img',
    'map',
    'track',
    'video'
]


EMBEDDED_CONTENT = [
    'embed',
    'fencedframe',
    'iframe',
    'object',
    'picture',
    'source'
]


SVG_AND_MATHML = [
    'svg',
    'math'
]


SCRIPTING = [
    'canvas',
    'noscript',
    'script'
]


DEMARCATING_EDITS = [
    'del',
    'ins'
]


TABLE_CONTENT = [
    'caption',
    'col',
    'colgroup',
    'table',
    'tbody',
    'td',
    'tfoot',
    'th',
    'thead',
    'tr',
]


FORMS = [
    'button',
    'datalist',
    'fieldset',
    'form',
    'input',
    'label',
    'legend',
    'meter',
    'optgroup',
    'option',
    'output',
    'progress',
    'select',
    'textarea'
]


INTERACTIVE_ELEMENTS = [
    'details',
    'dialog',
    'menu',
    'summary'
]


WEB_COMPONENTS = [
    'slot',
    'template'
]


ALL_ELEMENTS = MAIN_ROOT + DOCUMENT_METADATA + SECTIONING_ROOT + CONTENT_SECTIONING + TEXT_CONTENT + INLINE_TEXT_SEMANTICS + IMAGE_AND_MULTIMEDIA + EMBEDDED_CONTENT + SVG_AND_MATHML + SCRIPTING + DEMARCATING_EDITS + TABLE_CONTENT + FORMS + INTERACTIVE_ELEMENTS + WEB_COMPONENTS


def reindent_tree(node, indent):
    node.indent = indent
    for child in node.children:
        if isinstance(child, Stan):
            reindent_tree(child, indent + 1)


class Stan(object):
    def __init__(self, tagname, indent, *args, **kwargs):
        self.clone = False
        self.tagname = tagname
        self.indent = indent
        self.attributes = dict(kwargs)
        self.children = list(args)

    def __call__(self, **kwargs):
        if self.clone:
            self = self.copy()
        if 'indent' in kwargs:
            self.indent = kwargs.pop('indent')
        self.attributes = self.attributes | kwargs
        return self

    def __getitem__(self, item):
        if self.clone:
            self = self.copy()
        if isinstance(item, list):
            for child in item:
                if isinstance(child, Stan):
                    child.indent = self.indent + 1
            self.children.extend(item)
        else:
            if isinstance(item, Stan):
                item.indent = self.indent + 1
            self.children.append(item)
        return self

    def copy(self):
        children = [
            getattr(child, 'copy', lambda: child)()
            for child in self.children]
        attributes = {
            k: getattr(v, 'copy', lambda: v)()
            for k, v in self.attributes.items()}
        result = Stan(
            self.tagname, 0, *children, **attributes)
        return result

    def clone_pat(self, patname, **slots):
        if self.attributes.get("data-pat") == patname:
            copy = self.copy()
            reindent_tree(copy, 0)

            for k, v in slots.items():
                copy.fill_slots(k, v)
            return copy
        for child in self.children:
            if isinstance(child, Stan):
                result = child.clone_pat(patname, **slots)
                if result:
                    return result

    def clear_slots(self, slotname):
        for child in self.children:
            if not isinstance(child, Stan):
                continue
            if child.attributes.get("data-slot") != slotname:
                child.clear_slots(slotname)
                continue
            child.children = []

    def fill_slots(self, slotname, value):
        for i, child in enumerate(self.children):
            if not isinstance(child, Stan):
                continue
            attrslots = child.attributes.get("data-attr")
            if attrslots:
                attrslots = attrslots.split(",")
                attrslots = [
                    (k, v) for k, v in (x.split("=") for x in attrslots)]
                for attrname, attrslotname in attrslots:
                    if attrslotname == slotname:
                        child.attributes[attrname] = value
            if child.attributes.get("data-slot") != slotname:
                if isinstance(value, Stan):
                    reindent_tree(value, self.indent + 1)
                child.fill_slots(slotname, value)
                continue
            if isinstance(value, Stan):
                node = value.copy()
                reindent_tree(node, self.indent + 1)
                self.children[i] = node
            elif isinstance(value, list):
                child.children = []
                for node in value:
                    if isinstance(node, Stan):
                        newnode = node.copy()
                        reindent_tree(newnode, self.indent + 1)
                        child.children.append(newnode)
                    else:
                        child.children.append(node)
            else:
                child.children = [value]

    def append_slots(self, slotname, value):
        for child in self.children:
            if not isinstance(child, Stan):
                continue
            attrslots = child.attributes.get("data-attr")
            if attrslots:
                attrslots = attrslots.split(",")
                attrslots = [
                    (k, v) for k, v in (x.split("=") for x in attrslots)]
                for attrname, attrslotname in attrslots:
                    if attrslotname == slotname:
                        child.attributes[attrname] = value
            if child.attributes.get("data-slot") != slotname:
                child.append_slots(slotname, value)
                continue
            if isinstance(value, Stan):
                node = value.copy()
                child.children.append(node)
            elif isinstance(value, list):
                for node in value:
                    if isinstance(node, Stan):
                        child.children.append(node.copy())
                    else:
                        child.children.append(node)
            else:
                child.children.append(value)

    def __repr__(self):
        result = f"all.{self.tagname}"
        if self.attributes:
            result += "("
            for x in self.attributes:
                result += f"{x}={repr(self.attributes[x])}, "
            result = result[:-2] + ")"
        if self.children:
            indent = "    " * (self.indent + 1)
            result += "[\n" + indent
            for x in self.children:
                result += repr(x) + ",\n" + indent
            unindent = "    " * self.indent
            chars = len(indent) + 2
            result = result[:-chars] + "\n" + unindent + "]"

        return result


class TagGroup(object):
    def __init__(self, *tags):
        for tag in tags:
            newtag = Stan(tag, 0)
            newtag.clone = True
            setattr(self, tag, newtag)


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
all = TagGroup(*ALL_ELEMENTS)


def parse_template(source):
    context = etree.iterparse(
        source, events=("start", "end"), html=True, encoding="UTF-8")

    root = None
    current = None
    stack = []
    indent = 0

    for event, elem in context:
        if event == "start":
            newtag = Stan(elem.tag.lower(), indent, **elem.attrib)
            indent += 1
            if current is None:
                root = newtag
                current = newtag
            else:
                stack.append(current)
                current[newtag]
                current = newtag

            if elem.text and elem.text.replace("\n", "").replace(" ", ""):
                current[elem.text]

        elif event == "end":
            if elem.tail and elem.tail.strip():
                current[elem.tail]

            if current and current.tagname == elem.tag:
                if stack:
                    indent -= 1
                    current = stack.pop()
                else:
                    current = None
            # Clean up to free memory
            elem.clear()
    return root


class Template(object):
    def __init__(self, filename):
        self.filename = filename
        self.loaded = False

    def load(self):
        self.loaded = True
        self.template = parse_template(open(self.filename, 'rb'))
        self.root = self.template.copy()
        return self

    def clone_pat(self, patname, **slots):
        if not self.loaded:
            self.load()
        current = self.template
        for child in current.children:
            if not isinstance(child, Stan):
                continue
            result = child.clone_pat(patname, **slots)
            if result:
                attrslots = result.attributes.get("data-attr", "")
                attrslots = attrslots.split(",")
                attrslots = [
                    (k, v) for k, v in (x.split("=") for x in attrslots if x)]
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

    def fill_slots(self, slotname, value):
        if not self.loaded:
            self.load()
        self.root.fill_slots(slotname, value)

    def clear_slots(self, slotname):
        if not self.loaded:
            self.load()
        self.root.clear_slots(slotname)

    def append_slots(self, slotname, value):
        if not self.loaded:
            self.load()
        self.root.append_slots(slotname, value)


def clear_slots(node, slotname):
    return node.clear_slots(slotname)


def fill_slots(node, slotname, value):
    return node.fill_slots(slotname, value)


def append_slots(node, slotname, value):
    return node.append_slots(slotname, value)


async def produce_html(thing, state):
    indent = "    " * thing.indent
    yield f"{indent}<{thing.tagname}"
    if thing.attributes:
        for k, v in thing.attributes.items():
            attrpartchunks = []
            async for chunk in producers.produce(v, state):
                attrpartchunks.append(chunk)
            attrpartval = "".join(
                attrpartchunks).replace('"', '&quot;')
            attrpart = f' {k}="{attrpartval}"'
            yield attrpart
    if thing.tagname in VOID_ELEMENTS_SET:
        yield " />\n"
        return
    yield ">\n"
    if thing.children:
        for child in thing.children:
            if isinstance(child, Stan):
                async for chunk in produce_html(child, state):
                    yield chunk
            else:
                yield child
    yield f"\n{indent}</{thing.tagname}>\n"


producers.add_producer(Stan, produce_html)



