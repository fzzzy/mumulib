
import coverage # pragma: no cover

cov = coverage.Coverage(branch=True) # pragma: no cover
cov.start() # pragma: no cover

import unittest # pragma: no cover
import asyncio # pragma: no cover
import json # pragma: no cover

from mumulib.server import ( # pragma: no cover
    parse_json,
    parse_urlencoded,
    parse_multipart,
    consumers_app,
    DEFAULT_MAX_BODY_SIZE
)


class TestParseJson(unittest.TestCase):
    """Test parse_json function"""

    async def async_test_parse_json_basic(self):
        """Test parsing basic JSON body"""
        json_data = {"key": "value", "number": 42}
        body_bytes = json.dumps(json_data).encode('utf-8')

        # Mock receive callable that returns the body
        async def receive():
            return {
                'type': 'http.request',
                'body': body_bytes,
                'more_body': False
            }

        result = await parse_json(receive)
        self.assertEqual(result, json_data)

    def test_parse_json_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_basic())

    async def async_test_parse_json_empty_body(self):
        """Test parsing empty JSON body"""
        # Mock receive callable that returns empty body
        async def receive():
            return {
                'type': 'http.request',
                'body': b'',
                'more_body': False
            }

        result = await parse_json(receive)
        self.assertIsNone(result)

    def test_parse_json_empty_body(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_empty_body())

    async def async_test_parse_json_chunked(self):
        """Test parsing JSON body sent in chunks"""
        json_data = {"key": "value", "number": 42}
        body_bytes = json.dumps(json_data).encode('utf-8')

        # Split into chunks
        chunk1 = body_bytes[:10]
        chunk2 = body_bytes[10:]

        # Mock receive that returns chunks
        chunks = [
            {'type': 'http.request', 'body': chunk1, 'more_body': True},
            {'type': 'http.request', 'body': chunk2, 'more_body': False}
        ]
        chunk_iter = iter(chunks)

        async def receive():
            return next(chunk_iter)

        result = await parse_json(receive)
        self.assertEqual(result, json_data)

    def test_parse_json_chunked(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_chunked())

    async def async_test_parse_json_size_limit_exceeded(self):
        """Test that parse_json raises error when body exceeds size limit"""
        # Create body larger than limit
        large_body = b'x' * (DEFAULT_MAX_BODY_SIZE + 1)

        async def receive():
            return {
                'type': 'http.request',
                'body': large_body,
                'more_body': False
            }

        with self.assertRaises(ValueError) as context:
            await parse_json(receive, max_size=DEFAULT_MAX_BODY_SIZE)

        self.assertIn("Request body too large", str(context.exception))

    def test_parse_json_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_size_limit_exceeded())


class TestParseUrlencoded(unittest.TestCase):
    """Test parse_urlencoded function"""

    async def async_test_parse_urlencoded_basic(self):
        """Test parsing basic URL-encoded body"""
        body_bytes = b'key=value&number=42&name=John%20Doe'

        async def receive():
            return {
                'type': 'http.request',
                'body': body_bytes,
                'more_body': False
            }

        result = await parse_urlencoded(receive)
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['number'], '42')
        self.assertEqual(result['name'], 'John Doe')

    def test_parse_urlencoded_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_basic())

    async def async_test_parse_urlencoded_array_syntax(self):
        """Test parsing URL-encoded arrays with key[] syntax"""
        body_bytes = b'items[]=apple&items[]=banana&items[]=cherry'

        async def receive():
            return {
                'type': 'http.request',
                'body': body_bytes,
                'more_body': False
            }

        result = await parse_urlencoded(receive)
        self.assertIn('items[]', result)
        self.assertEqual(result['items[]'], ['apple', 'banana', 'cherry'])

    def test_parse_urlencoded_array_syntax(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_array_syntax())

    async def async_test_parse_urlencoded_empty_body(self):
        """Test parsing empty URL-encoded body"""
        async def receive():
            return {
                'type': 'http.request',
                'body': b'',
                'more_body': False
            }

        result = await parse_urlencoded(receive)
        self.assertEqual(result, {})

    def test_parse_urlencoded_empty_body(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_empty_body())

    async def async_test_parse_urlencoded_chunked(self):
        """Test parsing URL-encoded body sent in chunks"""
        body_bytes = b'key=value&number=42'
        chunk1 = body_bytes[:8]
        chunk2 = body_bytes[8:]

        chunks = [
            {'type': 'http.request', 'body': chunk1, 'more_body': True},
            {'type': 'http.request', 'body': chunk2, 'more_body': False}
        ]
        chunk_iter = iter(chunks)

        async def receive():
            return next(chunk_iter)

        result = await parse_urlencoded(receive)
        self.assertEqual(result['key'], 'value')
        self.assertEqual(result['number'], '42')

    def test_parse_urlencoded_chunked(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_chunked())

    async def async_test_parse_urlencoded_size_limit(self):
        """Test that parse_urlencoded raises error when body exceeds size limit"""
        large_body = b'x' * (DEFAULT_MAX_BODY_SIZE + 1)

        async def receive():
            return {
                'type': 'http.request',
                'body': large_body,
                'more_body': False
            }

        with self.assertRaises(ValueError) as context:
            await parse_urlencoded(receive, max_size=DEFAULT_MAX_BODY_SIZE)

        self.assertIn("Request body too large", str(context.exception))

    def test_parse_urlencoded_size_limit(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_size_limit())


