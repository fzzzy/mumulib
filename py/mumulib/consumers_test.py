# pyright: standard
import json
import unittest
from types import MappingProxyType

from mumulib.server import consumers_app


async def request(asgi_app, method, path, body):
    """
    Sends an HTTP request to an ASGI app without external dependencies.

    Args:
        asgi_app: The ASGI application to interact with.
        method (str): HTTP method (e.g., 'GET', 'POST').
        path (str): The request path.
        body (dict, optional): JSON-serializable body for the request.

    Returns:
        dict: A dictionary with 'status', 'headers', and 'body' keys.
    """
    # Create ASGI scope
    scope = {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "headers": [
            (b"content-type", b"application/json"),
            (b"host", b"testserver"),
        ],
        "query_string": b"",
        "state": {},
    }

    if body is not None:
        body_bytes = json.dumps(body).encode("utf-8")
        scope["headers"].append(
            (b"content-length", str(len(body_bytes)).encode("utf-8"))
        )
    else:
        body_bytes = b""

    # ASGI event queues
    receive_queue = [{"type": "http.request", "body": body_bytes, "more_body": False}]
    send_queue = []

    async def receive():
        return receive_queue.pop(0) if receive_queue else {"type": "http.disconnect"}

    async def send(event):
        send_queue.append(event)

    # Call the ASGI app
    await asgi_app(scope, receive, send)

    # Process the response
    response_start = next(
        event for event in send_queue if event["type"] == "http.response.start"
    )
    response_body = next(
        event for event in send_queue if event["type"] == "http.response.body"
    )

    decoded_body = response_body["body"].decode("utf-8")
    if decoded_body:
        try:
            decoded_body = json.loads(decoded_body)
        except json.decoder.JSONDecodeError:
            pass

    return {
        "status": response_start["status"],
        "headers": {k.decode(): v.decode() for k, v in response_start["headers"]},
        "body": decoded_body,
    }


class Foo:
    pass


ASGI_APP = consumers_app(
    {
        "hello": "world",
        "tuple": ("this", "is", "a", "tuple"),
        "list": ["this", "is", "a", "list"],
        "immutable": MappingProxyType({"cannot": "touch this"}),
        "immutable_with_index": MappingProxyType(
            {"index": "index_value", "other": "other_value"}
        ),
        "not_found": Foo(),
        "nested_list": [["asdf"], ["qwer"]],
        "nested_dict": {"nested": {"again": "string"}},
    }
)


