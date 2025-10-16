
import coverage # pragma: no cover

cov = coverage.Coverage(branch=True) # pragma: no cover
cov.start() # pragma: no cover

import unittest # pragma: no cover
import asyncio # pragma: no cover

from mumulib.producers import ( # pragma: no cover
    add_producer,
    produce,
    custom_serializer,
    produce_json,
    produce_file
)
from types import MappingProxyType # pragma: no cover
from mumulib import mumutypes # pragma: no cover


class TestCustomSerializer(unittest.TestCase):
    """Test custom_serializer function"""

    def test_mapping_proxy_type(self):
        """Test serialization of MappingProxyType"""
        original = {'key': 'value', 'number': 42}
        proxy = MappingProxyType(original)

        result = custom_serializer(proxy)

        self.assertEqual(result, original)
        self.assertIsInstance(result, dict)

    def test_non_mapping_proxy_type(self):
        """Test serialization of non-MappingProxyType returns None"""
        result = custom_serializer("string")
        self.assertIsNone(result)

        result = custom_serializer(123)
        self.assertIsNone(result)

        result = custom_serializer([1, 2, 3])
        self.assertIsNone(result)


class TestAddProducer(unittest.TestCase):
    """Test add_producer function"""

    async def async_test_add_producer_default_mime(self):
        """Test adding producer with default mime type"""
        from mumulib.producers import _producer_adapters

        # Create a simple producer function
        async def test_producer(obj, state):
            yield "test"

        # Add it for a custom type
        class CustomType:
            pass

        add_producer(CustomType, test_producer)

        # Verify it was added to default mime type
        self.assertIn('*/*', _producer_adapters)
        self.assertIn(CustomType, _producer_adapters['*/*'])
        self.assertEqual(_producer_adapters['*/*'][CustomType], test_producer)

        # Now actually use it by calling produce
        obj = CustomType()
        state = {'accept': ['*/*']}
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify the producer was called and produced output
        self.assertEqual(chunks, ['test'])

    def test_add_producer_default_mime(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_add_producer_default_mime())

    async def async_test_add_producer_custom_mime(self):
        """Test adding producer with custom mime type"""
        from mumulib.producers import _producer_adapters

        # Create a simple producer function
        async def xml_producer(obj, state):
            yield "<xml/>"

        # Add it for a custom mime type
        class CustomType:
            pass

        add_producer(CustomType, xml_producer, 'application/xml')

        # Verify it was added to custom mime type
        self.assertIn('application/xml', _producer_adapters)
        self.assertIn(CustomType, _producer_adapters['application/xml'])
        self.assertEqual(_producer_adapters['application/xml'][CustomType], xml_producer)

        # Now actually use it by calling produce with XML accept header
        obj = CustomType()
        state = {'accept': ['application/xml']}
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify the XML producer was called and produced output
        self.assertEqual(chunks, ['<xml/>'])

    def test_add_producer_custom_mime(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_add_producer_custom_mime())


class TestProduceWithAdapters(unittest.TestCase):
    """Test produce function with custom adapters"""

    async def async_test_adapter_mechanism(self):
        """Test that registered adapters are used based on accept header"""
        # Create a custom type
        class CustomType:
            def __init__(self, data):
                self.data = data

        # Create a custom producer
        async def custom_producer(obj, state):
            yield f"CUSTOM:{obj.data}"

        # Register the producer for text/custom mime type
        add_producer(CustomType, custom_producer, 'text/custom')

        # Create test object and state
        obj = CustomType("test-data")
        state = {'accept': ['text/custom', 'application/json']}

        # Call produce and collect output
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify custom producer was used
        self.assertEqual(chunks, ['CUSTOM:test-data'])

    def test_adapter_mechanism(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_adapter_mechanism())

    async def async_test_adapter_fallback(self):
        """Test fallback when no adapter matches"""
        # Create a custom type without registering a producer
        class UnregisteredType:
            def __str__(self):
                return "unregistered-string"

        obj = UnregisteredType()
        state = {'accept': ['text/custom', 'application/xml']}

        # Call produce - should fall back to str()
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify fallback to str() was used
        self.assertEqual(chunks, ['unregistered-string'])

    def test_adapter_fallback(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_adapter_fallback())

    async def async_test_json_adapter(self):
        """Test that JSON producer is used when accept includes application/json"""
        # Test with dict (registered for JSON)
        obj = {'key': 'value', 'number': 42}
        state = {'accept': ['application/json']}

        # Call produce and collect output
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify JSON was produced
        import json
        self.assertEqual(chunks, [json.dumps(obj)])

    def test_json_adapter(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_adapter())


class TestProduceWithFunctions(unittest.TestCase):
    """Test produce function with function objects"""

    async def async_test_function_producer(self):
        """Test that function objects are called as producers"""
        # Create a function that acts as a producer
        async def my_function(func, state):
            yield "function-output-1"
            yield "function-output-2"

        # State with accept headers that won't match any adapter
        state = {'accept': ['text/plain']}

        # Call produce with the function
        chunks = []
        async for chunk in produce(my_function, state):
            chunks.append(chunk)

        # Verify function was called and produced output
        self.assertEqual(chunks, ['function-output-1', 'function-output-2'])

    def test_function_producer(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_function_producer())

    async def async_test_function_receives_itself(self):
        """Test that function producer receives itself as first argument"""
        # Track what arguments the function receives
        received_args = []

        async def tracking_function(func, state):
            received_args.append(('func', func))
            received_args.append(('state', state))
            yield "output"

        state = {'accept': ['text/plain']}

        # Call produce
        chunks = []
        async for chunk in produce(tracking_function, state):
            chunks.append(chunk)

        # Verify function received itself as first argument
        self.assertEqual(len(received_args), 2)
        self.assertEqual(received_args[0][0], 'func')
        self.assertEqual(received_args[0][1], tracking_function)
        self.assertEqual(received_args[1][0], 'state')
        self.assertEqual(received_args[1][1], state)

    def test_function_receives_itself(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_function_receives_itself())


