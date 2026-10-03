# pyright: standard
import asyncio
import json
import os
import signal
import threading
import unittest
from pathlib import Path
from types import MappingProxyType
from unittest import mock

from mumulib.mumutypes import SpecialResponse, Upload
from mumulib.resource import Resource
from mumulib.server import (
    DEFAULT_MAX_BODY_SIZE,
    BodyTooLarge,
    EventSource,
    _close_streams_on_signal,
    consumers_app,
    parse_json,
    parse_multipart,
    parse_urlencoded,
)
from mumulib.tags import Markup


class TestParseJson(unittest.TestCase):
    """Test parse_json function"""

    async def async_test_parse_json_basic(self):
        """Test parsing basic JSON body"""
        json_data = {"key": "value", "number": 42}
        body_bytes = json.dumps(json_data).encode("utf-8")

        # Mock receive callable that returns the body
        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        result = await parse_json(receive)
        self.assertEqual(result, json_data)

    def test_parse_json_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_basic())

    async def async_test_parse_json_empty_body(self):
        """Test parsing empty JSON body"""

        # Mock receive callable that returns empty body
        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        result = await parse_json(receive)
        self.assertIsNone(result)

    def test_parse_json_empty_body(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_empty_body())

    async def async_test_parse_json_chunked(self):
        """Test parsing JSON body sent in chunks"""
        json_data = {"key": "value", "number": 42}
        body_bytes = json.dumps(json_data).encode("utf-8")

        # Split into chunks
        chunk1 = body_bytes[:10]
        chunk2 = body_bytes[10:]

        # Mock receive that returns chunks
        chunks = [
            {"type": "http.request", "body": chunk1, "more_body": True},
            {"type": "http.request", "body": chunk2, "more_body": False},
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
        large_body = b"x" * (DEFAULT_MAX_BODY_SIZE + 1)

        async def receive():
            return {"type": "http.request", "body": large_body, "more_body": False}

        with self.assertRaises(BodyTooLarge) as context:
            await parse_json(receive, max_size=DEFAULT_MAX_BODY_SIZE)

        self.assertIn("Request body too large", str(context.exception))

    def test_parse_json_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_json_size_limit_exceeded())


class TestParseUrlencoded(unittest.TestCase):
    """Test parse_urlencoded function"""

    async def async_test_parse_urlencoded_basic(self):
        """Test parsing basic URL-encoded body"""
        body_bytes = b"key=value&number=42&name=John%20Doe"

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        result = await parse_urlencoded(receive)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["number"], "42")
        self.assertEqual(result["name"], "John Doe")

    def test_parse_urlencoded_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_basic())

    async def async_test_parse_urlencoded_array_syntax(self):
        """Test parsing URL-encoded arrays with key[] syntax"""
        body_bytes = b"items[]=apple&items[]=banana&items[]=cherry"

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        result = await parse_urlencoded(receive)
        self.assertIn("items[]", result)
        self.assertEqual(result["items[]"], ["apple", "banana", "cherry"])

    def test_parse_urlencoded_array_syntax(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_array_syntax())

    def test_each_value_is_decoded_once(self):
        # %2541 is a literal %41, which decoding twice made an A
        body_bytes = b"text=100%25+off+%2541&item%5B%5D=a%26b"

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        result = asyncio.run(parse_urlencoded(receive))
        self.assertEqual(result, {"text": "100% off %41", "item[]": ["a&b"]})

    async def async_test_parse_urlencoded_empty_body(self):
        """Test parsing empty URL-encoded body"""

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        result = await parse_urlencoded(receive)
        self.assertEqual(result, {})

    def test_parse_urlencoded_empty_body(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_empty_body())

    async def async_test_parse_urlencoded_chunked(self):
        """Test parsing URL-encoded body sent in chunks"""
        body_bytes = b"key=value&number=42"
        chunk1 = body_bytes[:8]
        chunk2 = body_bytes[8:]

        chunks = [
            {"type": "http.request", "body": chunk1, "more_body": True},
            {"type": "http.request", "body": chunk2, "more_body": False},
        ]
        chunk_iter = iter(chunks)

        async def receive():
            return next(chunk_iter)

        result = await parse_urlencoded(receive)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["number"], "42")

    def test_parse_urlencoded_chunked(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_chunked())

    async def async_test_parse_urlencoded_size_limit(self):
        """Test that parse_urlencoded raises error when body exceeds size limit"""
        large_body = b"x" * (DEFAULT_MAX_BODY_SIZE + 1)

        async def receive():
            return {"type": "http.request", "body": large_body, "more_body": False}

        with self.assertRaises(BodyTooLarge) as context:
            await parse_urlencoded(receive, max_size=DEFAULT_MAX_BODY_SIZE)

        self.assertIn("Request body too large", str(context.exception))

    def test_parse_urlencoded_size_limit(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_urlencoded_size_limit())


class TestConsumersAppLifespan(unittest.TestCase):
    """Test ASGI lifespan handling"""

    async def async_test_lifespan_startup_shutdown(self):
        """Test lifespan startup and shutdown messages"""
        root = {"data": "test"}
        app = consumers_app(root)

        # Track what was sent
        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        # Simulate lifespan startup
        startup_message = {"type": "lifespan.startup"}
        shutdown_message = {"type": "lifespan.shutdown"}

        messages = [startup_message, shutdown_message]
        message_iter = iter(messages)

        async def receive():
            return next(message_iter)

        scope = {"type": "lifespan"}

        # Run the app with lifespan scope
        await app(scope, receive, send)

        # Verify startup complete was sent
        self.assertEqual(sent_messages[0], {"type": "lifespan.startup.complete"})
        # Verify shutdown complete was sent
        self.assertEqual(sent_messages[1], {"type": "lifespan.shutdown.complete"})

    def test_lifespan_startup_shutdown(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_lifespan_startup_shutdown())


class TestConsumersAppRouting(unittest.TestCase):
    """Test content-type routing based on path extensions"""

    async def async_test_request_content_type_does_not_choose_the_response(self):
        """A JSON request body is parsed, but the URL alone sets the reply's type"""
        root = {"data": Markup("success")}
        app = consumers_app(root)

        json_body = json.dumps({"key": "value"})

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                "type": "http.request",
                "body": json_body.encode("utf-8"),
                "more_body": False,
            }

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/data.html",
            "headers": [(b"content-type", b"application/json")],
            "state": {},
        }

        await app(scope, receive, send)

        # A JSON body is read as JSON, but the URL said .html, and that is
        # the response's type
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        headers = dict(response_start["headers"])
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")

    def test_request_content_type_does_not_choose_the_response(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_request_content_type_does_not_choose_the_response())

    async def async_test_json_path_extension(self):
        """Test that .json paths set JSON accept headers"""
        root = {"message": "hello"}
        app = consumers_app(root)

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/message.json",
            "headers": [],
            "state": {},
        }

        await app(scope, receive, send)

        # Check that response has JSON content-type
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        headers = dict(response_start["headers"])
        self.assertIn(b"application/json", headers[b"content-type"])

    def test_json_path_extension(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_path_extension())

    async def async_test_html_path_extension(self):
        """Test that .html paths set HTML accept headers"""
        root = {"message": Markup("hello")}
        app = consumers_app(root)

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/message.html",
            "headers": [],
            "state": {},
        }

        await app(scope, receive, send)

        # Check that response has HTML content-type
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        headers = dict(response_start["headers"])
        self.assertIn(b"text/html", headers[b"content-type"])

    def test_html_path_extension(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_html_path_extension())


