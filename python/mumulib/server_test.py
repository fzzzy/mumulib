
import coverage # pragma: no cover

cov = coverage.Coverage(branch=True) # pragma: no cover
cov.start() # pragma: no cover

import unittest # pragma: no cover
import asyncio # pragma: no cover
import json # pragma: no cover

from mumulib.server import ( # pragma: no cover
    parse_json,
    parse_urlencoded,
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

    async def async_test_json_path_extension(self):
        """Test that .json paths set JSON accept headers"""
        root = {'message': 'hello'}
        app = consumers_app(root)

        sent_messages = []
        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}

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
            return {'type': 'http.request', 'body': b'', 'more_body': False}

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


if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
