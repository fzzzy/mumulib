
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

    async def async_test_parse_multipart_multiple_chunks(self):
        """Test parsing multipart with multiple chunks (line 113->100)"""
        boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
        # Split the multipart body into multiple chunks
        chunk1 = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="field1"\r\n'
            b'\r\n'
            b'value1\r\n'
        )
        chunk2 = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="field2"\r\n'
            b'\r\n'
            b'value2\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW--'
        )

        chunks = [chunk1, chunk2]
        chunk_index = {'current': 0}

        async def receive():
            idx = chunk_index['current']
            chunk_index['current'] += 1
            if idx < len(chunks):
                return {
                    'type': 'http.request',
                    'body': chunks[idx],
                    'more_body': idx < len(chunks) - 1  # True for all but last chunk
                }
            return {  # pragma: no cover
                'type': 'http.request',
                'body': b'',
                'more_body': False
            }

        result = await parse_multipart(receive, boundary)
        self.assertEqual(result, {'field1': 'value1', 'field2': 'value2'})

    def test_parse_multipart_multiple_chunks(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_multiple_chunks())

    async def async_test_parse_multipart_malformed_part(self):
        """Test parsing multipart with malformed part missing Content-Disposition (line 125->116)"""
        boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body = (
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            b'Content-Disposition: form-data; name="field1"\r\n'
            b'\r\n'
            b'value1\r\n'
            b'------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n'
            # Malformed part - no Content-Disposition header at all
            b'Some-Other-Header: value\r\n'
            b'\r\n'
            b'ignored content\r\n'
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
        # Should only contain the valid fields, malformed part is skipped
        self.assertEqual(result, {'field1': 'value1', 'field2': 'value2'})

    def test_parse_multipart_malformed_part(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_malformed_part())


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
        self.assertGreater(len(sent_messages), 1)

        # The first message should be http.response.start
        self.assertEqual(sent_messages[0]['type'], 'http.response.start')

        # The bytes result should be in one of the body messages
        body_messages = [msg for msg in sent_messages if msg['type'] == 'http.response.body']
        self.assertGreater(len(body_messages), 0)

        # Find the message with our binary data
        found = any(b'binary data here' in msg['body'] for msg in body_messages)
        self.assertTrue(found, f"Binary data not found in body messages: {body_messages}")

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
            if BrokenObject in _consumer_adapters:  # pragma: no cover
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
            if CustomResponseObject in _consumer_adapters:  # pragma: no cover
                del _consumer_adapters[CustomResponseObject]

    def test_special_response_result(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_result())

    async def async_test_special_response_with_non_string_leaf(self):
        """Test that SpecialResponse with non-string/non-bytes leaf_object is handled (line 258)"""
        from mumulib.mumutypes import SpecialResponse

        # Create a custom object that returns a SpecialResponse with dict leaf_object
        class DictResponseObject:
            pass

        from mumulib.consumers import add_consumer

        async def dict_consumer(parent, segments, state, send):
            # Return a SpecialResponse with a dict as leaf_object
            return SpecialResponse(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [(b'content-type', b'text/plain')],
                },
                {'status': 'ok', 'count': 42}  # dict leaf_object
            )

        add_consumer(DictResponseObject, dict_consumer)

        try:
            root = DictResponseObject()
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
            self.assertEqual(response_start['status'], 200)

            # Check body - dict should be converted to string
            response_body = sent_messages[1]
            self.assertEqual(response_body['type'], 'http.response.body')
            # The dict gets str() applied, which gives something like "{'status': 'ok', 'count': 42}"
            self.assertIn(b'status', response_body['body'])
            self.assertIn(b'ok', response_body['body'])
        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters
            if DictResponseObject in _consumer_adapters:  # pragma: no cover
                del _consumer_adapters[DictResponseObject]

    def test_special_response_with_non_string_leaf(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_with_non_string_leaf())

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
            if '*/*' in _producer_adapters and ProducerObject in _producer_adapters['*/*']:  # pragma: no cover
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
            if '*/*' in _producer_adapters and BrokenProducer in _producer_adapters['*/*']:  # pragma: no cover
                del _producer_adapters['*/*'][BrokenProducer]

    def test_generic_exception_during_produce(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_generic_exception_during_produce())

    async def async_test_special_response_exception_after_first_chunk(self):
        """Test SpecialResponse exception after first chunk sent (line 237->240)"""
        from mumulib.mumutypes import HTTPResponse
        from mumulib.producers import add_producer

        class DelayedSpecialResponseProducer:
            pass

        async def produce_then_special_response(thing, state):
            """Producer that yields a chunk, then raises SpecialResponse"""
            yield 'First chunk'
            # After first chunk is sent, raise SpecialResponse
            raise HTTPResponse(403, 'Delayed forbidden')

        add_producer(DelayedSpecialResponseProducer, produce_then_special_response, '*/*')

        try:
            root = {'test': DelayedSpecialResponseProducer()}
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

            # Should have sent the first chunk normally
            self.assertEqual(sent_messages[0]['type'], 'http.response.start')
            self.assertEqual(sent_messages[1]['body'], b'First chunk')

            # Final body should contain the SpecialResponse leaf_object
            final_body = sent_messages[-1]
            self.assertEqual(final_body['type'], 'http.response.body')
            self.assertIn(b'Delayed forbidden', final_body['body'])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and DelayedSpecialResponseProducer in _producer_adapters['*/*']:  # pragma: no cover
                del _producer_adapters['*/*'][DelayedSpecialResponseProducer]

    def test_special_response_exception_after_first_chunk(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_exception_after_first_chunk())

    async def async_test_generic_exception_after_first_chunk(self):
        """Test generic exception after first chunk sent (line 243->250)"""
        from mumulib.producers import add_producer

        class DelayedExceptionProducer:
            pass

        async def produce_then_error(thing, state):
            """Producer that yields a chunk, then raises generic exception"""
            yield 'First chunk'
            # After first chunk is sent, raise a generic exception
            raise RuntimeError('Delayed error')

        add_producer(DelayedExceptionProducer, produce_then_error, '*/*')

        try:
            root = {'test': DelayedExceptionProducer()}
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

            # Should have sent the first chunk normally
            self.assertEqual(sent_messages[0]['type'], 'http.response.start')
            self.assertEqual(sent_messages[1]['body'], b'First chunk')

            # Final body should contain the error as JSON
            final_body = sent_messages[-1]
            self.assertEqual(final_body['type'], 'http.response.body')
            body_data = json.loads(final_body['body'].decode('utf-8'))
            self.assertEqual(body_data['error'], 'Internal Server Error')
            self.assertIn('Delayed error', body_data['message'])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and DelayedExceptionProducer in _producer_adapters['*/*']:  # pragma: no cover
                del _producer_adapters['*/*'][DelayedExceptionProducer]

    def test_generic_exception_after_first_chunk(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_generic_exception_after_first_chunk())