class TestConsumersAppLifespan(unittest.TestCase):
    """Test ASGI lifespan handling"""

    async def async_test_lifespan_startup_shutdown(self):
        """Test lifespan startup and shutdown messages"""
        root = {'data': 'test'}
        app = consumers_app(root)

        # Track what was sent
        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        # Simulate lifespan startup
        startup_message = {'type': 'lifespan.startup'}
        shutdown_message = {'type': 'lifespan.shutdown'}

        messages = [startup_message, shutdown_message]
        message_iter = iter(messages)

        async def receive():
            return next(message_iter)

        scope = {'type': 'lifespan'}

        # Run the app with lifespan scope
        await app(scope, receive, send)

        # Verify startup complete was sent
        self.assertEqual(sent_messages[0], {'type': 'lifespan.startup.complete'})
        # Verify shutdown complete was sent
        self.assertEqual(sent_messages[1], {'type': 'lifespan.shutdown.complete'})

    def test_lifespan_startup_shutdown(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_lifespan_startup_shutdown())


class TestConsumersAppRouting(unittest.TestCase):
    """Test content-type routing based on path extensions"""

    async def async_test_json_content_type_header(self):
        """Test that application/json content-type header is handled correctly"""
        root = {'data': {'result': 'success'}}
        app = consumers_app(root)

        json_body = json.dumps({'key': 'value'})

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                'type': 'http.request',
                'body': json_body.encode('utf-8'),
                'more_body': False
            }

        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/data',
            'headers': [(b'content-type', b'application/json')],
            'state': {}
        }

        await app(scope, receive, send)

        # Check that response has JSON content-type
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        headers = dict(response_start['headers'])
        self.assertIn(b'application/json', headers[b'content-type'])

    def test_json_content_type_header(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_content_type_header())

    async def async_test_json_path_extension(self):
        """Test that .json paths set JSON accept headers"""
        root = {'message': 'hello'}
        app = consumers_app(root)

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/message.json',
            'headers': [],
            'state': {}
        }

        await app(scope, receive, send)

        # Check that response has JSON content-type
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        headers = dict(response_start['headers'])
        self.assertIn(b'application/json', headers[b'content-type'])

    def test_json_path_extension(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_path_extension())

    async def async_test_html_path_extension(self):
        """Test that .html paths set HTML accept headers"""
        root = {'message.html': 'hello'}
        app = consumers_app(root)

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/message.html',
            'headers': [],
            'state': {}
        }

        await app(scope, receive, send)

        # Check that response has HTML content-type
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        headers = dict(response_start['headers'])
        self.assertIn(b'text/html', headers[b'content-type'])

    def test_html_path_extension(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_html_path_extension())


class TestParseMultipart(unittest.TestCase):
    """Test parse_multipart function"""

    async def async_test_parse_multipart_basic(self):
        """Test parsing basic multipart form data"""
        boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="field1"\r\n'
            b'\r\n'
            b'value1\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="field2"\r\n'
            b'\r\n'
            b'value2\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW--'
        )

        async def receive():
            return {
                'type': 'http.request',
                'body': body,
                'more_body': False
            }

        result = await parse_multipart(receive, boundary)
        self.assertEqual(result, {'field1': 'value1', 'field2': 'value2'})

    def test_parse_multipart_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_basic())

    async def async_test_parse_multipart_with_file(self):
        """Test parsing multipart with binary file content"""
        boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="file"; filename="test.bin"\r\n'
            b'Content-Type: application/octet-stream\r\n'
            b'\r\n'
            b'binary content\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW--'
        )

        async def receive():
            return {
                'type': 'http.request',
                'body': body,
                'more_body': False
            }

        result = await parse_multipart(receive, boundary)
        self.assertEqual(result, {'file': b'binary content'})

    def test_parse_multipart_with_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_with_file())


