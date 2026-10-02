"""XML: a dict as XML, for the readers that read it best -- language models.

    {"name": "Ada", "age": 3, "tags": ["a", "b"], "ok": true, "x": null}

as a Person's state, at /people/ada.xml, is

    <?xml version="1.0" encoding="UTF-8"?>
    <Person type="object">
      <name type="string">Ada</name>
      <age type="number">3</age>
      <tags type="array">
        <item type="string">a</item>
        <item type="string">b</item>
      </tags>
      <ok type="boolean">true</ok>
      <x type="null"/>
    </Person>

Each key is an element's name, as the common JSON-to-XML convention writes
it, and each element says its type, by JSON's name for it (design/xml.md).
A key that is no element name -- 1st, a b, 0 -- is <entry key="1st">. The
root is named by what the document is: a resource's or a persist's class,
or dict for a plain one. A list's elements are <item>s.

Only a dict is XML -- a plain dict, a resource's state, a persist's document
-- and anything else at .xml is not found. A resource or a persist inside a
plain dict is the URL of its own, a string, as in JSON: of its .xml.
"""

import re
from collections.abc import AsyncIterator
from types import MappingProxyType
from typing import Any, cast
from xml.sax.saxutils import escape, quoteattr

from mumulib.consumers import linked
from mumulib.mumutypes import Chunk, State
from mumulib.producers import add_producer, container_url, custom_serializer

__all__ = ["XmlOf"]

# An element's name: a letter or underscore, then letters, digits, _ . -;
# never xml in any case, which XML keeps for itself. Conservative: a key
# that is any other XML name is written as an <entry> too.
_NAME = re.compile(r"(?!(?i:xml))[A-Za-z_][A-Za-z0-9_.-]*\Z")

# What XML 1.0 cannot hold, even as a character reference
_UNWRITABLE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _open(key: str, kind: str) -> str:
    if _NAME.match(key):
        return f'<{key} type="{kind}"'
    return f'<entry key={quoteattr(key)} type="{kind}"'


def _close(key: str) -> str:
    return f"</{key}>" if _NAME.match(key) else "</entry>"


def _text(value: str) -> str:
    if _UNWRITABLE.search(value):
        raise ValueError("a string holds a character XML cannot")
    return escape(value)


def _element(key: str, value: Any, indent: str) -> list[str]:
    """The lines of one element, key's, holding value."""
    if isinstance(value, (dict, MappingProxyType)):
        entries = cast(dict[Any, Any], value).items()
        return _container(key, "object", [(str(k), v) for k, v in entries], indent)
    if isinstance(value, (list, tuple)):
        items = cast(list[Any], value)
        return _container(key, "array", [("item", v) for v in items], indent)
    if value is None:
        return [f"{indent}{_open(key, 'null')}/>"]
    if isinstance(value, bool):
        text, kind = ("true" if value else "false"), "boolean"
    elif isinstance(value, (int, float)):
        text, kind = repr(value), "number"
    elif isinstance(value, str):
        text, kind = _text(value), "string"
    else:
        # A type given a JSON form is that form; anything else, an error
        return _element(key, custom_serializer(value), indent)
    return [f"{indent}{_open(key, kind)}>{text}{_close(key)}"]


def _container(
    key: str, kind: str, entries: list[tuple[str, Any]], indent: str
) -> list[str]:
    if not entries:
        return [f"{indent}{_open(key, kind)}/>"]
    lines = [f"{indent}{_open(key, kind)}>"]
    for name, value in entries:
        lines.extend(_element(name, value, indent + "  "))
    lines.append(f"{indent}{_close(key)}")
    return lines


def to_xml(document: Any, root: str) -> str:
    """document, a dict, as an XML document whose root element is root."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', *_element(root, document, "")]
    return "\n".join(lines) + "\n"


class XmlOf:
    """A document to be XML, with the name of its root: what a resource or a
    persist answers .xml with, its state named by its class."""

    def __init__(self, document: Any, root: str) -> None:
        self.document = document
        self.root = root


async def _produce_xml_of(thing: XmlOf, state: State) -> AsyncIterator[Chunk]:
    yield to_xml(thing.document, thing.root)


async def _produce_xml(thing: Any, state: State) -> AsyncIterator[Chunk]:
    base = container_url(state.get("url", "/"))
    yield to_xml(linked(thing, base, "xml"), "dict")


add_producer(XmlOf, _produce_xml_of, "application/xml")
for _dict_type in (dict, MappingProxyType):
    add_producer(_dict_type, _produce_xml, "application/xml")
