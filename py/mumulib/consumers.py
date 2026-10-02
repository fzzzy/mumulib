"""\
@file consumers.py
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

import json
import os
import sys
import tempfile
from collections.abc import AsyncIterator, Callable, Iterable
from io import BufferedReader, TextIOWrapper
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from urllib.parse import quote

from mumulib.mumutypes import (
    Chunk,
    Consumer,
    NotFoundResponse,
    Send,
    SpecialResponse,
    State,
)
from mumulib.producers import (
    add_producer,
    can_produce,
    container_url,
    custom_serializer,
    listing_html,
    produce,
)

# The public API: Walking into an object, teaching it a new type of object to
# walk into, and guarding one: read-only, or with no index. The built-in
# consumers and their limits are the module's own.
__all__ = [
    "consume",
    "add_consumer",
    "GetOnly",
    "RefuseIndex",
    "Located",
    "Aliased",
]

_consumer_adapters: dict[type[Any], Consumer] = {}

# Security constants
MAX_LIST_INDEX = sys.maxsize // 2  # Reasonable upper bound for list indices
MAX_KEY_LENGTH = 1000  # Maximum length for dictionary keys to prevent DoS


def sanitize_dict_key(key: str) -> str:
    """Sanitize a dictionary key for security.

    Args:
        key (str): The dictionary key to sanitize (expected to be a string from
            URL path segments).

    Returns:
        str: The sanitized key.

    Raises:
        ValueError: If the key is invalid or too long.
    """
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError(
            f"Dictionary key too long: {len(key)} characters exceeds limit of "
            f"{MAX_KEY_LENGTH}"
        )

    # Remove any null bytes which could cause issues
    if "\x00" in key:
        raise ValueError("Dictionary key contains null bytes")

    return key


def validate_list_index(index_str: str) -> int:
    """Validate and convert a string to a safe list index.

    Each element has one URL, so an index has one spelling: 0, or ASCII
    digits with no leading zero. -1, 01, +1, " 1", 1_0 and other digits
    than ASCII's are all what int() takes for some element, and none of
    them is an index here.

    Args:
        index_str (str): The string representation of an index.

    Returns:
        int: The validated integer index.

    Raises:
        ValueError: If the index is invalid or out of safe bounds.
    """
    canonical = index_str.isascii() and index_str.isdigit()
    if not canonical or (index_str.startswith("0") and index_str != "0"):
        raise ValueError(f"Invalid integer index: {index_str}")
    index = int(index_str)

    if index > MAX_LIST_INDEX:
        raise ValueError(f"Index {index} out of safe bounds [0, {MAX_LIST_INDEX}]")

    return index


# Which types are containers -- True, False, or a question to ask of the
# thing, for a type only some of whose things are
_containers: dict[type[Any], bool | Callable[[Any], bool]] = {}

# Which types answer every method at their own URL, as a Resource does
_own_methods: set[type[Any]] = set()


def add_consumer(
    adapter_for_type: type[Any],
    conv: Consumer,
    container: bool | Callable[[Any], bool] = False,
    own_methods: bool = False,
) -> None:
    """Register a consumer function for a specific data type.

    Args:
        adapter_for_type (type): The type of data structure this consumer can handle.
        conv (coroutine): An async function with signature
            (parent, segments, state, send) that returns the resolved object or None.
        container: Whether things of this type are containers -- with entries
            a URL walks into, reached as a whole at their slash as HTML and at
            their name as data, and hidden whole by RefuseIndex. True, False,
            or a function asked of each thing: a Path is one if a directory.
        own_methods: Whether things of this type answer every method at their
            own URL themselves, as a Resource does. A container they are in
            hands them the request rather than writing or refusing it: a PUT
            to one is its own to answer, not a replacement.
    """
    _consumer_adapters[adapter_for_type] = conv
    _containers[adapter_for_type] = container
    if own_methods:
        _own_methods.add(adapter_for_type)
    else:
        _own_methods.discard(adapter_for_type)


def answers_own_methods(thing: object) -> bool:
    """Whether a thing answers every method at its URL itself, as its type
    was registered with add_consumer."""
    return type(thing) in _own_methods


def _own_handler(parent: Any, segment: str) -> Any | None:
    """The entry at segment if it answers its own methods, and else None.

    What a container does at the last segment -- a write, a delete, a
    refusal -- is for its plain entries; an entry that answers for itself is
    handed the request instead, whatever the method.
    """
    try:
        if isinstance(parent, (list, tuple)):
            items = cast(list[Any] | tuple[Any, ...], parent)
            index = validate_list_index(segment)
            entry = items[index] if index < len(items) else None
        else:
            entry = cast(dict[str, Any], parent).get(sanitize_dict_key(segment))
    except ValueError:
        return None
    return entry if answers_own_methods(entry) else None


class Located:
    """A published object that knows its own URL: a Resource, and anything
    else whose state is kept in a file named after where it is.

    It learns the URL from the path walked to reach it, the first time a
    request reaches it, and keeps it: /editors/characters/c1 for
    /editors/characters/c1.html and .json alike, and what is below it, and
    /editors/ for one reached as an index, at its slash. Until then url is
    None. One object has one URL: reaching it by another is Aliased, a 500.

    Its file is named by its URL, in the app's data directory:
    var/data/editors/characters/c1.json, and an index's index.json in its
    container's, var/data/editors/index.json. Then load is awaited, once,
    before the request goes on: what the object does with a file it may
    have, which here is nothing.
    """

    url: str | None = None
    file: Path | None = None
    # Whether what is read at and below it is its file's, and so is cached
    # by it: an ETag from the file, as a Persist's is, and not a Resource's,
    # which computes its answers
    cached = False

    def cached_for(self, segments: list[str], state: State) -> bool:
        """Whether this request, reaching it with segments remaining, reads
        what its file holds, and is cached by the file: cached, by default."""
        return self.cached

    async def load(self) -> None:
        """Called once, when a request first reaches it: url and file are set."""


class Aliased(Exception):
    """One Located object reached by a second URL. Its file, and what a write
    to it announces, are named by its URL, so it has only one."""

    def __init__(self, thing: Located, url: str) -> None:
        super().__init__(
            f"{type(thing).__name__} at {thing.url} was reached as {url}: "
            "an object is published at one URL"
        )


def url_of(walked: list[str]) -> str:
    """The URL of what the segments walked reach, without an extension: an
    index -- the last segment index -- is its container's slash."""
    if walked and walked[-1] == "index":
        return "/" + "".join(f"{segment}/" for segment in walked[:-1])
    return "/" + "/".join(walked)


