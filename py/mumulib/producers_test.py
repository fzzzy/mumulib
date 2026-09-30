# pyright: standard
import asyncio
import unittest
from pathlib import Path
from types import MappingProxyType

from mumulib import mumutypes
from mumulib.producers import (
    add_producer,
    custom_serializer,
    produce,
    produce_file,
    produce_json,
)

HERE = Path(__file__).parent


class TestCustomSerializer(unittest.TestCase):
    """Test custom_serializer function"""

    def test_mapping_proxy_type(self):
        """Test serialization of MappingProxyType"""
        original = {"key": "value", "number": 42}
        proxy = MappingProxyType(original)

        result = custom_serializer(proxy)

        self.assertEqual(result, original)
        self.assertIsInstance(result, dict)

    def test_anything_else_is_an_error_not_a_quiet_null(self):
        """What has no JSON form is refused, naming what it is"""

        class Thing:
            pass

        for thing in (Thing(), object(), {1, 2}):
            with self.subTest(thing=type(thing).__name__):
                with self.assertRaisesRegex(TypeError, type(thing).__name__):
                    custom_serializer(thing)


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
        self.assertIn("*/*", _producer_adapters)
        self.assertIn(CustomType, _producer_adapters["*/*"])
        self.assertEqual(_producer_adapters["*/*"][CustomType], test_producer)

        # Now actually use it by calling produce
        obj = CustomType()
        state = {"accept": ["*/*"]}
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify the producer was called and produced output
        self.assertEqual(chunks, ["test"])

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

        add_producer(CustomType, xml_producer, "application/xml")

        # Verify it was added to custom mime type
        self.assertIn("application/xml", _producer_adapters)
        self.assertIn(CustomType, _producer_adapters["application/xml"])
        self.assertEqual(
            _producer_adapters["application/xml"][CustomType], xml_producer
        )

        # Now actually use it by calling produce with XML accept header
        obj = CustomType()
        state = {"accept": ["application/xml"]}
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify the XML producer was called and produced output
        self.assertEqual(chunks, ["<xml/>"])

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
        add_producer(CustomType, custom_producer, "text/custom")

        # Create test object and state
        obj = CustomType("test-data")
        state = {"accept": ["text/custom", "application/json"]}

        # Call produce and collect output
        chunks = []
        async for chunk in produce(obj, state):
            chunks.append(chunk)

        # Verify custom producer was used
        self.assertEqual(chunks, ["CUSTOM:test-data"])

    def test_adapter_mechanism(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_adapter_mechanism())

    async def async_test_adapter_fallback(self):
        """With no producer for it, a thing is not found"""

        # Create a custom type without registering a producer
        class UnregisteredType:
            def __str__(self):
                return "unregistered-string"

        obj = UnregisteredType()
        state = {"accept": ["text/custom", "application/xml"]}

        # Nothing to make of it: not found, and never its str()
        with self.assertRaises(mumutypes.NotFoundResponse):
            async for _ in produce(obj, state):
                pass

    def test_adapter_fallback(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_adapter_fallback())

    async def async_test_json_adapter(self):
        """Test that JSON producer is used when accept includes application/json"""
        # Test with dict (registered for JSON)
        obj = {"key": "value", "number": 42}
        state = {"accept": ["application/json"]}

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
    """A function is called with the request, whatever kind it is."""

    def produced(self, thing, state=None):
        state = {"accept": ["text/plain", "*/*"]} if state is None else state

        async def collect():
            return [chunk async for chunk in produce(thing, state)]

        return asyncio.run(collect())

    def test_it_is_called_with_the_request_alone(self):
        received = []

        async def f(state):
            received.append(state)
            yield "output"

        state = {"accept": ["text/plain", "*/*"]}
        self.assertEqual(self.produced(f, state), ["output"])
        self.assertEqual(received, [state])

    def test_every_kind_of_function_answers(self):
        async def async_generator(state):
            yield "one,"
            yield "two"

        async def coroutine(state):
            return "from a coroutine"

        def generator(state):
            yield "a,"
            yield "b"

        def plain(state):
            return "from a function"

        for function, expected in [
            (async_generator, ["one,", "two"]),
            (coroutine, ["from a coroutine"]),
            (generator, ["a,", "b"]),
            (plain, ["from a function"]),
            (lambda state: "from a lambda", ["from a lambda"]),
        ]:
            with self.subTest(function=function.__name__):
                self.assertEqual(self.produced(function), expected)

    def test_what_it_returns_is_produced_as_if_published(self):
        def data(state):
            return {"a": 1}

        state = {"accept": ["application/json", "*/*"]}
        self.assertEqual(self.produced(data, state), ['{"a": 1}'])

    def test_a_method_is_not_found(self):
        class Thing:
            def method(self):
                return "never called"

        for method in (Thing().method, "abc".upper, "abc".__str__):
            with self.subTest(method=method):
                with self.assertRaises(mumutypes.NotFoundResponse):
                    self.produced(method)