class TestBytesResultHandling(unittest.TestCase):
    """Test handling of bytes results"""

    async def async_test_bytes_result(self):
        """Test that routes returning bytes are handled correctly"""
        root = {'binary': b'binary data here'}
        app = consumers_app(root)

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

        scope = {
            'type': 'http',
            'method': 'GET',
            'path': '/binary',
            'headers': [],
            'state': {}
        }

        await app(scope, receive, send)

        # Check that we got a response
        self.assertGreater(len(sent_messages), 0)
        response_body = sent_messages[-1]
        self.assertEqual(response_body['type'], 'http.response.body')
        # The bytes result should be in the body
        self.assertIn(b'binary data here', response_body['body'])

    def test_bytes_result(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_bytes_result())


class TestExceptionHandling(unittest.TestCase):
    """Test exception handling during routing and processing"""

    async def async_test_exception_during_consume(self):
        """Test that exceptions during consume are caught and return 500"""
        # Create a broken consumer that raises an exception
        class BrokenObject:
            pass

        # Register a consumer that will raise an exception
        from mumulib.consumers import add_consumer

        async def broken_consumer(parent, segments, state, send):
            raise RuntimeError("Intentional error during consume")

        # Temporarily register the broken consumer
        add_consumer(BrokenObject, broken_consumer)

        try:
            # Use BrokenObject as the root so it gets consumed directly
            root = BrokenObject()
            app = consumers_app(root)

            sent_messages = []
            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/anything',
                'headers': [],
                'state': {}
            }

            await app(scope, receive, send)

            # Should get 500 Internal Server Error
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 500)

            # Check error message
            response_body = sent_messages[1]
            body_data = json.loads(response_body['body'].decode('utf-8'))
            self.assertEqual(body_data['error'], 'Internal Server Error')
            self.assertIn('Intentional error', body_data['message'])
        finally:
            # Clean up - remove the broken consumer
            from mumulib.consumers import _consumer_adapters
            if BrokenObject in _consumer_adapters:
                del _consumer_adapters[BrokenObject]

    def test_exception_during_consume(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_exception_during_consume())

    async def async_test_special_response_result(self):
        """Test that SpecialResponse returned directly from consume is handled"""
        from mumulib.mumutypes import HTTPResponse

        # Create a custom object that returns a SpecialResponse
        class CustomResponseObject:
            pass

        from mumulib.consumers import add_consumer

        async def custom_consumer(parent, segments, state, send):
            # Return a SpecialResponse directly (like PUT/DELETE operations do)
            return HTTPResponse(201, 'Custom response body')

        add_consumer(CustomResponseObject, custom_consumer)

        try:
            root = CustomResponseObject()
            app = consumers_app(root)

            sent_messages = []
            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/test',
                'headers': [],
                'state': {}
            }

            await app(scope, receive, send)

            # Should get the custom response
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 201)

            # Check body
            response_body = sent_messages[1]
            self.assertEqual(response_body['type'], 'http.response.body')
            self.assertIn(b'Custom response body', response_body['body'])
        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters
            if CustomResponseObject in _consumer_adapters:
                del _consumer_adapters[CustomResponseObject]

    def test_special_response_result(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_result())

    async def async_test_special_response_exception_during_produce(self):
        """Test that SpecialResponse raised as exception during produce is handled"""
        from mumulib.mumutypes import HTTPResponse
        from mumulib.producers import add_producer

        # Create an object with a producer that raises SpecialResponse
        class ProducerObject:
            async def __aiter__(self):
                # Raise SpecialResponse as exception during iteration
                raise HTTPResponse(403, 'Forbidden by producer')
                yield  # pragma: no cover

        add_producer(ProducerObject, lambda obj, state: obj, '*/*')

        try:
            root = {'test': ProducerObject()}
            app = consumers_app(root)

            sent_messages = []
            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/test',
                'headers': [],
                'state': {}
            }

            await app(scope, receive, send)

            # Should get the special response
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 403)

            # Check body contains the leaf object
            response_body = sent_messages[1]
            self.assertIn(b'Forbidden by producer', response_body['body'])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and ProducerObject in _producer_adapters['*/*']:
                del _producer_adapters['*/*'][ProducerObject]

    def test_special_response_exception_during_produce(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_exception_during_produce())

    async def async_test_generic_exception_during_produce(self):
        """Test that generic exception during produce returns 500"""
        from mumulib.producers import add_producer

        # Create an object with a producer that raises an exception
        class BrokenProducer:
            async def __aiter__(self):
                raise RuntimeError("Producer error during iteration")
                yield  # pragma: no cover

        add_producer(BrokenProducer, lambda obj, state: obj, '*/*')

        try:
            root = {'test': BrokenProducer()}
            app = consumers_app(root)

            sent_messages = []
            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {'type': 'http.request', 'body': b'', 'more_body': False}  # pragma: no cover

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/test',
                'headers': [],
                'state': {}
            }

            await app(scope, receive, send)

            # Should get 500 error
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 500)

            # Check error message
            response_body = sent_messages[1]
            body_data = json.loads(response_body['body'].decode('utf-8'))
            self.assertEqual(body_data['error'], 'Internal Server Error')
            self.assertIn('Producer error', body_data['message'])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and BrokenProducer in _producer_adapters['*/*']:
                del _producer_adapters['*/*'][BrokenProducer]

    def test_generic_exception_during_produce(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_generic_exception_during_produce())