class TestParseMultipart(unittest.TestCase):
    """Test parse_multipart function"""

    async def async_test_parse_multipart_basic(self):
        """Test parsing basic multipart form data"""
        boundary = b"----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field1"\r\n'
            b"\r\n"
            b"value1\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field2"\r\n'
            b"\r\n"
            b"value2\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW--"
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        result = await parse_multipart(receive, boundary)
        self.assertEqual(result, {"field1": "value1", "field2": "value2"})

    def test_parse_multipart_basic(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_basic())

    async def async_test_parse_multipart_with_file(self):
        """Test parsing multipart with binary file content"""
        boundary = b"----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="file"; filename="test.bin"\r\n'
            b"Content-Type: application/octet-stream\r\n"
            b"\r\n"
            b"binary content\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW--"
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        result = await parse_multipart(receive, boundary)
        self.assertEqual(
            result,
            {
                "file": Upload(
                    filename="test.bin",
                    content_type="application/octet-stream",
                    data=b"binary content",
                )
            },
        )

    def test_parse_multipart_with_file(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_with_file())

    async def async_test_parse_multipart_multiple_chunks(self):
        """Test parsing multipart with multiple chunks (line 113->100)"""
        boundary = b"----WebKitFormBoundary7MA4YWxkTrZu0gW"
        # Split the multipart body into multiple chunks
        chunk1 = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field1"\r\n'
            b"\r\n"
            b"value1\r\n"
        )
        chunk2 = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field2"\r\n'
            b"\r\n"
            b"value2\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW--"
        )

        chunks = [chunk1, chunk2]
        chunk_index = {"current": 0}

        async def receive():
            idx = chunk_index["current"]
            chunk_index["current"] += 1
            if idx < len(chunks):
                return {
                    "type": "http.request",
                    "body": chunks[idx],
                    "more_body": idx < len(chunks) - 1,  # True for all but last chunk
                }
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        result = await parse_multipart(receive, boundary)
        self.assertEqual(result, {"field1": "value1", "field2": "value2"})

    def test_parse_multipart_multiple_chunks(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_multiple_chunks())

    async def async_test_parse_multipart_malformed_part(self):
        """Test parsing multipart with a part missing Content-Disposition"""
        boundary = b"----WebKitFormBoundary7MA4YWxkTrZu0gW"
        body = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field1"\r\n'
            b"\r\n"
            b"value1\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            # Malformed part - no Content-Disposition header at all
            b"Some-Other-Header: value\r\n"
            b"\r\n"
            b"ignored content\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="field2"\r\n'
            b"\r\n"
            b"value2\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW--"
        )

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        result = await parse_multipart(receive, boundary)
        # Should only contain the valid fields, malformed part is skipped
        self.assertEqual(result, {"field1": "value1", "field2": "value2"})

    def test_parse_multipart_malformed_part(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_parse_multipart_malformed_part())

    def parse(self, body, boundary=b"XyZ", chunk=None):
        """parse_multipart over body, in chunks of that size if given"""
        chunks = (
            [body]
            if chunk is None
            else [body[i : i + chunk] for i in range(0, len(body), chunk)]
        )

        async def receive():
            data = chunks.pop(0)
            return {"type": "http.request", "body": data, "more_body": bool(chunks)}

        return asyncio.run(parse_multipart(receive, boundary))

    def test_name_is_the_name_parameter_wherever_it_is(self):
        """filename first is still filed under name"""
        body = (
            b"--XyZ\r\n"
            b'Content-Disposition: form-data; filename="a.png"; name="photo"\r\n'
            b"Content-Type: image/png\r\n"
            b"\r\n"
            b"\x89PNG\r\n"
            b"--XyZ--\r\n"
        )
        self.assertEqual(
            self.parse(body),
            {
                "photo": Upload(
                    filename="a.png", content_type="image/png", data=b"\x89PNG"
                )
            },
        )

    def test_bytes_are_kept_exactly(self):
        """Trailing dashes and newlines, a lookalike boundary, and every
        byte value, chunked across a boundary or not"""
        data = bytes(range(256)) + b"--XyZ-not-it\r\n--\r\n\r\n--"
        body = (
            b"--XyZ\r\n"
            b'Content-Disposition: form-data; name="f"; filename="raw.bin"\r\n'
            b"\r\n" + data + b"\r\n--XyZ--\r\n"
        )
        for chunk in (None, 1, 7):
            with self.subTest(chunk=chunk):
                self.assertEqual(
                    self.parse(body, chunk=chunk),
                    {"f": Upload(filename="raw.bin", content_type=None, data=data)},
                )

    def test_filename_with_a_semicolon_and_non_ascii(self):
        body = (
            "--XyZ\r\n"
            'Content-Disposition: form-data; name="f"; filename="a;b €.txt"\r\n'
            "\r\n"
            "x\r\n"
            "--XyZ--\r\n"
        ).encode()
        self.assertEqual(self.parse(body)["f"].filename, "a;b €.txt")

    def test_an_empty_file_is_still_an_upload(self):
        body = (
            b"--XyZ\r\n"
            b'Content-Disposition: form-data; name="f"; filename=""\r\n'
            b"Content-Type: application/octet-stream\r\n"
            b"\r\n"
            b"\r\n"
            b"--XyZ--\r\n"
        )
        self.assertEqual(
            self.parse(body),
            {
                "f": Upload(
                    filename="", content_type="application/octet-stream", data=b""
                )
            },
        )

    def test_repeated_bracketed_names_are_a_list(self):
        body = (
            b"--XyZ\r\n"
            b'Content-Disposition: form-data; name="tag[]"\r\n\r\na\r\n'
            b"--XyZ\r\n"
            b'Content-Disposition: form-data; name="tag[]"\r\n\r\nb\r\n'
            b"--XyZ--\r\n"
        )
        self.assertEqual(self.parse(body), {"tag[]": ["a", "b"]})

    def test_a_body_with_no_closing_boundary_is_an_error(self):
        body = b'--XyZ\r\nContent-Disposition: form-data; name="a"\r\n\r\nabc'
        with self.assertRaises(ValueError):
            self.parse(body)


