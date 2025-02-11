

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


class BadRequestResponse(HTTPResponse):
    def __init__(self):
        HTTPResponse.__init__(self, 400, 'Bad Request')


class NotFoundResponse(HTTPResponse):
    def __init__(self):
        HTTPResponse.__init__(self, 404, 'Not Found')


class MethodNotAllowedResponse(HTTPResponse):
    def __init__(self):
        HTTPResponse.__init__(self, 405, 'Method Not Allowed')


class CreatedResponse(HTTPResponse):
    def __init__(self):
        HTTPResponse.__init__(self, 201, 'Created')


class SeeOtherResponse(SpecialResponse):
    def __init__(self, redirect_to):
        SpecialResponse.__init__(self, {
                    'type': 'http.response.start',
                    'status': 303,
                    'headers': [
                        (b'content-type', b'application/json'),
                        (b'location', redirect_to.encode('utf8')),
                    ],
        }, '')