class TestUnknownContentType(unittest.TestCase):
    """Test handling of unknown content types"""

    async def async_test_unknown_content_type(self):
        """Test that unknown content types print a message"""
        root = {'data': 'test'}
        app = consumers_app(root)

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {'type': 'http.request', 'body': b'test data', 'more_body': False}  # pragma: no cover

        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/data',
            'headers': [(b'content-type', b'application/x-custom-type')],
            'state': {}
        }

        await app(scope, receive, send)

        # Should still get a response (unknown types are just printed, not rejected)
        self.assertGreater(len(sent_messages), 0)

    def test_unknown_content_type(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_unknown_content_type())


class TestRequestSizeLimits(unittest.TestCase):
    """Test request body size limit enforcement"""

    async def async_test_json_size_limit_exceeded(self):
        """Test that oversized JSON body triggers 413 error"""
        root = {'data': 'test'}
        app = consumers_app(root)

        # Create a body that exceeds the default limit (10MB)
        oversized_body = json.dumps({'data': 'x' * (DEFAULT_MAX_BODY_SIZE + 1000)}).encode('utf-8')

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                'type': 'http.request',
                'body': oversized_body,
                'more_body': False
            }

        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/data',
            'headers': [(b'content-type', b'application/json')],
            'state': {}
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        self.assertEqual(response_start['status'], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body['body'].decode('utf-8'))
        self.assertEqual(body_data['error'], 'Payload Too Large')

    def test_json_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_size_limit_exceeded())

    async def async_test_urlencoded_size_limit_exceeded(self):
        """Test that oversized urlencoded body triggers 413 error"""
        root = {'data': 'test'}
        app = consumers_app(root)

        # Create a body that exceeds the default limit (10MB)
        oversized_body = ('key=' + 'x' * (DEFAULT_MAX_BODY_SIZE + 1000)).encode('utf-8')

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                'type': 'http.request',
                'body': oversized_body,
                'more_body': False
            }

        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/data',
            'headers': [(b'content-type', b'application/x-www-form-urlencoded')],
            'state': {}
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        self.assertEqual(response_start['status'], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body['body'].decode('utf-8'))
        self.assertEqual(body_data['error'], 'Payload Too Large')

    def test_urlencoded_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_urlencoded_size_limit_exceeded())

    async def async_test_multipart_size_limit_exceeded(self):
        """Test that oversized multipart body triggers 413 error"""
        root = {'data': 'test'}
        app = consumers_app(root)

        boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
        # Create a body that exceeds the default limit (10MB)
        oversized_content = b'x' * (DEFAULT_MAX_BODY_SIZE + 1000)
        oversized_body = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="huge_field"\r\n'
            b'\r\n'
            + oversized_content + b'\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW--'
        )

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                'type': 'http.request',
                'body': oversized_body,
                'more_body': False
            }

        scope = {
            'type': 'http',
            'method': 'POST',
            'path': '/data',
            'headers': [(b'content-type', b'multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW')],
            'state': {}
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start['type'], 'http.response.start')
        self.assertEqual(response_start['status'], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body['body'].decode('utf-8'))
        self.assertEqual(body_data['error'], 'Payload Too Large')

    def test_multipart_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_multipart_size_limit_exceeded())


if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
