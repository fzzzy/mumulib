"""\
@file stacked.py
@author Donovan Preston

Copyright (c) 2007, Linden Research, Inc.
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

from os import path

import itertools
import StringIO
import sys
import time
import traceback
import types
import urllib

import simplejson


class NoProducer(Exception):
    pass


_consumer_adapters = {}
def add_consumer(adapter_for_type, conv):
    _consumer_adapters[adapter_for_type] = conv


def consume(parent, request, segments):
    request.remaining = segments
    if not segments:
        request.site.adapt(parent, request)
        return

    if type(parent) in _consumer_adapters:
        _consumer_adapters[type(parent)](
            parent, request, segments)
        return

    if hasattr(parent, 'findChild'):
        child, handled, left = parent.findChild(request, segments)
        if child is None:
            request.response(404, body="Not Found")
            return
        try:
            consume(child, request, left)
        finally:
            parent.afterHandle(request)
        return

    if not segments[0].startswith('_'):
        if len(segments) == 1:
            method = request.method()
            if method == 'PUT':
                setattr(parent, segments[0], request.parsed_body())
                request.response(201, body='')
                return
            elif method == 'DELETE':
                if hasattr(parent, segments[0]):
                    delattr(parent, segments[0])
                request.response(200, body='')

        child = getattr(parent, segments[0], None)
        if child is not None:
            consume(child, request, segments[1:])
            return

    request.not_found()


def consume_tuple(parent, request, segments):
    try:
        child = parent[int(segments[0])]
    except (IndexError, ValueError):
        request.not_found()
        return
    consume(child, request, segments[1:])
add_consumer(tuple, consume_tuple)


def consume_list(parent, request, segments):
    if len(segments) == 1:
        method = request.method()
        if method == 'PUT':
            if segments[0] == 'last':
                parent.append(request.parsed_body())
                # tell the client the location of the new resource it created
                new_item = request.full_url().split('/')
                new_item[-1] = str(len(parent) - 1)
                request.set_header('location', '/'.join(new_item))
            else:
                segnum = int(segments[0])
                if segnum >= len(parent):
                    return request.response(403, body='Not allowed to put to nonexistant list element.  Use last.')
                parent[segnum] = request.parsed_body()
            request.response(201, body='')
            return
        elif method == 'DELETE':
            try:
                del parent[int(segments[0])]
            except IndexError:
                pass
            request.response(200, body='')
            return
    consume_tuple(parent, request, segments)
add_consumer(list, consume_list)


class immutable_dict(dict):
    pass


def consume_immutabledict(parent, request, segments):
    try:
        child = parent[segments[0]]
    except KeyError:
        request.not_found()
        return
    consume(child, request, segments[1:])
add_consumer(immutable_dict, consume_immutabledict)


def consume_dict(parent, request, segments):
    if len(segments) == 1:
        method = request.method()
        if method == 'PUT':
            parent[segments[0]] = request.parsed_body()
            request.response(201, body='')
            return
        elif method == 'DELETE':
            try:
                del parent[segments[0]]
            except KeyError:
                pass
            request.response(200, body='')
            return
    consume_immutabledict(parent, request, segments)
add_consumer(dict, consume_dict)


_producer_adapters = {}


def add_producer(adapter_for_type, conv, mime_type='*/*'):
    if mime_type not in _producer_adapters:
        _producer_adapters[mime_type] = {}
    _producer_adapters[mime_type][adapter_for_type] = conv


def produce(resource, req):
    req.site.adapt(resource, req)

def _none(_, req, segs=None):
    req.not_found()
add_consumer(types.NoneType, _none)
add_producer(types.NoneType, _none)


SIMPLEJSON_TYPES = [
    dict, list, tuple, str, unicode, int, long, float,
    bool, type(None)]


class DumbassEncoder(simplejson.JSONEncoder):
    def default(self, obj):
        return str(obj)
        if hasattr(obj, '__class__') and hasattr(obj, '__dict__'):
            state = dict([(str(k), v) for (k, v) in obj.__dict__.items()])
            return {
                '__type__': obj.__class__.__module__ +
                '.' + obj.__class__.__name__,
                '__state__': state}
        return simplejson.JSONEncoder.default(self, obj)

    def _iterencode(self, o, markers):
        if isinstance(o, dict):
            o = dict([(str(k), v) for (k, v) in o.items()])
        return simplejson.JSONEncoder._iterencode(self, o, markers)

def produce_simplejson(it, req):
    req.set_header('content-type', 'application/json')
    callback = req.get_query('callback')
    if callback is not None:
        ## See Yahoo's ajax documentation for information about using this
        ## callback style of programming
        ## http://developer.yahoo.com/common/json.html#callbackparam
        req.write("%s(%s)" % (callback, simplejson.dumps(it, cls=DumbassEncoder)))
    else:
        req.write(simplejson.dumps(it, cls=DumbassEncoder))


for typ in SIMPLEJSON_TYPES:
    add_producer(typ, produce_simplejson, 'application/json')


def produce_anything(it, req):
    req.write(str(it))


# TODO: Only for supporting stacked_test.py as it is
# currently written
add_producer(dict, produce_anything, '*/*')


add_producer(str, produce_anything, '*/*')
add_producer(unicode, produce_anything, '*/*')
add_producer(int, produce_anything, '*/*')
add_producer(float, produce_anything, '*/*')
add_producer(str, produce_anything, 'text/html')
add_producer(unicode, produce_anything, 'text/html')
add_producer(int, produce_anything, 'text/html')
add_producer(float, produce_anything, 'text/html')


def escape(string):
    string = str(string)
    return string.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def produce_dict_html(it, req):
    out = """<html>
    <body>
