"""\
@file producers.py
@author Donovan Preston

Copyright (c) 2007, Linden Research, Inc.
Copyright (c) 2024-2026, Donovan Preston

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import html
import inspect
import json
from collections.abc import AsyncGenerator, Callable, Iterable
from io import BufferedReader, TextIOWrapper
from pathlib import Path, PurePath
from types import (
    BuiltinFunctionType,
    FunctionType,
    GeneratorType,
    MappingProxyType,
    MethodType,
    MethodWrapperType,
)
from typing import Any, cast
from urllib.parse import quote

import aiofiles

from mumulib import mumutypes
from mumulib.mumutypes import Chunk, Producer, State

# The public API: Turning an object into a response, and teaching it a new
# type to turn. The built-in producers are the module's own.
__all__ = [
    "produce",
    "add_producer",
    "add_json_form",
]


# What a type's things are as JSON, for those that are not JSON themselves:
# found by exact type, as producers and consumers are
_json_forms: dict[type[Any], Callable[[Any], Any]] = {}


def add_json_form(adapter_for_type: type[Any], to_json: Callable[[Any], Any]) -> None:
    """Say what a type's things are in JSON: to_json(thing), something JSON
    can hold -- a Resource is its state. It is used wherever one is found,
    at the top or deep in a dict or a list."""
    _json_forms[adapter_for_type] = to_json


def custom_serializer(obj: object) -> Any:
    to_json = _json_forms.get(type(obj))
    if to_json is not None:
        return to_json(obj)
    if isinstance(obj, MappingProxyType):
        # isinstance cannot recover the proxy's type parameters.
        return dict(cast(MappingProxyType[str, Any], obj))
    # Anything else with no JSON of its own is an error, not a quiet null
    raise TypeError(f"a {type(obj).__name__} has no JSON form")


_producer_adapters: dict[str, dict[type[Any], Producer]] = {}


def add_producer(
    adapter_for_type: type[Any], conv: Producer, mime_type: str = "*/*"
) -> None:
    if mime_type not in _producer_adapters:
        _producer_adapters[mime_type] = {}
    _producer_adapters[mime_type][adapter_for_type] = conv


async def produce(thing: object, state: State) -> AsyncGenerator[Chunk]:
    thing_type = type(thing)
    for content_type in state["accept"]:
        adapter = _producer_adapters.get(content_type, {}).get(thing_type)
        if adapter:
            async for chunk in adapter(thing, state):
                yield chunk
            return
    if isinstance(thing, FunctionType):
        async for chunk in _produce_call(thing, state):
            yield chunk
        return
    # Nothing to say what it is as this type: not found, rather than its repr
    raise mumutypes.NotFoundResponse()


def can_produce(thing: object, content_type: str) -> bool:
    """Whether produce has something to make of thing as content_type."""
    for kind in (content_type, "*/*"):
        adapter = _producer_adapters.get(kind, {}).get(type(thing))
        if adapter is not None:
            return adapter is not _produce_not_found
    return isinstance(thing, FunctionType)


async def produce_text(thing: object, state: State) -> AsyncGenerator[str]:
    """A string, as it is, or a number's digits: its own content, as text."""
    yield str(thing)


async def _produce_call(function: FunctionType, state: State) -> AsyncGenerator[Chunk]:
    """A function a URL ended at: called with the request, and its answer.

    Whatever kind of function it is. An async generator's chunks are the
    response, and a plain generator's; a coroutine's result, and a plain
    function's return value, are produced as though they had been published
    there -- a dict is JSON at .json, a string is text.
    """
    result: Any = function(state)
    if hasattr(result, "__aiter__"):
        async for chunk in result:
            yield chunk
        return
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, GeneratorType):
        for chunk in cast(GeneratorType[Chunk, None, None], result):
            yield chunk
        return
    async for chunk in produce(result, state):
        yield chunk


async def _produce_not_found(thing: object, state: State) -> AsyncGenerator[Chunk]:
    # Not something to publish: its repr would say where it lives in memory
    raise mumutypes.NotFoundResponse()
    yield ""  # pragma: no cover -- an async generator, which raises first


async def produce_file(
    thing: TextIOWrapper | BufferedReader, state: State
) -> AsyncGenerator[mumutypes.SpecialResponse]:
    async for chunk in _produce_filename(str(thing.name), state):
        yield chunk


async def produce_path(
    thing: Path, state: State
) -> AsyncGenerator[mumutypes.SpecialResponse]:
    # A directory is walked into, not read: asked for as a file, it is not one
    if thing.is_dir():
        raise mumutypes.NotFoundResponse()
    async for chunk in _produce_filename(str(thing), state):
        yield chunk