class TestBytesResultHandling(unittest.TestCase):
    """Test handling of bytes results"""

    async def async_test_bytes_result(self):
        """Test that routes returning bytes are handled correctly"""
        root = {"binary": b"binary data here"}
        app = consumers_app(root)

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/binary.bin",
            "headers": [],
            "state": {},
        }

        await app(scope, receive, send)

        # Check that we got a response
        self.assertGreater(len(sent_messages), 1)

        # The first message should be http.response.start
        self.assertEqual(sent_messages[0]["type"], "http.response.start")

        # The bytes result should be in one of the body messages
        body_messages = [
            msg for msg in sent_messages if msg["type"] == "http.response.body"
        ]
        self.assertGreater(len(body_messages), 0)

        # Find the message with our binary data
        found = any(b"binary data here" in msg["body"] for msg in body_messages)
        self.assertTrue(
            found, f"Binary data not found in body messages: {body_messages}"
        )

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
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/anything.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should get 500 Internal Server Error
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 500)

            # Check error message
            response_body = sent_messages[1]
            body_data = json.loads(response_body["body"].decode("utf-8"))
            self.assertEqual(body_data["error"], "Internal Server Error")
            self.assertIn("Intentional error", body_data["message"])
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
            return HTTPResponse(201, "Custom response body")

        add_consumer(CustomResponseObject, custom_consumer)

        try:
            root = CustomResponseObject()
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should get the custom response
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 201)

            # Check body
            response_body = sent_messages[1]
            self.assertEqual(response_body["type"], "http.response.body")
            self.assertIn(b"Custom response body", response_body["body"])
        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters

            if CustomResponseObject in _consumer_adapters:
                del _consumer_adapters[CustomResponseObject]

    def test_special_response_result(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_result())

    async def async_test_special_response_with_non_string_leaf(self):
        """Test that a SpecialResponse with a non-str, non-bytes leaf is handled"""
        from mumulib.mumutypes import SpecialResponse

        # Create a custom object that returns a SpecialResponse with dict leaf_object
        class DictResponseObject:
            pass

        from mumulib.consumers import add_consumer

        async def dict_consumer(parent, segments, state, send):
            # Return a SpecialResponse with a dict as leaf_object
            return SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                },
                {"status": "ok", "count": 42},  # dict leaf_object
            )

        add_consumer(DictResponseObject, dict_consumer)

        try:
            root = DictResponseObject()
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should get the custom response
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 200)

            # Check body - dict should be converted to string
            response_body = sent_messages[1]
            self.assertEqual(response_body["type"], "http.response.body")
            # The dict gets str() applied, which gives something like
            # "{'status': 'ok', 'count': 42}"
            self.assertIn(b"status", response_body["body"])
            self.assertIn(b"ok", response_body["body"])
        finally:
            # Clean up
            from mumulib.consumers import _consumer_adapters

            if DictResponseObject in _consumer_adapters:
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
                raise HTTPResponse(403, "Forbidden by producer")
                yield

        add_producer(ProducerObject, lambda obj, state: obj, "*/*")

        try:
            root = {"test": ProducerObject()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should get the special response
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 403)

            # Check body contains the leaf object
            response_body = sent_messages[1]
            self.assertIn(b"Forbidden by producer", response_body["body"])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if (
                "*/*" in _producer_adapters
                and ProducerObject in _producer_adapters["*/*"]
            ):
                del _producer_adapters["*/*"][ProducerObject]

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
                yield

        add_producer(BrokenProducer, lambda obj, state: obj, "*/*")

        try:
            root = {"test": BrokenProducer()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should get 500 error
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 500)

            # Check error message
            response_body = sent_messages[1]
            body_data = json.loads(response_body["body"].decode("utf-8"))
            self.assertEqual(body_data["error"], "Internal Server Error")
            self.assertIn("Producer error", body_data["message"])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if (
                "*/*" in _producer_adapters
                and BrokenProducer in _producer_adapters["*/*"]
            ):
                del _producer_adapters["*/*"][BrokenProducer]

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
            yield "First chunk"
            # After first chunk is sent, raise SpecialResponse
            raise HTTPResponse(403, "Delayed forbidden")

        add_producer(
            DelayedSpecialResponseProducer, produce_then_special_response, "*/*"
        )

        try:
            root = {"test": DelayedSpecialResponseProducer()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should have sent the first chunk normally
            self.assertEqual(sent_messages[0]["type"], "http.response.start")
            self.assertEqual(sent_messages[1]["body"], b"First chunk")

            # Final body should contain the SpecialResponse leaf_object
            final_body = sent_messages[-1]
            self.assertEqual(final_body["type"], "http.response.body")
            self.assertIn(b"Delayed forbidden", final_body["body"])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if "*/*" in _producer_adapters:
                if DelayedSpecialResponseProducer in _producer_adapters["*/*"]:
                    del _producer_adapters["*/*"][DelayedSpecialResponseProducer]

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
            yield "First chunk"
            # After first chunk is sent, raise a generic exception
            raise RuntimeError("Delayed error")

        add_producer(DelayedExceptionProducer, produce_then_error, "*/*")

        try:
            root = {"test": DelayedExceptionProducer()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.json",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Should have sent the first chunk normally
            self.assertEqual(sent_messages[0]["type"], "http.response.start")
            self.assertEqual(sent_messages[1]["body"], b"First chunk")

            # Final body should contain the error as JSON
            final_body = sent_messages[-1]
            self.assertEqual(final_body["type"], "http.response.body")
            body_data = json.loads(final_body["body"].decode("utf-8"))
            self.assertEqual(body_data["error"], "Internal Server Error")
            self.assertIn("Delayed error", body_data["message"])
        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if "*/*" in _producer_adapters:
                if DelayedExceptionProducer in _producer_adapters["*/*"]:
                    del _producer_adapters["*/*"][DelayedExceptionProducer]

    def test_generic_exception_after_first_chunk(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_generic_exception_after_first_chunk())


class TestSpecialResponseWithWriter(unittest.TestCase):
    """Test handling of SpecialResponse with writer callback in produce"""

    async def async_test_special_response_with_writer(self):
        """Test that SpecialResponse with writer callback is handled correctly"""
        from mumulib.mumutypes import SpecialResponse
        from mumulib.producers import add_producer

        # Track writer execution
        writer_called = {"value": False}

        async def test_writer(send, receive):
            """A writer that sends additional data"""
            writer_called["value"] = True
            await send(
                {
                    "type": "http.response.body",
                    "body": b"Additional data from writer",
                    "more_body": False,
                }
            )

        class WriterProducerObject:
            """Object with a producer that yields SpecialResponse with writer"""

            pass

        async def produce_with_writer(thing, state):
            """Producer that yields a SpecialResponse with a writer, then more chunks"""
            yield SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                },
                "Initial response",  # leaf_object as string (will be encoded)
                test_writer,
            )
            # Yield a second chunk to cover the else clause for additional chunks
            yield "Second chunk from producer"

        try:
            # Register the producer (type, producer_func, mimetype)
            add_producer(WriterProducerObject, produce_with_writer, "*/*")

            root = {"test": WriterProducerObject()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.txt",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Verify the response includes the special response headers
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 200)
            self.assertEqual(
                response_start["headers"],
                [(b"content-type", b"text/plain; charset=UTF-8")],
            )

            # Verify the initial body was sent (from SpecialResponse leaf_object)
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1["type"], "http.response.body")
            self.assertEqual(response_body_1["body"], b"Initial response")
            self.assertTrue(response_body_1["more_body"])

            # Verify the writer was called and sent additional data
            self.assertTrue(writer_called["value"])
            response_body_2 = sent_messages[2]
            self.assertEqual(response_body_2["type"], "http.response.body")
            self.assertEqual(response_body_2["body"], b"Additional data from writer")
            # Note: more_body should be False from the writer
            self.assertFalse(response_body_2["more_body"])

            # Verify the second chunk from producer was sent (covers lines 229-230)
            response_body_3 = sent_messages[3]
            self.assertEqual(response_body_3["type"], "http.response.body")
            self.assertEqual(response_body_3["body"], b"Second chunk from producer")
            self.assertTrue(response_body_3["more_body"])

            # Final newline chunk
            response_body_4 = sent_messages[4]
            self.assertEqual(response_body_4["type"], "http.response.body")
            self.assertEqual(response_body_4["body"], b"\n")
            self.assertFalse(response_body_4["more_body"])

        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if (
                "*/*" in _producer_adapters
                and WriterProducerObject in _producer_adapters["*/*"]
            ):
                del _producer_adapters["*/*"][WriterProducerObject]

    def test_special_response_with_writer(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_with_writer())

    async def async_test_special_response_without_writer(self):
        """Test that SpecialResponse without writer callback is handled correctly"""
        from mumulib.mumutypes import SpecialResponse
        from mumulib.producers import add_producer

        class NoWriterProducerObject:
            """Object with a producer that yields SpecialResponse without writer"""

            pass

        async def produce_without_writer(thing, state):
            """Producer that yields a SpecialResponse without writer callback"""
            yield SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain")],
                },
                "Response without writer",
            )
            # No writer parameter, so chunk.writer will be None

        try:
            # Register the producer (type, producer_func, mimetype)
            add_producer(NoWriterProducerObject, produce_without_writer, "*/*")

            root = {"test": NoWriterProducerObject()}
            app = consumers_app(root)

            sent_messages = []

            async def send(message):
                sent_messages.append(message)

            async def receive():
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            scope = {
                "type": "http",
                "method": "GET",
                "path": "/test.txt",
                "headers": [],
                "state": {},
            }

            await app(scope, receive, send)

            # Verify the response includes the special response headers
            response_start = sent_messages[0]
            self.assertEqual(response_start["type"], "http.response.start")
            self.assertEqual(response_start["status"], 200)
            self.assertEqual(
                response_start["headers"],
                [(b"content-type", b"text/plain; charset=UTF-8")],
            )

            # Verify the body was sent
            response_body_1 = sent_messages[1]
            self.assertEqual(response_body_1["type"], "http.response.body")
            self.assertEqual(response_body_1["body"], b"Response without writer")
            self.assertTrue(response_body_1["more_body"])

            # Final newline chunk
            response_body_2 = sent_messages[2]
            self.assertEqual(response_body_2["type"], "http.response.body")
            self.assertEqual(response_body_2["body"], b"\n")
            self.assertFalse(response_body_2["more_body"])

        finally:
            # Clean up
            from mumulib.producers import _producer_adapters

            if (
                "*/*" in _producer_adapters
                and NoWriterProducerObject in _producer_adapters["*/*"]
            ):
                del _producer_adapters["*/*"][NoWriterProducerObject]

    def test_special_response_without_writer(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_special_response_without_writer())