def file_for(data: Path, url: str) -> Path:
    """Where in data the Located object at url keeps its file: its URL with
    .json, an index -- a slash -- being index.json. Never outside data."""
    name = f"{url}index" if url.endswith("/") else url
    file = data / f"{name.lstrip('/')}.json"
    if not file.resolve().is_relative_to(data.resolve()):
        raise ValueError(f"{url} names a file outside {data}")
    return file


def write_atomically(file: Path, text: str) -> None:
    """Write text to file whole or not at all: to a temporary file beside it,
    flushed to the disk, then renamed over it. A reader -- or the next start,
    after a crash -- sees the old file or the new one, never part of one."""
    file.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=file.parent, prefix=f".{file.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(text)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, file)
    except BaseException:
        os.unlink(temporary)
        raise


async def _locate(thing: Located, segments: list[str], state: State) -> None:
    # What has been walked is the request's segments, less those remaining
    walked = state.get("segments")
    if walked is None:
        return
    url = url_of(walked[: len(walked) - len(segments)])
    if thing.url is None:
        thing.url = url
        data = state.get("data")
        if data is not None:
            thing.file = file_for(data, url)
        await thing.load()
    elif thing.url != url:
        raise Aliased(thing, url)
    # The deepest walked to or through so far: what a write here changes,
    # and whose file -- if it is cached -- says whether a read is fresh
    state["container"] = url
    state["etag_file"] = thing.file if thing.cached_for(segments, state) else None


def answer(
    status: int, headers: list[tuple[bytes, bytes]] | None = None, body: bytes = b""
) -> SpecialResponse:
    """A response with no representation of its own: a write's outcome."""
    return SpecialResponse(
        {"type": "http.response.start", "status": status, "headers": headers or []},
        body,
    )