async def _produce_filename(
    filename: str, state: State
) -> AsyncGenerator[mumutypes.SpecialResponse]:
    # A file is its own type, by its extension on disk, and only that: a
    # .css asked for as .html, or as .js, is not found. With no extension
    # of its own, no URL names it.
    extension = state.get("extension")
    if extension is not None and PurePath(filename).suffix != f".{extension}":
        raise mumutypes.NotFoundResponse()
    # Bytes, whatever the file holds: nothing is decoded, so an image or a
    # font goes out exactly as it is on disk, and text as its own bytes
    async with aiofiles.open(filename, "rb") as file:
        content = await file.read()
    # The URL's type when the server gives one, else the file's own
    content_type = (
        state.get("content_type")
        or mumutypes.content_type_for(PurePath(filename).suffix[1:])
        or "application/octet-stream"
    )
    yield mumutypes.SpecialResponse(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", content_type.encode("utf8"))],
        },
        content,
    )


add_producer(TextIOWrapper, produce_file)
add_producer(BufferedReader, produce_file)


def container_url(url: str) -> str:
    """The URL of the directory a request named, ending in a slash.

    /static/ and /static.json both name static, whose entries are
    /static/<name>.
    """
    if url.endswith("/"):
        return url
    head, _, last = url.rpartition("/")
    return f"{head}/{last.rpartition('.')[0]}/"


def directory_listing(directory: Path) -> list[tuple[str, bool]]:
    """What a directory can serve, by name, and whether each is a directory.

    What its consumer would not find is not listed: hidden names, symlinks
    that lead outside, and files with no extension, which no URL can name.
    """
    root = directory.resolve()
    entries: list[tuple[str, bool]] = []
    for child in sorted(directory.iterdir()):
        if child.name.startswith(".") or not child.resolve().is_relative_to(root):
            continue
        if child.is_dir():
            entries.append((child.name, True))
        elif child.suffix:
            entries.append((child.name, False))
    return entries


def listing_html(entries: Iterable[tuple[str, str]]) -> str:
    """A container's listing: a list of links, each named for its entry."""
    items = "".join(
        f'  <li><a href="{html.escape(url)}">{html.escape(name)}</a></li>\n'
        for name, url in entries
    )
    return f"<ul>\n{items}</ul>"


def listing(
    entries: Iterable[tuple[str, str]], state: State, parent: str | None
) -> str:
    """A container's listing as its answer: a page, as Apache's directory
    indexes were, "Index of /static" its title and heading, and a link to
    its parent first, when it has one that can be shown. As a slot's
    filling -- state["fragment"], set by the tree it is in -- the list of
    links alone."""
    if state.get("fragment"):
        return listing_html(entries)
    base = container_url(state.get("url", "/"))
    name = html.escape(base if base == "/" else base.rstrip("/"))
    links = [("Parent Directory", parent)] if parent is not None else []
    return (
        "<!doctype html>\n<html>\n<head>\n"
        '<meta charset="utf-8" />\n'
        f"<title>Index of {name}</title>\n"
        "</head>\n<body>\n"
        f"<h1>Index of {name}</h1>\n"
        f"{listing_html([*links, *entries])}\n"
        "</body>\n</html>"
    )


async def produce_path_json(thing: Path, state: State) -> AsyncGenerator[Chunk]:
    """A file, or a directory as {name: URL}; a subdirectory's is its listing,
    /static/sub.json."""
    if not thing.is_dir():
        async for chunk in produce_path(thing, state):
            yield chunk
        return
    base = container_url(state.get("url", "/"))
    yield json.dumps(
        {
            name: base + quote(name) + (".json" if is_dir else "")
            for name, is_dir in directory_listing(thing)
        }
    )


# The platform's own Path class -- PosixPath or WindowsPath -- which is what a
# Path is, and producers are found by exact type. A directory has a listing
# as HTML and as JSON; as anything else it is not found.
add_producer(type(Path()), produce_path)
add_producer(type(Path()), produce_path_json, "application/json")


async def produce_json(thing: Any, state: State) -> AsyncGenerator[str]:
    yield json.dumps(thing, default=custom_serializer)


async def produce_bytes(thing: bytes, state: State) -> AsyncGenerator[bytes]:
    """Producer for bytes that yields them directly as binary data"""
    yield thing


JSON_TYPES = [dict, list, tuple, str, int, float, bool, MappingProxyType, type(None)]


for typ in JSON_TYPES:
    add_producer(typ, produce_json, "application/json")

# Add bytes producer for binary data (using */* to match all content types)
add_producer(bytes, produce_bytes)

# Text is text/plain, and a number's text is its digits: a string at .html
# would be served as markup -- a visitor's, in a note, as anyone's page --
# and at .js or .css as code. As those, and anything but .txt and .json, a
# scalar is not found; HTML of your own is a tags.Markup. True, False and
# None have no text but Python's, so they are JSON alone.
for _text_type in (str, int, float):
    add_producer(_text_type, produce_text, "text/plain")

# A method -- bound, built in, or a wrapper like "abc".__str__ -- is not a
# function to call for a request, and its repr is no answer: not found
for _method_type in (MethodType, BuiltinFunctionType, MethodWrapperType):
    add_producer(_method_type, _produce_not_found)
