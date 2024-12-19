"""\
@file consumers.py
@author Donovan Preston

Copyright (c) 2007, Linden Research, Inc.
Copyright (c) 2024, Donovan Preston

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


from mumulib.mumutypes import SpecialResponse

from types import MappingProxyType


_consumer_adapters = {}


def add_consumer(adapter_for_type, conv):
    """Register a consumer function for a specific data type.

    Args:
        adapter_for_type (type): The type of data structure this consumer can handle.
        conv (coroutine): An async function with signature (parent, segments, state, send)
            that returns the resolved object or None.
    """
    _consumer_adapters[adapter_for_type] = conv


async def consume(parent, segments, state, send):
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
        return await _consumer_adapters[parent_type](
            parent, segments, state, send)

    return None


async def consume_tuple(parent, segments, state, send):
    """Traverse a tuple using the first segment as an integer index.

    If the only segment is empty, returns the tuple itself. Otherwise, attempts
    to interpret the segment as an integer and return the corresponding element.
    Returns None if the index is invalid.

    Args:
        parent (tuple): The current tuple.
        segments (list[str]): Path segments, where segments[0] should be an integer index or empty.
        state (dict): Request-specific state.
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object or None if invalid.
    """
    if len(segments) == 1 and state["method"] != "GET":
        return SpecialResponse({
            'type': 'http.response.start',
            'status': 405,
            'headers': [
                (b'content-type', b'text/plain')
            ]
        }, b'Method not allowed')
    try:
        if len(segments) == 1 and not len(segments[0]):
            child = parent
        else:
            child = parent[int(segments[0])]
    except (IndexError, ValueError):
        return None
    return await consume(child, segments[1:], state, send)
add_consumer(tuple, consume_tuple)


async def consume_list(parent, segments, state, send):
    """Traverse a list using the first segment as an integer index or 'last' for appending.
    Supports GET, PUT, and DELETE methods:
      - GET: Return the requested element (if index is valid).
      - PUT: Replace an existing element at the given index, or append a new element
        if 'last' is used, returning a 201 Created response. If the index doesn't exist
        and isn't 'last', return 403.
      - DELETE: Remove the element at the given index if it exists, returning 200 OK.

    Args:
        parent (list): The current list.
        segments (list[str]): Path segments, where segments[0] is an index or 'last', or empty for the list itself.
        state (dict): Request-specific state, expected to have at least:
            - "method" (str): The HTTP method (e.g., GET, PUT, DELETE)
            - "parsed_body" (optional): The body to be used for PUT
            - "url" (optional): The base URL of the request, for forming the Location header
        send (coroutine): ASGI send function for sending responses if needed.

    Returns:
        any or None: The resolved object on GET or traversal, or None if not found.
    """
    if len(segments) == 1:
        method = state.get("method", "GET").upper()
        index_str = segments[0]

        if method == 'PUT':
            if index_str == 'last':
                # Append new element
                parent.append(state.get("parsed_body", None))
                location = f"{state.get("url", "")}/{len(parent)-1}"
                return SpecialResponse({
                    'type': 'http.response.start',
                    'status': 201,
                    'headers': [
                        (b'content-type', b'text/plain'),
                        (b'location', location.encode('utf-8'))],
                }, b'')
            else:
                # Replace existing element
                try:
                    segnum = int(index_str)
                    if segnum >= len(parent) or segnum < 0:
                        return SpecialResponse({
                            'type': 'http.response.start',
                            'status': 403,
                            'headers': [(b'content-type', b'text/plain')],
                        }, b'Not allowed to put to nonexistant list element.  Use last.')
                    parent[segnum] = state.get("parsed_body", None)
                    return SpecialResponse({
                        'type': 'http.response.start',
                        'status': 201,
                        'headers': [(b'content-type', b'text/plain')],
                    }, b'')
                except ValueError:
                    pass
        elif method == 'DELETE':
            # Delete an element
            try:
                segnum = int(index_str)
                del parent[segnum]
            except (ValueError, IndexError):
                # If invalid index, just return OK anyway
                pass
            return SpecialResponse({
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/plain')],
            }, b'')
    # If we get here, we either haven't done PUT/DELETE, or the path continues.
    return await consume_tuple(parent, segments, state, send)
add_consumer(list, consume_list)



async def _consume_immutabledict(parent, segments, state, send):
    """Traverse a dictionary by treating the first segment as a key.

    If the first segment is empty, returns the dictionary itself. Otherwise, returns
    the value corresponding to the key. If the key does not exist, returns None.

    Args:
        parent (dict): The current dictionary.
        segments (list[str]): Path segments, where segments[0] should be a dictionary key or empty.
        state (dict): Request-specific state.
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object or None if the key does not exist.
    """
    if len(segments) == 1 and state["method"] != "GET" and state["method"] != "POST":
        return SpecialResponse({
            'type': 'http.response.start',
            'status': 405,
            'headers': [
                (b'content-type', b'text/plain')
            ],
        }, b'Method not allowed')
    try:
        if len(segments) == 1 and not len(segments[0]):
            if "index" in parent:
                child = parent["index"]
            else:
                child = parent
        else:
            child = parent[segments[0]]
    except KeyError:
        return None
    return await consume(child, segments[1:], state, send)
add_consumer(MappingProxyType, _consume_immutabledict)


async def consume_dict(parent, segments, state, send):
    """Traverse a dictionary by treating the first segment as a key.
    Supports GET, PUT, and DELETE methods:
    - GET: Return the requested value.
    - PUT: Insert or update the value at the given key, returning 201 Created.
    - DELETE: Remove the key if it exists, returning 200 OK.

    Args:
        parent (dict): The current dictionary.
        segments (list[str]): Path segments, where segments[0] is a dictionary key or empty for the dict itself.
        state (dict): Request-specific state, expected to have at least:
            - "method" (str): The HTTP method (e.g., GET, PUT, DELETE)
            - "parsed_body" (optional): The body to be used for PUT
        send (coroutine): ASGI send function.

    Returns:
        any or None: The resolved object on GET or traversal, or None if the key does not exist.
    """
    if len(segments) == 1:
        method = state.get("method", "GET").upper()
        key = segments[0]

        if method == 'PUT':
            parent[key] = state.get("parsed_body", None)
            return SpecialResponse({
                'type': 'http.response.start',
                'status': 201,
                'headers': [(b'content-type', b'text/plain')],
            }, b'')

        elif method == 'DELETE':

            if key in parent:
                del parent[key]

            return SpecialResponse({ # pragma: no cover
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/plain')],
            }, b'')

    # If we get here, we either are doing a GET or traversing deeper.
    return await _consume_immutabledict(parent, segments, state, send)
add_consumer(dict, consume_dict)