class TestASGIApp(unittest.IsolatedAsyncioTestCase):
    async def test_basic(self):
        # Test GET /
        response = await request(ASGI_APP, "GET", "/index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"],
            {
                "hello": "world",
                "tuple": ["this", "is", "a", "tuple"],
                "list": ["this", "is", "a", "list"],
                "immutable": {"cannot": "touch this"},
                "immutable_with_index": {
                    "index": "index_value",
                    "other": "other_value",
                },
                "not_found": None,
                "nested_list": [["asdf"], ["qwer"]],
                "nested_dict": {"nested": {"again": "string"}},
            },
        )

    async def test_basic_put_delete(self):
        # Test GET /hello
        response = await request(ASGI_APP, "GET", "/hello.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "world")

        # Test PUT /hello
        response = await request(ASGI_APP, "PUT", "/hello.json", "newworld")
        self.assertEqual(response["status"], 201)

        # Verify GET /hello after PUT
        response = await request(ASGI_APP, "GET", "/hello.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "newworld")

        # Test DELETE /hello
        response = await request(ASGI_APP, "DELETE", "/hello.json", None)
        self.assertEqual(response["status"], 200)

        # DELETE of a key that is not there is still OK
        response = await request(ASGI_APP, "DELETE", "/hello.json", None)
        self.assertEqual(response["status"], 200)

        # Verify GET / after DELETE /hello
        response = await request(ASGI_APP, "GET", "/index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"],
            {
                "tuple": ["this", "is", "a", "tuple"],
                "list": ["this", "is", "a", "list"],
                "immutable": {"cannot": "touch this"},
                "immutable_with_index": {
                    "index": "index_value",
                    "other": "other_value",
                },
                "not_found": None,
                "nested_list": [["asdf"], ["qwer"]],
                "nested_dict": {"nested": {"again": "string"}},
            },
        )

    async def test_tuple(self):
        # Test GET /tuple and /tuple/2
        response = await request(ASGI_APP, "GET", "/tuple/index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "is", "a", "tuple"])

        response = await request(ASGI_APP, "GET", "/tuple/2.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "a")

        # Test PUT and DELETE on /tuple/2
        response = await request(ASGI_APP, "PUT", "/tuple/2.json", "change")
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "DELETE", "/tuple/2.json", None)
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "GET", "/tuple/asdf.json", None)
        self.assertEqual(response["status"], 404)

    async def test_list(self):
        # Test GET /list and /list/1
        response = await request(ASGI_APP, "GET", "/list/index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "is", "a", "list"])

        response = await request(ASGI_APP, "GET", "/list/1.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "is")

        # Test PUT /list/1
        response = await request(ASGI_APP, "PUT", "/list/1.json", "modified")
        self.assertEqual(response["status"], 201)

        # Verify GET /list after PUT /list/1
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "modified", "a", "list"])

        # Test PUT /list/555 fails
        response = await request(
            ASGI_APP, "PUT", "/list/555.json", json.dumps("notappended")
        )
        self.assertEqual(response["status"], 403)

        # Test PUT /list/asdf fails
        response = await request(
            ASGI_APP, "PUT", "/list/asdf.json", json.dumps("notappended")
        )
        self.assertEqual(response["status"], 405)

        # Test GET /list/asdf fails
        response = await request(ASGI_APP, "GET", "/list/asdf.json", None)
        self.assertEqual(response["status"], 404)

        # Test PUT /list/last
        response = await request(ASGI_APP, "PUT", "/list/last.json", "appended")
        self.assertEqual(response["status"], 201)
        # The new element's own URL, extension and all
        self.assertEqual(response["headers"]["location"], "/list/4.json")

        # Verify GET /list after PUT /list/last
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"], ["this", "modified", "a", "list", "appended"]
        )

        # Test DELETE /list/1
        response = await request(ASGI_APP, "DELETE", "/list/1.json", None)
        self.assertEqual(response["status"], 200)

        # Verify GET /list after DELETE /list/1
        response = await request(ASGI_APP, "GET", "/list.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], ["this", "a", "list", "appended"])

        # Test DELETE /list/555
        response = await request(ASGI_APP, "DELETE", "/list/555.json", None)
        self.assertEqual(response["status"], 200)

        # Test DELETE /list/asdf
        response = await request(ASGI_APP, "DELETE", "/list/asdf.json", None)
        self.assertEqual(response["status"], 200)

    async def test_nested_list(self):
        response = await request(ASGI_APP, "GET", "/nested_list/0/0.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "asdf")

    async def test_nested_dict(self):
        response = await request(
            ASGI_APP, "GET", "/nested_dict/nested/again.json", None
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "string")

    async def test_immutable(self):
        # Test GET /immutable
        response = await request(ASGI_APP, "GET", "/immutable.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"cannot": "touch this"})

        # Test PUT and DELETE on /immutable/cannot
        response = await request(
            ASGI_APP, "PUT", "/immutable/cannot.json", json.dumps("attempted change")
        )
        self.assertEqual(response["status"], 405)

        response = await request(ASGI_APP, "DELETE", "/immutable/cannot.json", None)
        self.assertEqual(response["status"], 405)

        # Verify GET /immutable after PUT and DELETE
        response = await request(ASGI_APP, "GET", "/immutable.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], {"cannot": "touch this"})

    async def test_immutable_with_index(self):
        # Test GET /immutable_with_index - should return the whole dict
        response = await request(ASGI_APP, "GET", "/immutable_with_index.json", None)
        self.assertEqual(response["status"], 200)
        self.assertEqual(
            response["body"], {"index": "index_value", "other": "other_value"}
        )

        # Test GET /immutable_with_index/ (with trailing slash) - should return
        # the "index" value
        response = await request(
            ASGI_APP, "GET", "/immutable_with_index/index.json", None
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "index_value")

        # Test GET /immutable_with_index/other - should return the "other" value
        response = await request(
            ASGI_APP, "GET", "/immutable_with_index/other.json", None
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"], "other_value")

    async def test_not_found(self):
        # Test GET /not_found/foo fails
        response = await request(ASGI_APP, "GET", "/not_found/foo.json", None)
        self.assertEqual(response["status"], 404)

        # Test GET /asdfasdfasdfasdf fails
        response = await request(ASGI_APP, "GET", "/asdfasdfasdfasdf.json", None)
        self.assertEqual(response["status"], 404)


class TestSecurityValidation(unittest.IsolatedAsyncioTestCase):
    """Test security validation for index and key sanitization."""

    async def test_list_index_out_of_bounds(self):
        # Test with extremely large index
        response = await request(ASGI_APP, "GET", f"/list/{2**62}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_list_negative_index_out_of_bounds(self):
        # Test with extremely negative index
        response = await request(ASGI_APP, "GET", f"/list/{-(2**62)}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_key_too_long(self):
        # Test with key longer than MAX_KEY_LENGTH (1000 chars)
        long_key = "a" * 1001
        response = await request(ASGI_APP, "GET", f"/nested_dict/{long_key}.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_key_with_null_byte(self):
        # Test with key containing null byte
        # URL encoding for null byte is %00
        response = await request(ASGI_APP, "GET", "/nested_dict/test\x00key.json", None)
        self.assertEqual(response["status"], 404)

    async def test_dict_put_key_too_long(self):
        # Test PUT with key longer than MAX_KEY_LENGTH
        long_key = "b" * 1001
        response = await request(
            ASGI_APP, "PUT", f"/nested_dict/{long_key}.json", "value"
        )
        self.assertEqual(response["status"], 404)

    async def test_dict_put_key_with_null_byte(self):
        # Test PUT with key containing null byte
        response = await request(
            ASGI_APP, "PUT", "/nested_dict/bad\x00key.json", "value"
        )
        self.assertEqual(response["status"], 404)

    async def test_tuple_index_out_of_bounds(self):
        # Test tuple access with extremely large index
        response = await request(ASGI_APP, "GET", f"/tuple/{2**62}.json", None)
        self.assertEqual(response["status"], 404)