class TestUnreadableBodies(unittest.TestCase):
    """A body that cannot be read is the client's fault, and not a 413"""

    def request(self, method, content_type, body):
        """The status and error type of one request to a small app"""
        app = consumers_app({"data": "test"})
        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        scope = {
            "type": "http",
            "method": method,
            "path": "/data.json",
            "headers": [(b"content-type", content_type)],
            "state": {},
        }
        asyncio.run(app(scope, receive, send))
        status = sent_messages[0]["status"]
        if status < 400:
            return status, None
        return status, json.loads(sent_messages[1]["body"])["error"]

    def test_unknown_content_type_on_a_write_is_415(self):
        self.assertEqual(
            self.request("POST", b"application/x-custom-type", b"test data"),
            (415, "Unsupported Media Type"),
        )

    def test_unknown_content_type_on_a_read_is_ignored(self):
        status, _ = self.request("GET", b"application/x-custom-type", b"")
        self.assertEqual(status, 200)

    def test_malformed_json_is_400(self):
        self.assertEqual(
            self.request("POST", b"application/json", b"{not json"),
            (400, "Bad Request"),
        )

    def test_a_body_that_is_not_utf8_is_400(self):
        self.assertEqual(
            self.request("POST", b"application/json", b'"\xff"'),
            (400, "Bad Request"),
        )
        self.assertEqual(
            self.request("POST", b"application/x-www-form-urlencoded", b"a=\xff"),
            (400, "Bad Request"),
        )

    def test_a_quoted_boundary_is_read(self):
        status, _ = self.request(
            "POST",
            b'multipart/form-data; boundary="a b"',
            b"--a b\r\n"
            b'Content-Disposition: form-data; name="x"\r\n\r\n1\r\n'
            b"--a b--\r\n",
        )
        self.assertEqual(status, 200)

    def test_multipart_with_no_boundary_is_400(self):
        self.assertEqual(
            self.request("POST", b"multipart/form-data", b""),
            (400, "Bad Request"),
        )

    def test_malformed_multipart_is_400(self):
        boundary = b"multipart/form-data; boundary=XyZ"
        # No blank line between a part's headers and its content
        self.assertEqual(
            self.request(
                "POST", boundary, b"--XyZ\r\nContent-Disposition: x\r\n--XyZ--"
            ),
            (400, "Bad Request"),
        )


class TestRequestSizeLimits(unittest.TestCase):
    """Test request body size limit enforcement"""

    async def async_test_json_size_limit_exceeded(self):
        """Test that oversized JSON body triggers 413 error"""
        root = {"data": "test"}
        app = consumers_app(root)

        # Create a body that exceeds the default limit (10MB)
        oversized_body = json.dumps(
            {"data": "x" * (DEFAULT_MAX_BODY_SIZE + 1000)}
        ).encode("utf-8")

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {"type": "http.request", "body": oversized_body, "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/data.json",
            "headers": [(b"content-type", b"application/json")],
            "state": {},
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body["body"].decode("utf-8"))
        self.assertEqual(body_data["error"], "Payload Too Large")

    def test_json_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_json_size_limit_exceeded())

    async def async_test_urlencoded_size_limit_exceeded(self):
        """Test that oversized urlencoded body triggers 413 error"""
        root = {"data": "test"}
        app = consumers_app(root)

        # Create a body that exceeds the default limit (10MB)
        oversized_body = ("key=" + "x" * (DEFAULT_MAX_BODY_SIZE + 1000)).encode("utf-8")

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {"type": "http.request", "body": oversized_body, "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/data.json",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
            "state": {},
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body["body"].decode("utf-8"))
        self.assertEqual(body_data["error"], "Payload Too Large")

    def test_urlencoded_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_urlencoded_size_limit_exceeded())

    async def async_test_multipart_size_limit_exceeded(self):
        """Test that oversized multipart body triggers 413 error"""
        root = {"data": "test"}
        app = consumers_app(root)

        # Create a body that exceeds the default limit (10MB)
        oversized_content = b"x" * (DEFAULT_MAX_BODY_SIZE + 1000)
        oversized_body = (
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW\r\n"
            b'Content-Disposition: form-data; name="huge_field"\r\n'
            b"\r\n" + oversized_content + b"\r\n"
            b"------WebKitFormBoundary7MA4YWxkTrZu0gW--"
        )

        sent_messages = []

        async def send(message):
            sent_messages.append(message)

        async def receive():
            return {"type": "http.request", "body": oversized_body, "more_body": False}

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/data.json",
            "headers": [
                (
                    b"content-type",
                    b"multipart/form-data; "
                    b"boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW",
                )
            ],
            "state": {},
        }

        await app(scope, receive, send)

        # Should get 413 Payload Too Large error
        response_start = sent_messages[0]
        self.assertEqual(response_start["type"], "http.response.start")
        self.assertEqual(response_start["status"], 413)

        # Check error message
        response_body = sent_messages[1]
        body_data = json.loads(response_body["body"].decode("utf-8"))
        self.assertEqual(body_data["error"], "Payload Too Large")

    def test_multipart_size_limit_exceeded(self):
        """Wrapper to run async test"""
        asyncio.run(self.async_test_multipart_size_limit_exceeded())


async def get(root, path, method="GET"):
    """The response start and the whole body, for one request to root's app."""
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {"type": "http", "method": method, "path": path, "headers": []}
    await consumers_app(root)({**scope, "state": {}}, receive, send)
    start = sent[0]
    body = b"".join(m.get("body", b"") for m in sent[1:])
    return start["status"], dict(start["headers"]), body


class Client:
    """One client of an app's event stream: what it was sent, and a way to go."""

    def __init__(self, app, path="/events.sse", send_blocks=None):
        self.sent = []
        self.receives = 0
        self.leave = asyncio.Event()
        self.send_blocks = send_blocks

        async def receive():
            self.receives += 1
            if self.receives == 1:
                return {"type": "http.request", "body": b"", "more_body": False}
            await self.leave.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            # A stalled connection: the event's send waits until let through
            body = message.get("body", b"")
            if self.send_blocks is not None and body.startswith(b"data: "):
                await self.send_blocks.wait()
            self.sent.append(message)

        scope = {"type": "http", "method": "GET", "path": path, "headers": []}
        self.task = asyncio.ensure_future(app({**scope, "state": {}}, receive, send))

    @property
    def status(self):
        return self.sent[0]["status"]

    @property
    def body(self):
        return b"".join(m.get("body", b"") for m in self.sent[1:])

    async def go(self):
        self.leave.set()
        await self.task


