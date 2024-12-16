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


class NoProducer(Exception):
    pass


_producer_adapters = {}


def add_producer(adapter_for_type, conv, mime_type='*/*'):
    if mime_type not in _producer_adapters:
        _producer_adapters[mime_type] = {}
    _producer_adapters[mime_type][adapter_for_type] = conv


def produce(resource, req):
    req.site.adapt(resource, req)


def _none(_, req, segs=None):
    req.not_found()
add_producer(types.NoneType, _none)


JSON_TYPES = [
    dict, list, tuple, str, bytes, int, long, float,
    bool, type(None)]



def produce_json(it, req):
    req.set_header('content-type', 'application/json')
    callback = req.get_query('callback')
    if callback is not None:
        ## See Yahoo's ajax documentation for information about using jsonp
        ## http://developer.yahoo.com/common/json.html#callbackparam
        req.write("%s(%s)" % (callback, simplejson.dumps(it, cls=DumbassEncoder)))
    else:
        req.write(simplejson.dumps(it, cls=DumbassEncoder))


for typ in JSON_TYPES:
    add_producer(typ, produce_json, 'application/json')