<dl>"""
    for key, value in it.items():
        out += """
    <dt>%s</dt>
    <dd>%s</dd>""" % (escape(key), escape(value))
    out += """
</dl>
    </body>
</html>
    """
    req.write(out)
add_producer(dict, produce_dict_html, 'text/html')


def produce_list(it, req):
    fake = TestRequest(req)
    for item in it:
        produce(item, fake)
    req.write(fake.result())
add_producer(list, produce_list, '*/*')
add_producer(list, produce_list, 'text/html')


def produce_module(mod, req):
    produce(getattr(mod, 'index', None), req)
add_producer(types.ModuleType, produce_module, '*/*')
add_producer(types.ModuleType, produce_module, 'text/html')
add_producer(types.ModuleType, produce_module, 'application/json')


def handle_function(func, req, path=None):
    result = func(req)
    if result is not None:
        req.write(result)
add_consumer(types.FunctionType, handle_function)
add_producer(types.FunctionType, handle_function, '*/*')
add_producer(types.FunctionType, handle_function, 'text/html')
add_producer(types.FunctionType, handle_function, 'application/json')


class TestSite(object):
    def handle_request(self, req):
        assert False, "Shouldn't be called"

    def adapt(self, obj, req):
        req.write(str(obj))


class TestRequest(StringIO.StringIO):
    def __init__(self, req=None, site=None):
        StringIO.StringIO.__init__(self)
        self._outgoing_headers = {}
        if req is None:
            self.site = TestSite()
            self.depth = 0
        else:
            self.site = req.site
            self.depth = req.depth
        if site is not None:
            self.site = site

    def result(self):
        self.seek(0)
        return self.read()

    def response(self, code, headers=None, body=''):
        self.status = code
        self.write(body)

    def error(self, response=None, body=None, log_traceback=True):
        self.write('error: %s %s' % (response, body))

    def get_header(self, name, default=None):
        return default

    def set_header(self, key, value):
        self._outgoing_headers[key.lower()] = value

    def get_outgoing_header(self, key):
        return self._outgoing_headers[key.lower()]

    def not_found(self):
        self.error(404, 'not_found')

    def method(self):
        return 'GET'

    def read_body(self):
        return ''

    def parsed_body(self):
        return ''

    def full_url(self):
        return 'full_url'