def refuse(allow: str) -> SpecialResponse:
    """405, naming the methods that are allowed here."""
    return answer(
        405,
        [(b"content-type", b"text/plain"), (b"allow", allow.encode())],
        b"Method not allowed",
    )


async def consume(
    parent: object, segments: list[str], state: State, send: Send
) -> Any | None:
    """Traverse a nested data structure by following a list of path segments.

    If no segments remain, returns the current parent. Otherwise, attempts to find
    an appropriate consumer for the current parent's type and delegates traversal
    to it. If no matching consumer is found, returns None.

    Args:
        parent (any): The current data structure node to be traversed.
        segments (list[str]): The remaining path segments to follow.
        state (dict): A dictionary for request-specific state.
        send (coroutine): ASGI send function to send responses if needed.

    Returns:
        any or None: The object found at the end of the traversal, or None if not found.
    """
    if isinstance(parent, Located):
        await _locate(parent, segments, state)
    if not segments:
        return parent
    state["remaining"] = segments

    parent_type = type(parent)
    if parent_type in _consumer_adapters:
        return await _consumer_adapters[parent_type](parent, segments, state, send)

    return None


async def consume_tuple(
    parent: tuple[Any, ...], segments: list[str], state: State, send: Send
) -> Any | None:
    """Traverse a tuple using the first segment as an integer index.

    If the only segment is index, returns the tuple itself. Otherwise, attempts
    to interpret the segment as an integer and return the corresponding element.
    Returns None if the index is invalid.

    Args:
        parent (tuple): The current tuple.
        segments (list[str]): Path segments, where segments[0] should be an
            integer index, or index for the tuple itself.
        state (dict): Request-specific state.
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object or None if invalid.
    """
    if len(segments) == 1 and state["method"] != "GET":
        own = _own_handler(parent, segments[0])
        if own is not None:
            return await consume(own, [], state, send)
        return refuse("GET")
    child: Any
    try:
        # index, last in the path, is the collection itself
        if len(segments) == 1 and segments[0] == "index":
            child = parent
        else:
            index = validate_list_index(segments[0])
            child = parent[index]
    except IndexError, ValueError:
        return None
    return await consume(child, segments[1:], state, send)


add_consumer(tuple, consume_tuple, container=True)


async def consume_list(
    parent: list[Any], segments: list[str], state: State, send: Send
) -> Any:
    """Traverse a list using the first segment as an integer index, or 'last'
    for appending.
    Supports GET, PUT, and DELETE methods:
      - GET: Return the requested element (if index is valid).
      - PUT: Replace an existing element at the given index, 204 No Content
        (201 Created if it had been deleted), or
        append a new element if 'last' is used, 201 Created with its URL in
        Location. If the index doesn't exist and isn't 'last', return 403.
      - DELETE: Leave None in the element's place, 204 No Content, so that
        it is not found and no other element's URL changes; or 404 if there
        was nothing there. A PUT to its index, 201, brings it back.

    Args:
        parent (list): The current list.
        segments (list[str]): Path segments, where segments[0] is an index or
            'last', or index for the list itself.
        state (dict): Request-specific state, expected to have at least:
            - "method" (str): The HTTP method (e.g., GET, PUT, DELETE)
            - "parsed_body" (optional): The body to be used for PUT
            - "url" (optional): The base URL of the request, for forming the
              Location header
        send (coroutine): ASGI send function for sending responses if needed.

    Returns:
        any or None: The resolved object on GET or traversal, or None if not found.
    """
    if len(segments) == 1:
        method = state.get("method", "GET").upper()
        index_str = segments[0]
        own = _own_handler(parent, index_str) if method != "GET" else None
        if own is not None:
            return await consume(own, [], state, send)

        if method == "PUT" and index_str == "last":
            # Append new element
            parent.append(state.get("parsed_body", None))
            # The new element's own URL: /todos/last.json appends, and
            # the element is /todos/3.json
            base = state.get("url", "").rpartition("/")[0]
            extension = state.get("extension")
            suffix = f".{extension}" if extension else ""
            location = f"{base}/{len(parent) - 1}{suffix}"
            return answer(201, [(b"location", location.encode("utf-8"))])
        if method in ("PUT", "DELETE"):
            try:
                segnum = validate_list_index(index_str)
            except ValueError:
                return None
            if segnum >= len(parent):
                if method == "DELETE":
                    return None
                return answer(
                    403,
                    [(b"content-type", b"text/plain")],
                    b"Not allowed to put to nonexistant list element.  Use last.",
                )
            # Nothing moves: a deleted element leaves None in its place, not
            # found, and every other element keeps its URL. A PUT there
            # brings it back.
            found = parent[segnum] is not None
            if method == "DELETE":
                if not found:
                    return None
                parent[segnum] = None
                return answer(204)
            parent[segnum] = state.get("parsed_body", None)
            return answer(204 if found else 201)
    # If we get here, we either haven't done PUT/DELETE, or the path continues.
    return await consume_tuple(tuple(parent), segments, state, send)