class TestSpecialResponseWithWriter(unittest.TestCase):
    """Test handling of SpecialResponse with writer callback in produce"""

    async def async_test_special_response_with_writer(self):
        """Test that SpecialResponse with writer callback is handled correctly (lines 203-210)"""
        from mumulib.producers import add_producer
        from mumulib.mumutypes import SpecialResponse

        # Track writer execution
        writer_called = {'value': False}

        async def test_writer(send, receive):
            """A writer that sends additional data"""
            writer_called['value'] = True
            await send({
                'type': 'http.response.body',
                'body': b'Additional data from writer',
                'more_body': False,
            })

        class WriterProducerObject:
            """Object with a producer that yields SpecialResponse with writer"""
            pass

        async def produce_with_writer(thing, state):
            """Producer that yields a SpecialResponse with writer callback, then additional chunks"""
            yield SpecialResponse(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [(b'content-type', b'text/plain')],
                },
                'Initial response',  # leaf_object as string (will be encoded)
                test_writer
            )
            # Yield a second chunk to cover lines 229-230 (else clause for additional chunks)
            yield 'Second chunk from producer'

        try:
            # Register the producer (type, producer_func, mimetype)
            add_producer(WriterProducerObject, produce_with_writer, '*/*')

            root = {'test': WriterProducerObject()}
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

            # Verify the response includes the special response headers
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 200)
            self.assertEqual(response_start['headers'], [(b'content-type', b'text/plain')])

            # Verify the initial body was sent (from SpecialResponse leaf_object)
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1['type'], 'http.response.body')
            self.assertEqual(response_body_1['body'], b'Initial response')
            self.assertTrue(response_body_1['more_body'])

            # Verify the writer was called and sent additional data
            self.assertTrue(writer_called['value'])
            response_body_2 = sent_messages[2]
            self.assertEqual(response_body_2['type'], 'http.response.body')
            self.assertEqual(response_body_2['body'], b'Additional data from writer')
            # Note: more_body should be False from the writer
            self.assertFalse(response_body_2['more_body'])

            # Verify the second chunk from producer was sent (covers lines 229-230)
            response_body_3 = sent_messages[3]
            self.assertEqual(response_body_3['type'], 'http.response.body')
            self.assertEqual(response_body_3['body'], b'Second chunk from producer')
            self.assertTrue(response_body_3['more_body'])

            # Final newline chunk
            response_body_4 = sent_messages[4]
            self.assertEqual(response_body_4['type'], 'http.response.body')
            self.assertEqual(response_body_4['body'], b'\n')
            self.assertFalse(response_body_4['more_body'])

        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and WriterProducerObject in _producer_adapters['*/*']:  # pragma: no cover
                del _producer_adapters['*/*'][WriterProducerObject]

    def test_special_response_with_writer(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_with_writer())

    async def async_test_special_response_without_writer(self):
        """Test that SpecialResponse without writer callback is handled correctly (line 211->226)"""
        from mumulib.producers import add_producer
        from mumulib.mumutypes import SpecialResponse

        class NoWriterProducerObject:
            """Object with a producer that yields SpecialResponse without writer"""
            pass

        async def produce_without_writer(thing, state):
            """Producer that yields a SpecialResponse without writer callback"""
            yield SpecialResponse(
                {
                    'type': 'http.response.start',
                    'status': 200,
                    'headers': [(b'content-type', b'text/plain')],
                },
                'Response without writer'
            )
            # No writer parameter, so chunk.writer will be None

        try:
            # Register the producer (type, producer_func, mimetype)
            add_producer(NoWriterProducerObject, produce_without_writer, '*/*')

            root = {'test': NoWriterProducerObject()}
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

            # Verify the response includes the special response headers
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 200)
            self.assertEqual(response_start['headers'], [(b'content-type', b'text/plain')])

            # Verify the body was sent
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1['type'], 'http.response.body')
            self.assertEqual(response_body_1['body'], b'Response without writer')
            self.assertTrue(response_body_1['more_body'])

            # Final newline chunk
            response_body_2 = sent_messages[2]
            self.assertEqual(response_body_2['type'], 'http.response.body')
            self.assertEqual(response_body_2['body'], b'\n')
            self.assertFalse(response_body_2['more_body'])

        finally:
            # Clean up
            from mumulib.producers import _producer_adapters
            if '*/*' in _producer_adapters and NoWriterProducerObject in _producer_adapters['*/*']:  # pragma: no cover
                del _producer_adapters['*/*'][NoWriterProducerObject]

    def test_special_response_without_writer(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_without_writer())


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