async def settle():
    """Let every task that can run, run, until none can."""
    for _ in range(50):
        await asyncio.sleep(0)


class TestEventSource(unittest.IsolatedAsyncioTestCase):
    """Server-sent events: each item put goes to every stream open then."""

    def setUp(self):
        self.events = EventSource()
        self.app = consumers_app({"events": self.events})

    async def test_a_stream_starts_with_its_headers_and_a_ping(self):
        client = Client(self.app)
        await settle()
        self.assertEqual(client.status, 200)
        headers = dict(client.sent[0]["headers"])
        self.assertEqual(headers[b"content-type"], b"text/event-stream; charset=UTF-8")
        self.assertEqual(headers[b"cache-control"], b"no-cache")
        self.assertEqual(client.body, b"event: ping\ndata: {}\n\n")
        await client.go()

    async def test_every_listener_hears_every_event(self):
        first, second = Client(self.app), Client(self.app)
        await settle()
        self.assertEqual(self.events.listeners, 2)
        self.events.put("a")
        self.events.put("b")
        await settle()
        for client in (first, second):
            self.assertTrue(client.body.endswith(b'data: "a"\n\ndata: "b"\n\n'))
        await first.go()
        await second.go()

    async def test_a_client_hears_only_what_is_put_after_it_connects(self):
        self.events.put("before anyone")
        client = Client(self.app)
        await settle()
        self.events.put("after")
        await settle()
        self.assertNotIn(b"before anyone", client.body)
        self.assertIn(b'data: "after"', client.body)
        await client.go()

    async def test_each_item_is_its_json(self):
        client = Client(self.app)
        await settle()
        self.events.put({"text": "Milk", "done": False})
        self.events.put(MappingProxyType({"read": "only"}))
        self.events.put([1, None, True])
        await settle()
        lines = client.body.split(b"\n\n")[1:-1]
        self.assertEqual(
            [json.loads(line.removeprefix(b"data: ")) for line in lines],
            [{"text": "Milk", "done": False}, {"read": "only"}, [1, None, True]],
        )
        await client.go()

    async def test_a_string_with_newlines_is_still_one_event(self):
        client = Client(self.app)
        await settle()
        self.events.put("one\n\ntwo")
        await settle()
        self.assertTrue(client.body.endswith(b'data: "one\\n\\ntwo"\n\n'))
        await client.go()

    async def test_what_has_no_json_is_refused_where_it_is_put(self):
        client = Client(self.app)
        await settle()
        with self.assertRaises(TypeError):
            self.events.put(object())
        await settle()
        self.assertEqual(client.body, b"event: ping\ndata: {}\n\n")
        await client.go()

    async def test_a_client_that_goes_is_forgotten_and_its_response_ends(self):
        client = Client(self.app)
        await settle()
        await client.go()
        self.assertEqual(self.events.listeners, 0)
        self.assertFalse(client.sent[-1]["more_body"])
        # Putting with no one to hear is nothing
        self.events.put("to no one")

    async def test_one_receive_for_the_whole_stream(self):
        client = Client(self.app)
        await settle()
        for n in range(100):
            self.events.put(n)
            await settle()
        self.assertIn(b"data: 99\n\n", client.body)
        # The body's, then one waiting for the client to go: not one an event
        self.assertEqual(client.receives, 2)
        await client.go()

    async def test_a_client_too_far_behind_is_closed(self):
        self.events = EventSource(max_backlog=2)
        self.app = consumers_app({"events": self.events})
        stalled = asyncio.Event()
        slow, fine = Client(self.app, send_blocks=stalled), Client(self.app)
        await settle()
        # The slow one takes the first and stalls sending it; its buffer then
        # fills, and the next is one too many
        for n in range(4):
            self.events.put(n)
            await settle()
        self.assertEqual(self.events.listeners, 1)
        stalled.set()
        await slow.task
        self.assertFalse(slow.sent[-1]["more_body"])
        # The other heard everything
        self.assertIn(b"data: 3\n\n", fine.body)
        await fine.go()

    async def test_a_cancelled_stream_leaves_nothing_behind(self):
        # As the server shutting down cancels it
        client = Client(self.app)
        await settle()
        client.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await client.task
        self.assertEqual(self.events.listeners, 0)

    async def test_it_is_found_as_an_event_stream_and_nothing_else(self):
        for path in ("/events.json", "/events.txt", "/events.html"):
            with self.subTest(path=path):
                client = Client(self.app, path)
                await client.go()
                self.assertEqual(client.status, 404)
        self.assertEqual(self.events.listeners, 0)


class Lifespan:
    """An app's lifespan, as a server runs it: started, and later shut down."""

    def __init__(self, app):
        self.incoming = asyncio.Queue()
        self.sent = []

        async def send(message):
            self.sent.append(message)

        self.task = asyncio.ensure_future(
            app({"type": "lifespan"}, self.incoming.get, send)
        )

    async def start(self):
        await self.incoming.put({"type": "lifespan.startup"})
        await settle()

    async def shut_down(self):
        await self.incoming.put({"type": "lifespan.shutdown"})
        await self.task


async def write(app, method, path, body=None):
    """The status of one request to app, with body as JSON if given."""
    sent = []
    data = json.dumps(body).encode() if body is not None else b""

    async def receive():
        return {"type": "http.request", "body": data, "more_body": False}

    async def send(message):
        sent.append(message)

    headers = [(b"content-type", b"application/json")] if body is not None else []
    scope = {"type": "http", "method": method, "path": path, "headers": headers}
    await app({**scope, "state": {}}, receive, send)
    return sent[0]["status"]