add_consumer(list, consume_list, container=True)


async def _consume_immutabledict(
    parent: MappingProxyType[str, Any], segments: list[str], state: State, send: Send
) -> Any | None:
    """Traverse a dictionary by treating the first segment as a key.

    If the only segment is index, returns the "index" entry or else the
    dictionary itself. Otherwise, returns
    the value corresponding to the key. If the key does not exist, returns None.

    Args:
        parent (dict): The current dictionary.
        segments (list[str]): Path segments, where segments[0] should be a
            dictionary key, or index for its "index" entry or itself.
        state (dict): Request-specific state.
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object or None if the key does not exist.
    """
    if len(segments) == 1 and state["method"] != "GET" and state["method"] != "POST":
        own = _own_handler(parent, segments[0])
        if own is not None:
            return await consume(own, [], state, send)
        return refuse("GET, POST")
    child: Any
    try:
        # index, last in the path, is the dict's "index" entry if it has
        # one, and else the dict itself; anywhere else it is a key like any
        if len(segments) == 1 and segments[0] == "index" and "index" not in parent:
            child = parent
        else:
            key = sanitize_dict_key(segments[0])
            child = parent[key]
    except KeyError, ValueError:
        return None
    return await consume(child, segments[1:], state, send)


add_consumer(MappingProxyType, _consume_immutabledict, container=True)


async def consume_dict(
    parent: dict[str, Any], segments: list[str], state: State, send: Send
) -> Any:
    """Traverse a dictionary by treating the first segment as a key.
    Supports GET, PUT, and DELETE methods:
    - GET: Return the requested value.
    - PUT: Insert the value at the given key, 201 Created, or replace the
      one there, 204 No Content.
    - DELETE: Remove the key, 204 No Content, or 404 if it is not there.

    Args:
        parent (dict): The current dictionary.
        segments (list[str]): Path segments, where segments[0] is a dictionary
            key, or index.
        state (dict): Request-specific state, expected to have at least:
            - "method" (str): The HTTP method (e.g., GET, PUT, DELETE)
            - "parsed_body" (optional): The body to be used for PUT
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object on GET or traversal, or None if the key
            does not exist.
    """
    if len(segments) == 1:
        method = state.get("method", "GET").upper()

        try:
            key = sanitize_dict_key(segments[0])
        except ValueError:
            return None
        own = _own_handler(parent, key) if method != "GET" else None
        if own is not None:
            return await consume(own, [], state, send)

        if method == "PUT":
            # Created if it was not found before: absent, or None
            created = parent.get(key) is None
            parent[key] = state.get("parsed_body", None)
            return answer(201 if created else 204)

        elif method == "DELETE":
            if key not in parent:
                return None
            del parent[key]
            return answer(204)

    # If we get here, we either are doing a GET or traversing deeper.
    return await _consume_immutabledict(MappingProxyType(parent), segments, state, send)


add_consumer(dict, consume_dict, container=True)


class GetOnly:
    """An object published to be read, and nothing else.

    consumers_app publishes for reading and writing alike, on purpose: PUT
    writes an entry of a dict or a list, and DELETE removes one. Wrapped in
    GetOnly, an object hands GET on to what it wraps and answers anything else
    with 405 Method Not Allowed, at any depth below it:

        consumers_app(GetOnly(root))              # the whole site, read-only
        consumers_app({"notes": notes, "about": GetOnly(about)})

    It guards what is reached through it, not its own place in a parent: PUT
    /about.json above is the unguarded dict's to answer, and would replace
    the entry. Guard the parent, or the root, to keep that too.
    """

    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped


