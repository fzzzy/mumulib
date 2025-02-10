"""\
@file producers.py
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

from io import TextIOWrapper
import json
import mimetypes
from types import FunctionType, MappingProxyType

from mumulib import mumutypes


def custom_serializer(obj):
    if isinstance(obj, MappingProxyType):
        return dict(obj)
    return None


_producer_adapters = {}


def add_producer(adapter_for_type, conv, mime_type='*/*'):
    if mime_type not in _producer_adapters:
        _producer_adapters[mime_type] = {}
    _producer_adapters[mime_type][adapter_for_type] = conv


async def produce(thing, state):
    thing_type = type(thing)
    for content_type in state['accept']:
        adapter = _producer_adapters.get(content_type, {}).get(thing_type)
        if adapter:
            async for chunk in adapter(thing, state):
                yield chunk
            return
    if thing_type is FunctionType:
        async for chunk in thing(thing, state):
            yield chunk
        return
    yield str(thing)


async def produce_file(thing, state):
    content_type = mimetypes.guess_type(thing.name)
    read_mode = 'r'
    if content_type[0] == "font/ttf":
        read_mode = 'rb'
    newthing = open(thing.name, read_mode)
    charset = b'; charset=UTF-8'
    if read_mode == 'rb':
        charset = b''
    yield mumutypes.SpecialResponse({
        'type': 'http.response.start',
        'status': 200,
        'headers': [(b'content-type', content_type[0].encode("utf8") + charset)],
    }, newthing.read())
add_producer(TextIOWrapper, produce_file)


async def produce_json(thing, state):
    yield json.dumps(thing, default=custom_serializer)


JSON_TYPES = [
    dict, list, tuple, str, bytes, int, float,
    bool, MappingProxyType, type(None)]


for typ in JSON_TYPES:
    add_producer(typ, produce_json, 'application/json')