class TestChanges(unittest.IsolatedAsyncioTestCase):
    """Given changes, each request that changed something puts its URL there."""

    def setUp(self):
        self.changes = EventSource()

        def greet(state):
            return {"hello": state.get("parsed_body")}

        def broken(state):
            raise RuntimeError("broken on purpose")

        self.root = {
            "index": "home",
            "todos": ["a"],
            "fixed": ("a",),
            "greet": greet,
            "broken": broken,
            "changes": self.changes,
            "sub": {},
        }
        self.app = consumers_app(self.root, changes=self.changes)

    async def heard(self, *requests):
        """The URLs a listener hears while requests are made."""
        listener = Client(self.app, "/changes.sse")
        await settle()
        statuses = [await write(self.app, *request) for request in requests]
        await settle()
        await listener.go()
        events = listener.body.split(b"\n\n")[1:-1]
        return statuses, [json.loads(e.removeprefix(b"data: ")) for e in events]

    async def test_a_write_with_no_container_above_it_puts_slash(self):
        statuses, urls = await self.heard(
            ("PUT", "/todos/0.json", "b"),
            ("PUT", "/todos/last.json", "c"),
            ("DELETE", "/todos/0.json"),
            ("PUT", "/", "new home"),
            ("POST", "/greet.json", "Ada"),
        )
        self.assertEqual(statuses, [204, 201, 204, 204, 200])
        self.assertEqual(urls, ["/", "/", "/", "/", "/"])

    async def test_a_write_puts_the_nearest_resource_at_or_above_it(self):
        class Inner(Resource):
            async def handle_PUT(self, request):
                return "put"

        class Shelf(Inner):
            child_books = ["a", "b"]
            child_inner = {"deeper": Inner()}

        self.root["shelf"] = Shelf()
        statuses, urls = await self.heard(
            # The resource's own, at its URL, whatever type it is written as
            ("PUT", "/shelf.json", "x"),
            ("PUT", "/shelf.txt", "x"),
            # Inside it, in a list of its own: the resource is what changed
            ("PUT", "/shelf/books/0.json", "c"),
            ("PUT", "/shelf/books/last.json", "d"),
            # And a resource inside it is nearer still
            ("PUT", "/shelf/inner/deeper.json", "x"),
        )
        self.assertEqual(statuses, [200, 200, 204, 201, 200])
        self.assertEqual(
            urls, ["/shelf", "/shelf", "/shelf", "/shelf", "/shelf/inner/deeper"]
        )

    async def test_a_303_is_a_form_posts_success_and_is_announced(self):
        class Form(Resource):
            async def handle_POST(self, request):
                self.see_other("/")

        self.root["form"] = Form()
        statuses, urls = await self.heard(("POST", "/form.html", "x"))
        self.assertEqual((statuses, urls), ([303], ["/form"]))

    async def test_the_app_serves_the_stream_and_live_js_under_mumulib(self):
        listener = Client(self.app, "/mumulib/changes.sse")
        await settle()
        await write(self.app, "PUT", "/todos/0.json", "b")
        await settle()
        await listener.go()
        self.assertIn(b'data: "/"', listener.body)
        status, headers, body = await get(self.root, "/mumulib/live.js")
        self.assertEqual(status, 404)  # get() builds an app without changes
        sent = []

        async def send(message):
            sent.append(message)

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        scope = {
            "type": "http",
            "method": "GET",
            "path": "/mumulib/live.js",
            "headers": [],
        }
        await self.app({**scope, "state": {}}, receive, send)
        self.assertEqual(sent[0]["status"], 200)
        self.assertIn(b"data-live", b"".join(m.get("body", b"") for m in sent[1:]))
        # Read-only, and nothing of root's is shadowed but its own mumulib
        self.assertEqual(await write(self.app, "PUT", "/mumulib/live.js", "x"), 405)

    async def test_what_changed_nothing_puts_nothing(self):
        statuses, urls = await self.heard(
            ("GET", "/todos/0.json"),
            ("DELETE", "/missing.json"),
            ("PUT", "/fixed/0.json", "x"),
            ("PUT", "/todos/9.json", "x"),
            ("POST", "/broken.json", "x"),
        )
        self.assertEqual(statuses, [200, 404, 405, 403, 500])
        self.assertEqual(urls, [])

    async def test_without_changes_nothing_is_put(self):
        app = consumers_app(self.root)
        listener = Client(app, "/changes.sse")
        await settle()
        self.assertEqual(await write(app, "PUT", "/todos/0.json", "b"), 204)
        await settle()
        await listener.go()
        # The ping, and no event after it
        self.assertEqual(listener.body.count(b"data: "), 1)


class TestStreamsEndOnSignal(unittest.IsolatedAsyncioTestCase):
    """SIGINT or SIGTERM ends every event stream, then reaches the server's
    own handler, so the server's wait for open responses ends at once."""

    def setUp(self):
        # Whatever these tests set, the process's own handlers come back
        for signum in (signal.SIGINT, signal.SIGTERM):
            self.addCleanup(signal.signal, signum, signal.getsignal(signum))
        self.heard = []
        # The server's handler, as uvicorn's is set before the app starts
        signal.signal(signal.SIGTERM, lambda signum, frame: self.heard.append(signum))
        self.events, self.others = EventSource(), EventSource()
        self.app = consumers_app({"events": self.events, "others": self.others})

    async def test_a_signal_ends_every_stream_then_reaches_the_server(self):
        lifespan = Lifespan(self.app)
        await lifespan.start()
        clients = [
            Client(self.app),
            Client(self.app),
            Client(self.app, "/others.sse"),
        ]
        await settle()
        self.assertEqual((self.events.listeners, self.others.listeners), (2, 1))
        os.kill(os.getpid(), signal.SIGTERM)
        for client in clients:
            await client.task
            self.assertFalse(client.sent[-1]["more_body"])
        self.assertEqual((self.events.listeners, self.others.listeners), (0, 0))
        self.assertEqual(self.heard, [signal.SIGTERM])
        await lifespan.shut_down()

    async def test_shutting_down_puts_the_servers_handler_back(self):
        server_handler = signal.getsignal(signal.SIGTERM)
        lifespan = Lifespan(self.app)
        await lifespan.start()
        self.assertIsNot(signal.getsignal(signal.SIGTERM), server_handler)
        await lifespan.shut_down()
        self.assertIs(signal.getsignal(signal.SIGTERM), server_handler)

    async def test_a_shutdown_with_no_startup_undoes_nothing(self):
        before = signal.getsignal(signal.SIGTERM)
        lifespan = Lifespan(self.app)
        await lifespan.shut_down()
        self.assertEqual(lifespan.sent, [{"type": "lifespan.shutdown.complete"}])
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    async def test_a_handler_set_since_is_left_alone(self):
        lifespan = Lifespan(self.app)
        await lifespan.start()
        later = lambda signum, frame: None  # noqa: E731
        signal.signal(signal.SIGTERM, later)
        await lifespan.shut_down()
        self.assertIs(signal.getsignal(signal.SIGTERM), later)

    async def test_an_ignored_signal_still_ends_the_streams(self):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        lifespan = Lifespan(self.app)
        await lifespan.start()
        client = Client(self.app)
        await settle()
        os.kill(os.getpid(), signal.SIGTERM)
        await client.task
        self.assertEqual(self.events.listeners, 0)
        await lifespan.shut_down()

    async def test_the_default_is_still_the_default(self):
        # SIG_DFL for SIGTERM ends the process; raise_signal is that, here
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        lifespan = Lifespan(self.app)
        await lifespan.start()
        with mock.patch("mumulib.server.signal.raise_signal") as raised:
            os.kill(os.getpid(), signal.SIGTERM)
            await settle()
        raised.assert_called_once_with(signal.SIGTERM)
        self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_DFL)
        await lifespan.shut_down()

    async def test_from_another_thread_nothing_is_chained(self):
        before = signal.getsignal(signal.SIGTERM)
        loop = asyncio.get_running_loop()
        restores = []
        thread = threading.Thread(
            target=lambda: restores.append(_close_streams_on_signal(loop))
        )
        thread.start()
        thread.join()
        self.assertIs(signal.getsignal(signal.SIGTERM), before)
        restores[0]()
        self.assertIs(signal.getsignal(signal.SIGTERM), before)


