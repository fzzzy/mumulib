

from lxml import etree


# From MDN reference
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


class Stan(object):
    def __init__(self, tagname, indent, *args, **kwargs):
        self.tagname = tagname
        self.indent = indent
        self.attributes = dict(kwargs)
        self.children = list(args)

    def __call__(self, **kwargs):
        if 'indent' in kwargs:
            self.indent = kwargs.pop('indent')
        self.attributes | kwargs
        return self

    def __getitem__(self, item):
        ## Check if item is a list
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
        return Stan(
            self.tagname, self.indent, *children, **attributes)

    def clone_pat(self, patname, **slots):
        if self.attributes.get("data-pat") == patname:
            copy = self.copy()
            for k, v in slots.items():
                fill_slots(copy, k, v)
            return copy
        for child in self.children:
            if isinstance(child, Stan):
                result = child.clone_pat(patname, **slots)
                if result:
                    return result

    def fill_slots(self, slotname, value):
        for child in self.children:
            if not isinstance(child, Stan):
                continue
            if child.attributes.get("data-slot") != slotname:
                child.fill_slots(slotname, value)
                continue
            if isinstance(value, Stan):
                node = value.copy()
                self.children.replace(child, node)
            elif isinstance(value, list):
                child.children = []
                for node in value:
                    if isinstance(node, Stan):
                        child.children.append(node.copy())
                    else:
                        child.children.append(node)
            else:
                child.children = [value]

    def append_slots(self, slotname, value):
        for child in self.children:
            if not isinstance(child, Stan):
                continue
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
                result += f", {x}={repr(self.attributes[x])}"
            result += ")"
        if self.children:
            indent = "    " * (self.indent + 1)
            result += "[\n" + indent
            for x in self.children:
                result += repr(x) + ",\n" + indent
            unindent = "    " * self.indent
            chars = len(indent) + 2
            result = result[:-chars] + "\n" + unindent + "]"

        return result


class Entity(object):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"Entity({self.name})"


class TagGroup(object):
    def __init__(self, *tags):
        for tag in tags:
            setattr(self, tag, Stan(tag, 0))


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


class Pattern(object):
    def __init__(self, name, pattern):
        self.name = name
        self.pattern = pattern

    def copy(self):
        return self.pattern.copy()


class Slot(object):
    def __init__(self, name, contents):
        self.name = name
        self.contents = contents
        self.filled_contents = None

    def fill(self, value):
        self.filled_contents = value


def parse_template(source):
    context = etree.iterparse(
        source, events=("start", "end"), html=True)

    root = None
    current = None
    stack = []
    indent = 0

    for event, elem in context:
        if event == "start":
            newtag = Stan(elem.tag, indent, **elem.attrib)
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
            else:
                print(elem, repr(elem.text))

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
    print(root)
    return root



class Template(object):
    def __init__(self, filename):
        self.filename = filename
        self.loaded = False

    def load(self):
        self.loaded = True
        self.root = parse_template(self.filename)

    def clone_pat(self, patname, **slots):
        if not self.loaded:
            self.load()
        current = self.root
        for child in current.children:
            if not isinstance(child, Stan):
                continue
            result = child.clone_pat(patname, **slots)
            if result:
                return result
        else:
            raise ValueError(f"Pattern {patname} not found in template.")


def fill_slots(node, slotname, value):
    return node.fill_slots(slotname, value)


def append_slots(node, slotname, value):
    return node.append_slots(slotname, value)


if __name__ == "__main__":
    t = Template("templates.html")
    t.load()
    root = t.root
    person1 = t.clone_pat("person", name="John Doe", age="25", color="blue")
    person2 = t.clone_pat("person", name="Jane Doe", age="93", color="mauve")
    root.fill_slots("people", [person1, person2])
    print(root)