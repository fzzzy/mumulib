
import coverage # pragma: no cover

cov = coverage.Coverage(branch=True) # pragma: no cover
cov.start() # pragma: no cover

import unittest # pragma: no cover

from mumulib.mumutypes import ( # pragma: no cover
    SpecialResponse,
    HTTPResponse,
    BadRequestResponse,
    NotFoundResponse,
    MethodNotAllowedResponse,
    CreatedResponse,
    SeeOtherResponse
)


class TestSpecialResponse(unittest.TestCase):
    """Test SpecialResponse base class"""

    def test_init_without_writer(self):
        """Test SpecialResponse initialization without writer"""
        asgi_dict = {'type': 'http.response.start', 'status': 200}
        leaf = 'test body'

        response = SpecialResponse(asgi_dict, leaf)

        self.assertEqual(response.asgi_send_dict, asgi_dict)
        self.assertEqual(response.leaf_object, leaf)
        self.assertIsNone(response.writer)

    def test_init_with_writer(self):
        """Test SpecialResponse initialization with writer"""
        asgi_dict = {'type': 'http.response.start', 'status': 200}
        leaf = 'test body'

        def writer(x):
            return x

        response = SpecialResponse(asgi_dict, leaf, writer)

        self.assertEqual(response.asgi_send_dict, asgi_dict)
        self.assertEqual(response.leaf_object, leaf)
        self.assertEqual(response.writer, writer)

    def test_is_exception(self):
        """Test that SpecialResponse is an Exception"""
        response = SpecialResponse({}, 'body')
        self.assertIsInstance(response, Exception)


class TestHTTPResponse(unittest.TestCase):
    """Test HTTPResponse class"""

    def test_init(self):
        """Test HTTPResponse initialization"""
        response = HTTPResponse(200, 'OK')

        self.assertEqual(response.asgi_send_dict['type'], 'http.response.start')
        self.assertEqual(response.asgi_send_dict['status'], 200)
        self.assertEqual(response.asgi_send_dict['headers'], [(b'content-type', b'text/plain')])
        self.assertEqual(response.leaf_object, 'OK')

    def test_custom_status_code(self):
        """Test HTTPResponse with custom status code"""
        response = HTTPResponse(418, "I'm a teapot")

        self.assertEqual(response.asgi_send_dict['status'], 418)
        self.assertEqual(response.leaf_object, "I'm a teapot")


class TestBadRequestResponse(unittest.TestCase):
    """Test BadRequestResponse class"""

    def test_init(self):
        """Test BadRequestResponse initialization"""
        response = BadRequestResponse()

        self.assertEqual(response.asgi_send_dict['status'], 400)
        self.assertEqual(response.leaf_object, 'Bad Request')

    def test_inherits_from_http_response(self):
        """Test that BadRequestResponse inherits from HTTPResponse"""
        response = BadRequestResponse()
        self.assertIsInstance(response, HTTPResponse)


class TestNotFoundResponse(unittest.TestCase):
    """Test NotFoundResponse class"""

    def test_init(self):
        """Test NotFoundResponse initialization"""
        response = NotFoundResponse()

        self.assertEqual(response.asgi_send_dict['status'], 404)
        self.assertEqual(response.leaf_object, 'Not Found')

    def test_inherits_from_http_response(self):
        """Test that NotFoundResponse inherits from HTTPResponse"""
        response = NotFoundResponse()
        self.assertIsInstance(response, HTTPResponse)


class TestMethodNotAllowedResponse(unittest.TestCase):
    """Test MethodNotAllowedResponse class"""

    def test_init(self):
        """Test MethodNotAllowedResponse initialization"""
        response = MethodNotAllowedResponse()

        self.assertEqual(response.asgi_send_dict['status'], 405)
        self.assertEqual(response.leaf_object, 'Method Not Allowed')

    def test_inherits_from_http_response(self):
        """Test that MethodNotAllowedResponse inherits from HTTPResponse"""
        response = MethodNotAllowedResponse()
        self.assertIsInstance(response, HTTPResponse)


class TestCreatedResponse(unittest.TestCase):
    """Test CreatedResponse class"""

    def test_init(self):
        """Test CreatedResponse initialization"""
        response = CreatedResponse()

        self.assertEqual(response.asgi_send_dict['status'], 201)
        self.assertEqual(response.leaf_object, 'Created')

    def test_inherits_from_http_response(self):
        """Test that CreatedResponse inherits from HTTPResponse"""
        response = CreatedResponse()
        self.assertIsInstance(response, HTTPResponse)


class TestSeeOtherResponse(unittest.TestCase):
    """Test SeeOtherResponse class"""

    def test_init(self):
        """Test SeeOtherResponse initialization"""
        redirect_url = 'https://example.com/redirect'
        response = SeeOtherResponse(redirect_url)

        self.assertEqual(response.asgi_send_dict['type'], 'http.response.start')
        self.assertEqual(response.asgi_send_dict['status'], 303)
        self.assertEqual(response.leaf_object, '')

        # Check headers
        headers = response.asgi_send_dict['headers']
        self.assertEqual(len(headers), 2)
        self.assertEqual(headers[0], (b'content-type', b'application/json'))
        self.assertEqual(headers[1], (b'location', redirect_url.encode('utf8')))

    def test_inherits_from_special_response(self):
        """Test that SeeOtherResponse inherits from SpecialResponse"""
        response = SeeOtherResponse('https://example.com')
        self.assertIsInstance(response, SpecialResponse)

    def test_unicode_redirect_url(self):
        """Test SeeOtherResponse with unicode characters in URL"""
        redirect_url = 'https://example.com/путь'
        response = SeeOtherResponse(redirect_url)

        # Verify URL is properly encoded
        headers = response.asgi_send_dict['headers']
        self.assertEqual(headers[1][0], b'location')
        self.assertEqual(headers[1][1], redirect_url.encode('utf8'))


if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