class TestUrlNamesTheType(unittest.TestCase):
    """The extension on a URL is the only thing that sets the reply's type."""

    def test_a_url_without_an_extension_is_not_found(self):
        status, _, body = asyncio.run(get({"todos": [1]}, "/todos"))
        self.assertEqual(status, 404)
        self.assertIn(b"extension", body)

    def test_an_extension_with_no_type_is_not_found(self):
        status, _, _ = asyncio.run(get({"todos": [1]}, "/todos.nosuchtype"))
        self.assertEqual(status, 404)

    def test_the_extension_is_the_representation_not_the_key(self):
        root = {"motto": "write it"}
        status, headers, body = asyncio.run(get(root, "/motto.json"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"application/json; charset=UTF-8")
        self.assertEqual(json.loads(body), "write it")
        status, headers, body = asyncio.run(get(root, "/motto.txt"))
        self.assertEqual((status, body.strip()), (200, b"write it"))
        self.assertEqual(headers[b"content-type"], b"text/plain; charset=UTF-8")
        # Text is never HTML: a string there could be anyone's markup
        self.assertEqual(asyncio.run(get(root, "/motto.html"))[0], 404)

    def test_a_container_has_one_url_per_type(self):
        root = {"todos": ["write it"]}
        # Its HTML is its slash, for people in browsers
        status, headers, _ = asyncio.run(get(root, "/todos/"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        # Any other type is its name, as a leaf's is
        status, _, body = asyncio.run(get(root, "/todos.json"))
        self.assertEqual((status, json.loads(body)), (200, ["write it"]))
        # And nothing else: not HTML by its name, and no index spelled out
        for path in (
            "/todos.html",
            "/todos/index.html",
            "/todos/index.htm",
            "/todos/index.json",
        ):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get(root, path))[0], 404)

    def test_the_index_entry_is_the_slash_and_only_the_slash(self):
        # A dict with a front page still has its data by name
        root = {"todos": {"index": Markup("<p>my todos</p>"), "a": 1}}
        _, _, body = asyncio.run(get(root, "/todos/"))
        self.assertEqual(body.strip(), b"<p>my todos</p>")
        _, _, body = asyncio.run(get(root, "/todos.json"))
        self.assertEqual(json.loads(body), {"index": "<p>my todos</p>", "a": 1})

    def test_the_root_has_its_slash_and_no_other_name(self):
        root = {"index": Markup("<p>home</p>")}
        self.assertEqual(asyncio.run(get(root, "/"))[0], 200)
        for path in ("/index.html", "/index.json", "/index.txt"):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get(root, path))[0], 404)

    def test_the_site_root_is_index_html(self):
        status, headers, body = asyncio.run(get({"index": Markup("<p>home</p>")}, "/"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        self.assertEqual(body.strip(), b"<p>home</p>")

    def test_a_trailing_slash_is_the_index_as_html(self):
        root = {"todos": {"index": Markup("<ul></ul>"), "a": 1}}
        status, headers, body = asyncio.run(get(root, "/todos/"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        self.assertEqual(body.strip(), b"<ul></ul>")

    def test_put_to_the_slash_writes_the_index_entry(self):
        root = {"index": "old"}

        async def put():
            sent = []

            async def send(message):
                sent.append(message)

            async def receive():
                return {"type": "http.request", "body": b'"new"', "more_body": False}

            scope = {
                "type": "http",
                "method": "PUT",
                "path": "/",
                "headers": [(b"content-type", b"application/json")],
                "state": {},
            }
            await consumers_app(root)(scope, receive, send)
            return sent[0]["status"]

        self.assertEqual(asyncio.run(put()), 204)
        # What was put is what comes back, and nothing else was written
        self.assertEqual(root, {"index": "new"})
        # What a client writes is text, and never served as HTML: a visitor's
        # string at / would be anyone's page
        status, _, _ = asyncio.run(get(root, "/"))
        self.assertEqual(status, 404)

    def test_index_is_only_special_last(self):
        # In the middle of a path it is a key like any other
        root = {"index": {"b": "under index"}, "b": "at the root"}
        _, _, body = asyncio.run(get(root, "/index/b.json"))
        self.assertEqual(json.loads(body), "under index")

    def test_the_empty_key_means_nothing(self):
        status, _, _ = asyncio.run(get({"a": 1}, "//a.json"))
        self.assertEqual(status, 404)

    def test_a_container_is_replaced_and_removed_by_its_name(self):
        root = {"todos": {"a": 1}}

        async def put():
            sent = []

            async def send(message):
                sent.append(message)

            async def receive():
                return {"type": "http.request", "body": b'["new"]', "more_body": False}

            scope = {
                "type": "http",
                "method": "PUT",
                "path": "/todos.json",
                "headers": [(b"content-type", b"application/json")],
                "state": {},
            }
            await consumers_app(root)(scope, receive, send)
            return sent[0]["status"]

        self.assertEqual(asyncio.run(put()), 204)
        self.assertEqual(root, {"todos": ["new"]})
        self.assertEqual(asyncio.run(get(root, "/todos.json", "DELETE"))[0], 204)
        self.assertEqual(root, {})

    def test_other_extensions_take_their_type_from_mimetypes(self):
        status, headers, _ = asyncio.run(get({"site": b"p {}"}, "/site.css"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"text/css; charset=UTF-8")
        _, headers, _ = asyncio.run(get({"logo": b"\x89PNG"}, "/logo.png"))
        self.assertEqual(headers[b"content-type"], b"image/png")

    def test_a_producer_that_starts_the_reply_gets_the_urls_type(self):
        from mumulib.producers import add_producer

        class Report:
            pass

        async def produce_report(thing, state):
            yield SpecialResponse(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"text/plain"), (b"x-kept", b"1")],
                },
                b"\x00\x01binary",
            )

        add_producer(Report, produce_report)
        status, headers, body = asyncio.run(get({"r": Report()}, "/r.json"))
        self.assertEqual(status, 200)
        self.assertEqual(headers[b"content-type"], b"application/json; charset=UTF-8")
        self.assertEqual(headers[b"x-kept"], b"1")
        # Bytes go out as they are, not as the text of their repr
        self.assertTrue(body.startswith(b"\x00\x01binary"))


class TestFunctionsInTheTree(unittest.TestCase):
    """A function a URL ends at is its own producer, called as f(state)."""

    def setUp(self):
        self.calls = []

        async def f(state):
            self.calls.append(dict(state))
            yield "one,"
            yield "two"

        self.f = f

    def test_it_is_called_with_the_request(self):
        status, headers, body = asyncio.run(get({"f": self.f}, "/f.txt"))
        self.assertEqual((status, body.strip()), (200, b"one,two"))
        self.assertEqual(headers[b"content-type"], b"text/plain; charset=UTF-8")
        [state] = self.calls
        self.assertEqual(
            (state["method"], state["url"], state["extension"]),
            ("GET", "/f.txt", "txt"),
        )

    def test_post_calls_it_with_the_body(self):
        async def post():
            sent = []

            async def send(message):
                sent.append(message)

            async def receive():
                return {"type": "http.request", "body": b'{"n": 1}', "more_body": False}

            scope = {
                "type": "http",
                "method": "POST",
                "path": "/f.json",
                "headers": [(b"content-type", b"application/json")],
                "state": {},
            }
            await consumers_app({"f": self.f})(scope, receive, send)
            return sent[0]["status"]

        self.assertEqual(asyncio.run(post()), 200)
        self.assertEqual(self.calls[0]["parsed_body"], {"n": 1})

    def test_it_is_a_leaf(self):
        for path in ("/f/", "/f/more.txt"):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get({"f": self.f}, path))[0], 404)
        self.assertEqual(self.calls, [])

    def test_a_method_is_not_found(self):
        root = {"upper": "abc".upper, "str": "abc".__str__}
        for path in ("/upper.txt", "/str.txt"):
            with self.subTest(path=path):
                status, _, body = asyncio.run(get(root, path))
                self.assertEqual(status, 404)
                self.assertNotIn(b"built-in", body)

    def test_its_parent_answers_put_and_delete_for_it(self):
        root = {"f": self.f}
        self.assertEqual(asyncio.run(get(root, "/f.txt", "DELETE"))[0], 204)
        self.assertEqual(root, {})
        self.assertEqual(self.calls, [])


