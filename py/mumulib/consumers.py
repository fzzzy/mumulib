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

import sys
from collections.abc import AsyncIterator
from pathlib import Path
from types import MappingProxyType
from typing import Any

from mumulib.mumutypes import (
    Chunk,
    Consumer,
    NotFoundResponse,
    Send,
    SpecialResponse,
    State,
)
from mumulib.producers import add_producer, produce

# The public API: Walking into an object, teaching it a new type of object to
# walk into, and guarding one: read-only, or with no index. The built-in
# consumers and their limits are the module's own.
__all__ = [
    "consume",
    "add_consumer",
    "GetOnly",
    "RefuseIndex",
]

_consumer_adapters: dict[type[Any], Consumer] = {}

# Security constants
MAX_LIST_INDEX = sys.maxsize // 2  # Reasonable upper bound for list indices
MIN_LIST_INDEX = -(sys.maxsize // 2)  # Reasonable lower bound for list indices
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

    Args:
        index_str (str): The string representation of an index.

    Returns:
        int: The validated integer index.

    Raises:
        ValueError: If the index is invalid or out of safe bounds.
    """
    try:
        index = int(index_str)
    except ValueError:
        raise ValueError(f"Invalid integer index: {index_str}")

    if index > MAX_LIST_INDEX or index < MIN_LIST_INDEX:
        raise ValueError(
            f"Index {index} out of safe bounds [{MIN_LIST_INDEX}, {MAX_LIST_INDEX}]"
        )

    return index


def add_consumer(adapter_for_type: type[Any], conv: Consumer) -> None:
    """Register a consumer function for a specific data type.

    Args:
        adapter_for_type (type): The type of data structure this consumer can handle.
        conv (coroutine): An async function with signature
            (parent, segments, state, send) that returns the resolved object or None.
    """
    _consumer_adapters[adapter_for_type] = conv


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
        return SpecialResponse(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [(b"content-type", b"text/plain")],
            },
            b"Method not allowed",
        )
    child: Any
    try:
        # index, last in the path, is the collection itself
        if len(segments) == 1 and segments[0] == "index":
            child = parent
        else:
            index = validate_list_index(segments[0])
            child = parent[index]
    except (IndexError, ValueError):
        return None
    return await consume(child, segments[1:], state, send)


add_consumer(tuple, consume_tuple)


async def consume_list(
    parent: list[Any], segments: list[str], state: State, send: Send
) -> Any:
    """Traverse a list using the first segment as an integer index, or 'last'
    for appending.
    Supports GET, PUT, and DELETE methods:
      - GET: Return the requested element (if index is valid).
      - PUT: Replace an existing element at the given index, or append a new element
        if 'last' is used, returning a 201 Created response. If the index doesn't exist
        and isn't 'last', return 403.
      - DELETE: Remove the element at the given index if it exists, returning 200 OK.

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

        if method == "PUT":
            if index_str == "last":
                # Append new element
                parent.append(state.get("parsed_body", None))
                # The new element's own URL: /todos/last.json appends, and
                # the element is /todos/3.json
                base = state.get("url", "").rpartition("/")[0]
                extension = state.get("extension")
                suffix = f".{extension}" if extension else ""
                location = f"{base}/{len(parent) - 1}{suffix}"
                return SpecialResponse(
                    {
                        "type": "http.response.start",
                        "status": 201,
                        "headers": [
                            (b"content-type", b"text/plain"),
                            (b"location", location.encode("utf-8")),
                        ],
                    },
                    b"",
                )
            else:
                # Replace existing element
                try:
                    segnum = validate_list_index(index_str)
                    if segnum >= len(parent) or segnum < 0:
                        return SpecialResponse(
                            {
                                "type": "http.response.start",
                                "status": 403,
                                "headers": [(b"content-type", b"text/plain")],
                            },
                            b"Not allowed to put to nonexistant list element.  "
                            b"Use last.",
                        )
                    parent[segnum] = state.get("parsed_body", None)
                    return SpecialResponse(
                        {
                            "type": "http.response.start",
                            "status": 201,
                            "headers": [(b"content-type", b"text/plain")],
                        },
                        b"",
                    )
                except ValueError:
                    pass
        elif method == "DELETE":
            # Delete an element
            try:
                segnum = validate_list_index(index_str)
                del parent[segnum]
            except (ValueError, IndexError):
                # If invalid index, just return OK anyway
                pass
            return SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                },
                b"",
            )
    # If we get here, we either haven't done PUT/DELETE, or the path continues.
    return await consume_tuple(tuple(parent), segments, state, send)