class TestProduceJson(unittest.TestCase):
    """Test produce_json function"""

    async def async_test_produce_json_dict(self):
        """Test JSON production with dict"""
        obj = {"key": "value", "number": 42}
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
        original = {"key": "value", "number": 42}
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
        test_file_path = HERE.parent / "README.md"

        with open(test_file_path) as file_obj:
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
            self.assertEqual(response.asgi_send_dict["type"], "http.response.start")
            self.assertEqual(response.asgi_send_dict["status"], 200)

            # Verify headers
            headers = response.asgi_send_dict["headers"]
            self.assertEqual(len(headers), 1)
            self.assertEqual(headers[0][0], b"content-type")
            # Text file should have charset
            self.assertIn(b"charset=UTF-8", headers[0][1])

            # The file's bytes, undecoded
            self.assertIsInstance(response.leaf_object, bytes)
            self.assertIn(b"mumulib", response.leaf_object)

    def test_produce_text_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_text_file())

    async def async_test_produce_file_content_type(self):
        """Test that produce_file sets correct content-type"""
        # Use a Python file which should be detected as text/x-python
        test_file_path = HERE / "__init__.py"

        with open(test_file_path) as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            response = chunks[0]
            headers = response.asgi_send_dict["headers"]
            content_type = headers[0][1]

            # Should detect Python file type
            self.assertIn(b"text/x-python", content_type)

    def test_produce_file_content_type(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_file_content_type())

    async def async_test_produce_file_with_unknown_type(self):
        """Test produce_file with file that has unknown content type"""
        # Use a file without an extension, so mimetypes cannot guess it
        test_file_path = HERE.parent / "LICENSE"

        with open(test_file_path) as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            response = chunks[0]
            headers = response.asgi_send_dict["headers"]
            content_type = headers[0][1]

            # Should have some content type (either detected or default)
            self.assertIsNotNone(content_type)
            # Should have charset for text file
            self.assertEqual(content_type, b"application/octet-stream")

    def test_produce_file_with_unknown_type(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_file_with_unknown_type())

    async def async_test_produce_ttf_file(self):
        """Test producing a TTF font file (binary)"""
        # Use an actual TTF file - open in binary mode to get BufferedReader
        test_file_path = HERE / "test_fixtures" / "Lexington-Gothic.ttf"

        with open(test_file_path, "rb") as file_obj:
            state = {}

            chunks = []
            async for chunk in produce_file(file_obj, state):
                chunks.append(chunk)

            # Should return exactly one SpecialResponse
            self.assertEqual(len(chunks), 1)

            response = chunks[0]
            self.assertIsInstance(response, mumutypes.SpecialResponse)

            # Verify ASGI dict structure
            self.assertEqual(response.asgi_send_dict["type"], "http.response.start")
            self.assertEqual(response.asgi_send_dict["status"], 200)

            # Verify headers
            headers = response.asgi_send_dict["headers"]
            self.assertEqual(len(headers), 1)
            self.assertEqual(headers[0][0], b"content-type")

            # TTF file should be detected as font/ttf and should NOT have charset
            content_type = headers[0][1]
            self.assertIn(b"font/ttf", content_type)
            self.assertNotIn(b"charset", content_type)

            # Verify body is bytes (binary content)
            self.assertIsInstance(response.leaf_object, bytes)
            # TTF files start with specific magic bytes
            self.assertTrue(len(response.leaf_object) > 0)

    def test_produce_ttf_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_produce_ttf_file())


class TestFilesOverHttp(unittest.TestCase):
    """Files served by consumers_app arrive as their exact bytes."""

    def serve(self, root, path):
        from mumulib.server import consumers_app

        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {"type": "http", "method": "GET", "path": path, "headers": []}

        async def request():
            await consumers_app(root)({**scope, "state": {}}, receive, send)

        asyncio.run(request())
        body = b"".join(m.get("body", b"") for m in sent[1:])
        return sent[0]["status"], dict(sent[0]["headers"]), body

    def test_a_binary_file_arrives_byte_for_byte(self):
        path = HERE / "test_fixtures" / "pixel.png"
        with open(path, "rb") as file:
            status, headers, body = self.serve({"pixel": file}, "/pixel.png")
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"image/png")
        self.assertTrue(body.startswith(path.read_bytes()))

    def test_a_file_opened_as_text_is_still_sent_as_its_bytes(self):
        path = HERE / "test_fixtures" / "pixel.png"
        with open(path) as file:
            _, _, body = self.serve({"pixel": file}, "/pixel.png")
        self.assertTrue(body.startswith(path.read_bytes()))

    def test_the_url_names_a_files_type(self):
        path = HERE.parent / "README.md"
        with open(path) as file:
            _, headers, body = self.serve({"readme": file}, "/readme.txt")
        self.assertEqual(headers[b"content-type"], b"text/plain; charset=UTF-8")
        self.assertTrue(body.startswith(path.read_bytes()))