# What GetOnly answers anything but GET with
_ONLY_GET = SpecialResponse(
    {
        "type": "http.response.start",
        "status": 405,
        "headers": [
            (b"allow", b"GET"),
            (b"content-type", b"text/plain; charset=UTF-8"),
        ],
    },
    b"Only GET\n",
)


async def _consume_get_only(
    parent: GetOnly, segments: list[str], state: State, send: Send
) -> Any:
    if state.get("method", "GET").upper() != "GET":
        return _ONLY_GET
    return await consume(parent.wrapped, segments, state, send)


async def _produce_get_only(thing: GetOnly, state: State) -> AsyncIterator[Chunk]:
    # GetOnly asked for itself, as /about.json above: what it wraps
    async for chunk in produce(thing.wrapped, state):
        yield chunk


add_consumer(GetOnly, _consume_get_only, container=lambda g: is_container(g.wrapped))
add_producer(GetOnly, _produce_get_only)


async def _consume_directory(
    parent: Path, segments: list[str], state: State, send: Send
) -> Any:
    """Walk into a directory: each segment names what is in it.

    The server takes the extension off the last segment, as the type; it goes
    back on here, as part of the file's name, so /static/app.min.js is
    static/app.min.js. The directory's slash is its index.html, if it has
    one, and else itself -- which, as HTML, is a listing of what is in it; as
    JSON, at /static.json, it is the listing as data, and a subdirectory is
    /static/sub.json. RefuseIndex is how to have no listing.

    What is served stays inside the directory: .. and hidden names, like .git
    or .env, are not found, and neither is a symlink that leads outside. And a
    directory is read, never written: anything but GET is refused.
    """
    if not parent.is_dir():
        return None
    if state.get("method", "GET").upper() != "GET":
        return _ONLY_GET
    name = segments[0]
    if len(segments) == 1 and state.get("extension"):
        name = f"{name}.{state['extension']}"
    if not name or name.startswith(".") or "/" in name or "\\" in name:
        return None
    child = parent / name
    if not child.exists() and len(segments) == 1:
        # Its slash: its index.html, or else itself
        if segments[0] == "index":
            return parent
        # A subdirectory, as data: /static/sub.json
        if state.get("extension") != "html" and (parent / segments[0]).is_dir():
            child = parent / segments[0]
    if not child.exists() or not child.resolve().is_relative_to(parent.resolve()):
        return None
    return await consume(child, segments[1:], state, send)


# As for the producer: the platform's own Path class, by exact type
add_consumer(type(Path()), _consume_directory, container=Path.is_dir)


class RefuseIndex:
    """An object whose index is not found.

    A container is served whole by default: at its slash, its "index" entry
    or itself, and by the name for data, itself -- a dict as JSON, a
    directory's listing. Wrapped in RefuseIndex, neither is found at any
    depth below it, nor the object itself, and no container is written whole
    there either -- replaced, removed, or put where there was none. Only what
    is not a container comes out, which for a directory is its files; its
    entries can still be written.

        consumers_app({"static": RefuseIndex(Path("static"))})
    """

    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped


async def _consume_refuse_index(
    parent: RefuseIndex, segments: list[str], state: State, send: Send
) -> Any:
    if segments[-1] == "index":
        return None
    method = state.get("method", "GET").upper()
    if method != "GET":
        # A write happens during the walk, in the parent's consumer, so what
        # it lands on is found first by walking to it as a read. Nothing below
        # handles a container whole: not replacing or removing one, and not
        # putting one where there was none.
        target = await consume(
            parent.wrapped, segments, {**state, "method": "GET"}, send
        )
        putting_one = method == "PUT" and is_container(state.get("parsed_body"))
        if is_container(target) or putting_one:
            return None
    found = await consume(parent.wrapped, segments, state, send)
    # A container below it, whole -- a directory's listing, a dict's JSON --
    # is its index too, by the name for data
    return None if is_container(found) else found


async def _produce_refuse_index(
    thing: RefuseIndex, state: State
) -> AsyncIterator[Chunk]:
    # Asked for itself: refused if a container, and else what it wraps
    if is_container(thing.wrapped):
        raise NotFoundResponse()
    async for chunk in produce(thing.wrapped, state):
        yield chunk


