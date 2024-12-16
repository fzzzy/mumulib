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


import json
from types import MappingProxyType


def custom_serializer(obj):
    if isinstance(obj, MappingProxyType):
        return dict(obj)
    return None


class NoProducer(Exception):
    pass


_producer_adapters = {}


def add_producer(adapter_for_type, conv, mime_type='*/*'):
    if mime_type not in _producer_adapters:
        _producer_adapters[mime_type] = {}
    _producer_adapters[mime_type][adapter_for_type] = conv


async def produce(thing, state):
    for content_type in state['accept']:
        adapter = _producer_adapters.get(content_type, {}).get(type(thing))
        if adapter:
            async for chunk in adapter(thing, state):
                yield chunk
            return
    yield str(thing).encode('utf8')


async def produce_json(thing, state):
    yield json.dumps(thing, default=custom_serializer).encode('utf8')


JSON_TYPES = [
    dict, list, tuple, str, bytes, int, float,
    bool, MappingProxyType, type(None)]


for typ in JSON_TYPES:
    add_producer(typ, produce_json, 'application/json')