class TestTextAndListings(unittest.TestCase):
    """Text is its own content; a container's slash lists what is in it."""

    def test_strings_and_numbers_are_text_and_json_alone(self):
        root = {"motto": "mumu", "count": 3, "ratio": 0.5}
        for path, expected in [
            ("/motto.txt", b"mumu"),
            ("/count.txt", b"3"),
            ("/ratio.txt", b"0.5"),
            ("/count.json", b"3"),
            ("/motto.json", b'"mumu"'),
        ]:
            with self.subTest(path=path):
                status, _, body = asyncio.run(get(root, path))
                self.assertEqual((status, body.strip()), (200, expected))
        # As markup, or code, a string could be anyone's: not found
        for path in (
            "/motto.html",
            "/ratio.html",
            "/motto.js",
            "/motto.css",
            "/motto.xml",
            "/motto.svg",
        ):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get(root, path))[0], 404)

    def test_markup_is_html_and_nothing_else(self):
        root = {"page": Markup("<p>mine</p>")}
        status, headers, body = asyncio.run(get(root, "/page.html"))
        self.assertEqual((status, body.strip()), (200, b"<p>mine</p>"))
        self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
        for path in ("/page.txt", "/page.json"):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get(root, path))[0], 404)

    def test_a_file_is_its_own_type_alone(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "style.css"
            sheet.write_text("p {}")
            root = {"style": sheet, "static": Path(directory)}
            for path, status in [
                ("/style.css", 200),
                ("/style.html", 404),
                ("/style.js", 404),
                ("/style.txt", 404),
                ("/static/style.css", 200),
                ("/static/style.html", 404),
            ]:
                with self.subTest(path=path):
                    self.assertEqual(asyncio.run(get(root, path))[0], status)

    def test_true_and_false_are_json_alone(self):
        # (None is not found at all: a consumer's None is "not found")
        root = {"on": True, "off": False}
        self.assertEqual(asyncio.run(get(root, "/on.json"))[2].strip(), b"true")
        self.assertEqual(asyncio.run(get(root, "/off.json"))[2].strip(), b"false")
        for path in ("/on.txt", "/off.html"):
            with self.subTest(path=path):
                self.assertEqual(asyncio.run(get(root, path))[0], 404)

    def test_none_is_null_in_json_and_not_found_as_an_answer(self):
        root = {"data": {"a": None, "items": [1, None, 3]}}
        _, _, body = asyncio.run(get(root, "/data.json"))
        self.assertEqual(json.loads(body), {"a": None, "items": [1, None, 3]})
        self.assertEqual(asyncio.run(get(root, "/data/a.json"))[0], 404)

    def test_what_has_no_producer_is_not_found(self):
        class Thing:
            def __str__(self):
                return "a repr that must not be served"

        status, _, body = asyncio.run(get({"thing": Thing()}, "/thing.txt"))
        self.assertEqual(status, 404)
        self.assertNotIn(b"repr", body)

    def test_json_of_what_has_no_json_form_is_an_err(self):
        class Thing:
            pass

        status, _, body = asyncio.run(get({"data": {"thing": Thing()}}, "/data.json"))
        self.assertEqual(status, 500)
        self.assertIn(b"Thing has no JSON form", body)

    def test_a_containers_slash_lists_what_could_be_fetched(self):
        import tempfile

        with (
            tempfile.NamedTemporaryFile(suffix=".css") as css,
            tempfile.NamedTemporaryFile(suffix="") as bare,
        ):
            with open(css.name) as sheet, open(bare.name) as plain:
                root = {
                    "notes": {
                        "motto": "mumu",
                        "count": 3,
                        "a b&c": "escaped",
                        "sub": {"x": 1},
                        "items": ["one"],
                        "sheet": sheet,
                        "plain": plain,
                        "on": True,
                        "nothing": None,
                        "method": "abc".upper,
                        "a/b": "no URL can name it",
                    }
                }
                status, headers, body = asyncio.run(get(root, "/notes/"))
                self.assertEqual(status, 200)
                self.assertEqual(headers[b"content-type"], b"text/html; charset=UTF-8")
                self.assertEqual(
                    body.decode().strip(),
                    "<!doctype html>\n<html>\n<head>\n"
                    '<meta charset="utf-8" />\n'
                    "<title>Index of /notes</title>\n"
                    "</head>\n<body>\n"
                    "<h1>Index of /notes</h1>\n"
                    "<ul>\n"
                    '  <li><a href="/">Parent Directory</a></li>\n'
                    '  <li><a href="/notes/motto.txt">motto</a></li>\n'
                    '  <li><a href="/notes/count.txt">count</a></li>\n'
                    '  <li><a href="/notes/a%20b%26c.txt">a b&amp;c</a></li>\n'
                    '  <li><a href="/notes/sub/">sub</a></li>\n'
                    '  <li><a href="/notes/items/">items</a></li>\n'
                    '  <li><a href="/notes/sheet.css">sheet</a></li>\n'
                    '  <li><a href="/notes/on.json">on</a></li>\n'
                    "</ul>\n"
                    "</body>\n</html>",
                )
                for url in (
                    "/notes/motto.txt",
                    "/notes/sheet.css",
                    "/notes/sub/",
                    "/notes/items/",
                ):
                    with self.subTest(url=url):
                        self.assertEqual(asyncio.run(get(root, url))[0], 200)

    def test_a_listing_below_names_its_parent(self):
        _, _, body = asyncio.run(get({"a": {"b": {"c": 1}}}, "/a/b/"))
        self.assertIn(b"<h1>Index of /a/b</h1>", body)
        self.assertIn(b'<li><a href="/a/">Parent Directory</a></li>', body)

    def test_a_listings_parent_is_where_its_parent_is_shown(self):
        from mumulib.consumers import GetOnly
        from mumulib.persist import Persist
        from mumulib.resource import Resource

        class Page(Resource):
            child_items = ["a"]

        class Indexed(Resource):
            child_index = Markup("<h1>Its page</h1>")
            child_items = ["a"]

        root = {
            "page": Page(),
            "indexed": Indexed(),
            "guarded": GetOnly({"inner": {"x": 1}}),
            "kept": Persist({"sub": {"x": 1}}),
        }
        # A resource is named as a file: its page, not a slash it has not got
        _, _, body = asyncio.run(get(root, "/page/items/"))
        self.assertIn(b'<a href="/page.html">Parent Directory</a>', body)
        # Unless its page is its index, at its slash
        _, _, body = asyncio.run(get(root, "/indexed/items/"))
        self.assertIn(b'<a href="/indexed/">Parent Directory</a>', body)
        # A guard at a container's URL is that container: the parent above it
        _, _, body = asyncio.run(get(root, "/guarded/inner/"))
        self.assertIn(b'<a href="/guarded/">Parent Directory</a>', body)
        # A persist's slash is its document's listing
        _, _, body = asyncio.run(get(root, "/kept/sub/"))
        self.assertIn(b'<a href="/kept/">Parent Directory</a>', body)

    def test_a_parent_with_no_page_to_show_is_no_link(self):
        from mumulib.consumers import parent_link

        # Walked through something that is neither a container nor has HTML
        state = {"url": "/x/y/", "walked": [(object(), "/x"), ({}, "/x/y")]}
        self.assertIsNone(parent_link(state))
        # And the root has none, nor a listing reached with nothing walked
        self.assertIsNone(parent_link({"url": "/"}))
        self.assertIsNone(parent_link({"url": "/x/y/"}))

    def test_the_root_lists_itself_with_no_parent(self):
        _, _, body = asyncio.run(get({"a": "x"}, "/"))
        self.assertIn(b"<title>Index of /</title>", body)
        self.assertNotIn(b"Parent Directory", body)

    def test_a_list_lists_its_indexes(self):
        _, _, body = asyncio.run(get({"items": ["a", "b"]}, "/items/"))
        self.assertIn(b'<a href="/items/0.txt">0</a>', body)
        self.assertIn(b'<a href="/items/1.txt">1</a>', body)

    def test_the_root_and_a_guarded_dict_list_too(self):
        _, _, body = asyncio.run(get({"a": "x"}, "/"))
        self.assertIn(b'<a href="/a.txt">a</a>', body)
        from mumulib.consumers import GetOnly

        _, _, body = asyncio.run(get({"g": GetOnly({"a": "x"})}, "/g/"))
        self.assertIn(b'<a href="/g/a.txt">a</a>', body)