class TestProduceJson(unittest.TestCase):
    """Test produce_json function"""

    async def async_test_produce_json_dict(self):
        """Test JSON production with dict"""
        obj = {'key': 'value', 'number': 42}
        state = {}

        chunks = []
        async for chunk in produce_json(obj, state):
            chunks.append(chunk)

        import json
        self.assertEqual(chunks, [json.dumps(obj)])

    def test_produce_json_dict(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_json_dict())

    async def async_test_produce_json_with_mapping_proxy(self):
        """Test JSON production with MappingProxyType"""
        original = {'key': 'value', 'number': 42}
        proxy = MappingProxyType(original)
        state = {}

        chunks = []
        async for chunk in produce_json(proxy, state):
            chunks.append(chunk)

        import json
        # Should serialize as dict due to custom_serializer
        self.assertEqual(chunks, [json.dumps(original)])

    def test_produce_json_with_mapping_proxy(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_json_with_mapping_proxy())


class TestProduceFile(unittest.TestCase):
    """Test produce_file function with actual files"""

    async def async_test_produce_text_file(self):
        """Test producing a text file"""
        # Use an actual text file from the project
        test_file_path = '../../python/mumulib.egg-info/top_level.txt'

        with open(test_file_path, 'r') as file_obj:
            state = {}

            # Call produce_file
            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            # Should return exactly one SpecialResponse
            self.assertEqual(len(chunks), 1)

            # Verify it's a SpecialResponse
            response = chunks[0]
            self.assertIsInstance(response, mumutypes.SpecialResponse)

            # Verify ASGI dict structure
            self.assertEqual(response.asgi_send_dict['type'], 'http.response.start')
            self.assertEqual(response.asgi_send_dict['status'], 200)

            # Verify headers
            headers = response.asgi_send_dict['headers']
            self.assertEqual(len(headers), 1)
            self.assertEqual(headers[0][0], b'content-type')
            # Text file should have charset
            self.assertIn(b'charset=UTF-8', headers[0][1])

            # Verify body contains file content
            self.assertIsInstance(response.leaf_object, str)
            self.assertIn('mumulib', response.leaf_object)

    def test_produce_text_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_text_file())

    async def async_test_produce_file_content_type(self):
        """Test that produce_file sets correct content-type"""
        # Use a Python file which should be detected as text/x-python
        test_file_path = '__init__.py'

        with open(test_file_path, 'r') as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            response = chunks[0]
            headers = response.asgi_send_dict['headers']
            content_type = headers[0][1]

            # Should detect Python file type
            self.assertIn(b'text/x-python', content_type)

    def test_produce_file_content_type(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_file_content_type())

    async def async_test_produce_file_with_unknown_type(self):
        """Test produce_file with file that has unknown content type"""
        # Use a file without clear extension
        test_file_path = '../../python/mumulib.egg-info/dependency_links.txt'

        with open(test_file_path, 'r') as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            response = chunks[0]
            headers = response.asgi_send_dict['headers']
            content_type = headers[0][1]

            # Should have some content type (either detected or default)
            self.assertIsNotNone(content_type)
            # Should have charset for text file
            self.assertIn(b'charset=UTF-8', content_type)

    def test_produce_file_with_unknown_type(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_file_with_unknown_type())

    async def async_test_produce_ttf_file(self):
        """Test producing a TTF font file (binary)"""
        # Use an actual TTF file - open in binary mode to get BufferedReader
        test_file_path = 'test_fixtures/Lexington-Gothic.ttf'

        with open(test_file_path, 'rb') as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            # Should return exactly one SpecialResponse
            self.assertEqual(len(chunks), 1)

            response = chunks[0]
            self.assertIsInstance(response, mumutypes.SpecialResponse)

            # Verify ASGI dict structure
            self.assertEqual(response.asgi_send_dict['type'], 'http.response.start')
            self.assertEqual(response.asgi_send_dict['status'], 200)

            # Verify headers
            headers = response.asgi_send_dict['headers']
            self.assertEqual(len(headers), 1)
            self.assertEqual(headers[0][0], b'content-type')

            # TTF file should be detected as font/ttf and should NOT have charset
            content_type = headers[0][1]
            self.assertIn(b'font/ttf', content_type)
            self.assertNotIn(b'charset', content_type)

            # Verify body is bytes (binary content)
            self.assertIsInstance(response.leaf_object, bytes)
            # TTF files start with specific magic bytes
            self.assertTrue(len(response.leaf_object) > 0)

    def test_produce_ttf_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_ttf_file())


if __name__ == "__main__": # pragma: no cover
    unittest.main(exit=False) # pragma: no cover
    cov.stop() # pragma: no cover
    cov.save() # pragma: no cover

    # Print coverage report to the terminal
    cov.report(show_missing=True) # pragma: no cover