def is_container(thing: object) -> bool:
    """Whether a thing has entries a URL walks into, and so an index.

    As its type was registered with add_consumer. A container has one URL
    per type: its slash, /todos/, as HTML, and its name, /todos.json, as
    anything else -- never /todos.html, and never index.<ext> spelled out.
    """
    answer = _containers.get(type(thing), False)
    return answer(thing) if callable(answer) else answer


add_consumer(
    RefuseIndex,
    _consume_refuse_index,
    container=lambda r: is_container(r.wrapped),
)
add_producer(RefuseIndex, _produce_refuse_index)


def _entry_url(base: str, name: str, value: Any) -> str | None:
    """Where a container's entry is, for its listing -- or None, if nowhere.

    A container is at its slash. A file is at its own extension, the only
    type it is served as, and one with none is nowhere; text, a string or a
    number, is linked as .txt, where it is; anything else as HTML. What
    would not be found is not listed.
    """
    if not name or "/" in name or name == "index":
        return None
    if is_container(value):
        return f"{base}{quote(name)}/"
    if not can_produce(value, "text/html"):
        if can_produce(value, "text/plain"):
            return f"{base}{quote(name)}.txt"
        return None
    filename = getattr(value, "name", None)
    if isinstance(value, (TextIOWrapper, BufferedReader, Path)) and isinstance(
        filename, str
    ):
        suffix = Path(filename).suffix
        return f"{base}{quote(name)}{suffix}" if suffix else None
    return f"{base}{quote(name)}.html"


async def _produce_container_html(thing: Any, state: State) -> AsyncIterator[Chunk]:
    """A container at its slash, with no "index" entry: a list of links to
    what is in it, as a directory's is."""
    entries = cast(
        Iterable[tuple[Any, Any]],
        thing.items()
        if isinstance(thing, (dict, MappingProxyType))
        else enumerate(thing),
    )
    base = container_url(state.get("url", "/"))
    links: list[tuple[str, str]] = []
    for key, value in entries:
        url = _entry_url(base, str(key), value)
        if url is not None:
            links.append((str(key), url))
    yield listing_html(links)


for _container_type in (dict, MappingProxyType, list, tuple):
    add_producer(_container_type, _produce_container_html, "text/html")


def _entries(value: Any) -> Iterable[tuple[str, Any]] | None:
    """A plain container's entries, keyed as their URLs name them, or None
    for anything else."""
    if isinstance(value, (dict, MappingProxyType)):
        return ((str(k), v) for k, v in cast(dict[Any, Any], value).items())
    if isinstance(value, (list, tuple)):
        items = cast(list[Any] | tuple[Any, ...], value)
        return ((str(i), v) for i, v in enumerate(items))
    return None


def plain(value: Any, where: str) -> None:
    """Refuse a resource's state, or a persist's document, that holds a
    resource or a persist: it is plain JSON, and a container in a container
    is not, yet (design/state-sync.md, decision 14). A TypeError names the
    place, as where/key/key."""
    if isinstance(value, Located):
        raise TypeError(
            f"{where} is a {type(value).__name__}: a resource's state, or a "
            "persist's document, holds no resource or persist"
        )
    entries = _entries(value)
    for key, entry in entries or ():
        plain(entry, f"{where}/{key}")


def linked(value: Any, base: str, extension: str = "json") -> Any:
    """value with each resource or persist in it the URL of its own, as
    extension -- a plain string -- by where it is below base."""
    entries = _entries(value)
    if entries is None:
        return value
    result = {
        key: f"{base}{quote(key)}.{extension}"
        if isinstance(entry, Located)
        else linked(entry, f"{base}{quote(key)}/", extension)
        for key, entry in entries
    }
    if isinstance(value, (list, tuple)):
        return list(result.values())
    return result


async def _produce_container_json(thing: Any, state: State) -> AsyncIterator[Chunk]:
    """A plain container as JSON: its entries, and each resource or persist
    in it as its URL -- /editors/characters.json is
    {"c1": "/editors/characters/c1.json", ...} -- for a client to bind."""
    base = container_url(state.get("url", "/"))
    yield json.dumps(linked(thing, base), default=custom_serializer)


for _container_type in (dict, MappingProxyType, list, tuple):
    add_producer(_container_type, _produce_container_json, "application/json")
