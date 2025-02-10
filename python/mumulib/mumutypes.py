

class SpecialResponse(Exception):
    def __init__(self, asgi_send_dict, leaf_object, writer=None):
        self.asgi_send_dict = asgi_send_dict
        self.leaf_object = leaf_object
        self.writer = writer


class HTTPResponse(SpecialResponse):
    def __init__(self, code, body):
        SpecialResponse.__init__(self, {
                    'type': 'http.response.start',
                    'status': code,
                    'headers': [
                        (b'content-type', b'text/plain'),
                    ],
        }, body)

