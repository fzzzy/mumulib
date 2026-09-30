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
import json
from collections.abc import AsyncGenerator
from io import BufferedReader, TextIOWrapper
from pathlib import Path, PurePath
from types import FunctionType, MappingProxyType
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
]


def custom_serializer(obj: object) -> dict[str, Any] | None:
    if isinstance(obj, MappingProxyType):
        # isinstance cannot recover the proxy's type parameters.
        return dict(cast(MappingProxyType[str, Any], obj))
    return None


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
        async for chunk in thing(thing, state):
            yield chunk
        return
    yield str(thing)


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


def _directory_url(url: str) -> str:
    """The URL of the directory a request named, ending in a slash.

    A directory is named by its index: /static/, or /static/index.json. Its
    entries are /static/<name>.
    """
    return url if url.endswith("/") else url.rpartition("/")[0] + "/"


def _listing(directory: Path) -> list[tuple[str, bool]]:
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


async def produce_path_html(thing: Path, state: State) -> AsyncGenerator[Chunk]:
    """A file, or a directory as a list of links to what is in it."""
    if not thing.is_dir():
        async for chunk in produce_path(thing, state):
            yield chunk
        return
    base = _directory_url(state.get("url", "/"))
    items = "".join(
        f'  <li><a href="{html.escape(base + quote(name) + ("/" if is_dir else ""))}">'
        f"{html.escape(name)}</a></li>\n"
        for name, is_dir in _listing(thing)
    )
    yield f"<ul>\n{items}</ul>"


async def produce_path_json(thing: Path, state: State) -> AsyncGenerator[Chunk]:
    """A file, or a directory as {name: URL}; a subdirectory's is its listing."""
    if not thing.is_dir():
        async for chunk in produce_path(thing, state):
            yield chunk
        return
    base = _directory_url(state.get("url", "/"))
    yield json.dumps(
        {
            name: base + quote(name) + ("/index.json" if is_dir else "")
            for name, is_dir in _listing(thing)
        }
    )


# The platform's own Path class -- PosixPath or WindowsPath -- which is what a
# Path is, and producers are found by exact type. A directory has a listing
# as HTML and as JSON; as anything else it is not found.
add_producer(type(Path()), produce_path)
add_producer(type(Path()), produce_path_html, "text/html")
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