class TestEventSource(unittest.TestCase):
    """Test EventSource SSE streaming functionality"""

    async def async_test_eventsource_streaming(self):
        """Test EventSource with queue events and client disconnect (lines 272-309)"""
        from mumulib.server import EventSource
        from mumulib.consumers import add_consumer

        # Create a queue for sending events
        event_queue = asyncio.Queue()

        # Create an EventSource producer
        eventsource_handler = EventSource(event_queue)

        # Create a custom object to attach the EventSource
        class StreamObject:
            pass

        # Register as a consumer that returns the EventSource
        async def stream_consumer(parent, segments, state, send):
            return eventsource_handler

        add_consumer(StreamObject, stream_consumer)

        try:
            root = StreamObject()
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():  # pragma: no cover
                # Simulate client staying connected for a short time
                await asyncio.sleep(0.1)
                return {'type': 'http.request', 'body': b'', 'more_body': False}

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/stream',
                'headers': [],
                'state': {}
            }

            # Run the app in a task so we can cancel it (to trigger CancelledError)
            app_task = asyncio.create_task(app(scope, receive, send))

            # Give it a moment to start
            await asyncio.sleep(0.01)

            # Put events in the queue while it's running
            await event_queue.put('event1')
            await asyncio.sleep(0.01)
            await event_queue.put('event2')
            await asyncio.sleep(0.01)

            # Cancel the task to trigger CancelledError in the writer
            app_task.cancel()
            try:
                await app_task
            except asyncio.CancelledError:  # pragma: no cover
                pass  # Expected

            # Verify SSE response was sent
            self.assertGreater(len(sent_messages), 0)

            # Check the response start has SSE headers
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 200)
            headers_dict = dict(response_start['headers'])
            self.assertEqual(headers_dict[b'content-type'], b'text/event-stream; charset=UTF-8')
            self.assertEqual(headers_dict[b'cache-control'], b'no-cache')

            # Check the initial ping event was sent
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1['type'], 'http.response.body')
            self.assertIn(b'event: ping', response_body_1['body'])
            self.assertTrue(response_body_1['more_body'])

            # Check that events from the queue were sent
            event_bodies = [msg['body'] for msg in sent_messages if msg['type'] == 'http.response.body']
            event_bodies_str = b''.join(event_bodies).decode('utf-8')

            # At least one of our events should have been sent
            self.assertTrue('event1' in event_bodies_str or 'event2' in event_bodies_str,
                          f"Expected events in {event_bodies_str}")

        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters
            if StreamObject in _consumer_adapters:  # pragma: no cover
                del _consumer_adapters[StreamObject]

    def test_eventsource_streaming(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_eventsource_streaming())

    async def async_test_eventsource_client_disconnect(self):
        """Test EventSource with client disconnect (lines 295-296)"""
        from mumulib.server import EventSource
        from mumulib.consumers import add_consumer

        # Create a queue for sending events
        event_queue = asyncio.Queue()

        # Create an EventSource producer
        eventsource_handler = EventSource(event_queue)

        # Create a custom object to attach the EventSource
        class StreamObject2:
            pass

        # Register as a consumer that returns the EventSource
        async def stream_consumer(parent, segments, state, send):
            return eventsource_handler

        add_consumer(StreamObject2, stream_consumer)

        try:
            root = StreamObject2()
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            # This receive will complete immediately, simulating client disconnect
            async def receive():
                return {'type': 'http.disconnect'}

            scope = {
                'type': 'http',
                'method': 'GET',
                'path': '/stream',
                'headers': [],
                'state': {}
            }

            # Run the app - it should handle the disconnect gracefully
            await app(scope, receive, send)

            # Verify SSE response was sent
            self.assertGreater(len(sent_messages), 0)

            # Check the response start has SSE headers
            response_start = sent_messages[0]
            self.assertEqual(response_start['type'], 'http.response.start')
            self.assertEqual(response_start['status'], 200)

            # Check the initial ping event was sent
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1['type'], 'http.response.body')
            self.assertIn(b'event: ping', response_body_1['body'])

        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters
            if StreamObject2 in _consumer_adapters:  # pragma: no cover
                del _consumer_adapters[StreamObject2]

    def test_eventsource_client_disconnect(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_eventsource_client_disconnect())


if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