add_consumer(list, consume_list)


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
        return SpecialResponse(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [(b"content-type", b"text/plain")],
            },
            b"Method not allowed",
        )
    child: Any
    try:
        # index, last in the path, is the dict's "index" entry if it has
        # one, and else the dict itself; anywhere else it is a key like any
        if len(segments) == 1 and segments[0] == "index" and "index" not in parent:
            child = parent
        else:
            key = sanitize_dict_key(segments[0])
            child = parent[key]
    except (KeyError, ValueError):
        return None
    return await consume(child, segments[1:], state, send)


add_consumer(MappingProxyType, _consume_immutabledict)


async def consume_dict(
    parent: dict[str, Any], segments: list[str], state: State, send: Send
) -> Any:
    """Traverse a dictionary by treating the first segment as a key.
    Supports GET, PUT, and DELETE methods:
    - GET: Return the requested value.
    - PUT: Insert or update the value at the given key, returning 201 Created.
    - DELETE: Remove the key if it exists, returning 200 OK.

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

        if method == "PUT":
            parent[key] = state.get("parsed_body", None)
            return SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 201,
                    "headers": [(b"content-type", b"text/plain")],
                },
                b"",
            )

        elif method == "DELETE":
            if key in parent:
                del parent[key]

            return SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                },
                b"",
            )

    # If we get here, we either are doing a GET or traversing deeper.
    return await _consume_immutabledict(MappingProxyType(parent), segments, state, send)


add_consumer(dict, consume_dict)


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


add_consumer(GetOnly, _consume_get_only)
add_producer(GetOnly, _produce_get_only)


async def _consume_directory(
    parent: Path, segments: list[str], state: State, send: Send
) -> Any:
    """Walk into a directory: each segment names what is in it.

    The server takes the extension off the last segment, as the type; it goes
    back on here, as part of the file's name, so /static/app.min.js is
    static/app.min.js. index is index.<extension>, if there is one, and else
    the directory itself -- which, as HTML or JSON, is a listing of what is in
    it. RefuseIndex is how to have no listing.

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
    if not child.exists() and len(segments) == 1 and segments[0] == "index":
        return parent
    if not child.exists() or not child.resolve().is_relative_to(parent.resolve()):
        return None
    return await consume(child, segments[1:], state, send)


# As for the producer: the platform's own Path class, by exact type
add_consumer(type(Path()), _consume_directory)


class RefuseIndex:
    """An object whose index is not found.

    A container's index -- its "index" entry, or itself: a dict as JSON, a
    directory's listing -- is served by default. Wrapped in RefuseIndex, a
    request whose last segment is index is not found at any depth below it,
    and neither is the object asked for itself (/static.html, above), which
    is its index by another name. Everything else is handed on.

        consumers_app({"static": RefuseIndex(Path("static"))})
    """

    def __init__(self, wrapped: Any) -> None:
        self.wrapped = wrapped


async def _consume_refuse_index(
    parent: RefuseIndex, segments: list[str], state: State, send: Send
) -> Any:
    if segments[-1] == "index":
        return None
    return await consume(parent.wrapped, segments, state, send)


async def _produce_refuse_index(
    thing: RefuseIndex, state: State
) -> AsyncIterator[Chunk]:
    # Asked for itself: its index by another name
    raise NotFoundResponse()
    yield ""  # pragma: no cover -- an async generator, which raises first


add_consumer(RefuseIndex, _consume_refuse_index)
add_producer(RefuseIndex, _produce_refuse_index)
