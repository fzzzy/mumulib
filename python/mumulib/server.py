
import asyncio
import json
import traceback
from typing import Any, Callable, Dict, Optional
from urllib import parse

from mumulib.consumers import consume
from mumulib.mumutypes import SpecialResponse, HTTPResponse
from mumulib.producers import produce

# Default max request body size: 10MB
DEFAULT_MAX_BODY_SIZE = 10 * 1024 * 1024


async def send_error_response(send: Callable, status: int, error_type: str, message: str) -> None:
    """
    Send a consistent JSON error response.

    Args:
        send: ASGI send callable
        status: HTTP status code
        error_type: Error type/title (e.g., "Bad Request", "Internal Server Error")
        message: Detailed error message
    """
    await send({
        'type': 'http.response.start',
        'status': status,
        'headers': [(b'content-type', b'application/json; charset=UTF-8')],
    })
    await send({
        'type': 'http.response.body',
        'body': json.dumps({"error": error_type, "message": message}).encode('utf-8'),
        'more_body': False,
    })


async def parse_json(receive: Callable, max_size: int = DEFAULT_MAX_BODY_SIZE) -> Optional[Any]:
    body = b''

    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        if message['type'] == 'http.request':
            # Accumulate body chunks
            body += message.get('body', b'')

            # Check if body size exceeds limit
            if len(body) > max_size:
                raise ValueError(f"Request body too large: {len(body)} bytes exceeds limit of {max_size} bytes")

            # Check if this is the last body chunk
            if not message.get('more_body', False):
                break

    # Process the full body
    body_text = body.decode('utf-8')
    if len(body_text):
        return json.loads(body_text)
    return None


async def parse_urlencoded(receive: Callable, max_size: int = DEFAULT_MAX_BODY_SIZE) -> Dict[str, Any]:
    body = b''

    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        if message['type'] == 'http.request':
            # Accumulate body chunks
            body += message.get('body', b'')

            # Check if body size exceeds limit
            if len(body) > max_size:
                raise ValueError(f"Request body too large: {len(body)} bytes exceeds limit of {max_size} bytes")

            # Check if this is the last body chunk
            if not message.get('more_body', False):
                break
    result: Dict[str, Any] = {}
    for (k, v) in parse.parse_qsl(body.decode('utf-8')):
        k = parse.unquote(k)
        v = parse.unquote(v)
        if k.endswith("]") and "[" in k:
            l = result.get(k, [])
            l.append(v)
            result[k] = l
        else:
            result[k] = v
    return result


async def parse_multipart(receive: Callable, boundary: bytes, max_size: int = DEFAULT_MAX_BODY_SIZE) -> Dict[str, Any]:
    body = b''
    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        if message['type'] == 'http.request':
            # Accumulate body chunks
            body += message.get('body', b'')

            # Check if body size exceeds limit
            if len(body) > max_size:
                raise ValueError(f"Request body too large: {len(body)} bytes exceeds limit of {max_size} bytes")

            # Check if this is the last body chunk
            if not message.get('more_body', False):
                break
    result: Dict[str, Any] = {}
    for part in body.split(boundary):
        if not part or part.strip() == b'--':
            continue
        headers_bytes, content = part.split(b"\r\n\r\n", 1)
        headers = headers_bytes.split(b"\r\n")
        name: Optional[bytes] = None
        for header in headers:
            if header.startswith(b"Content-Disposition:"):
                name = header.split(b";")[1].split(b"=")[1][1:-1]
        if name:
            # Strip trailing \r\n-- or \r\n from content
            stripped_content = content.rstrip(b'-').rstrip(b'\r\n')
            for x in headers:
                if b'Content-Type' in x:
                    result[name.decode("utf-8")] = stripped_content
                    break
            else:
                result[name.decode("utf-8")] = stripped_content.decode("utf-8")
    return result


def consumers_app(root: Any) -> Callable:
    async def app(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope['type'] == 'lifespan':
            while True:
                message = await receive()
                if message['type'] == 'lifespan.startup':
                    await send({'type': 'lifespan.startup.complete'})
                if message['type'] == 'lifespan.shutdown':
                    await send({'type': 'lifespan.shutdown.complete'})
                    return

        assert scope['type'] == 'http'

        state = scope["state"]
        state["url"] = scope["path"]
        state["method"] = scope["method"]
        content_type = None
        if scope["path"].endswith(".json"):
            state["accept"] = ["application/json", "*/*"]
            content_type = "application/json; charset=UTF-8"
        elif scope["path"].endswith(".html"):
            state["accept"] = ["text/html", "*/*"]
            content_type = "text/html; charset=UTF-8"
        else:
            state["accept"] = ["*/*"]
            content_type = "text/html; charset=UTF-8"

        try:
            for (key, value) in scope["headers"]:
                if key.lower() == b"content-type":
                    lowervalue = value.lower().split(b";")[0]
                    if lowervalue == b'application/json':
                        state["parsed_body"] = await parse_json(receive)
                        state["accept"] = ["application/json", "*/*"]
                        content_type = "application/json; charset=UTF-8"
                    elif lowervalue == b'application/x-www-form-urlencoded':
                        state["parsed_body"] = await parse_urlencoded(receive)
                    elif lowervalue == b'multipart/form-data':
                        boundary = b'--' + value[len(lowervalue) + 11:]
                        state["parsed_body"] = await parse_multipart(
                            receive, boundary)
                    else:
                        print("Unknown content type: %s" % value)
        except ValueError as exc:
            # Handle request body size limit errors
            await send_error_response(send, 413, "Payload Too Large", str(exc))
            return

        try:
            result = await consume(root, scope["path"].split("/")[1:], state, send)
        except Exception as exc:
            # Handle errors during request consumption/routing
            traceback.print_exc()
            await send_error_response(send, 500, "Internal Server Error", str(exc))
            return
        if result is None:
            await send_error_response(send, 404, "Not Found", f"Resource not found: {scope['path']}")
            return

        if isinstance(result, SpecialResponse):
            await send(result.asgi_send_dict)
            result = result.leaf_object
        else:
            first_chunk = True
            try:
                async for chunk in produce(result, state):
                    if first_chunk:
                        if isinstance(chunk, SpecialResponse):
                            await send(chunk.asgi_send_dict)
                            await send({
                                'type': 'http.response.body',
                                'body': str(chunk.leaf_object).encode('utf8'),
                                'more_body': True,
                            })
                            if chunk.writer is not None:
                                await chunk.writer(send, receive)
                        else:
                            await send({
                                'type': 'http.response.start',
                                'status': 200,
                                'headers': [(b'content-type', content_type.encode('utf8'))],
                            })
                            await send({
                                'type': 'http.response.body',
                                'body': str(chunk).encode('utf8'),
                                'more_body': True,
                            })
                        first_chunk = False
                    else:
                        await send({
                            'type': 'http.response.body',
                            'body': str(chunk).encode('utf8'),
                            'more_body': True,
                        })
                result = "\n"
            except SpecialResponse as special:
                if first_chunk:
                    await send(special.asgi_send_dict)
                    first_chunk = False
                result = special.leaf_object
            except Exception as exc:
                traceback.print_exc()
                if first_chunk:
                    await send({
                        'type': 'http.response.start',
                        'status': 500,
                        'headers': [(b'content-type', b'application/json; charset=UTF-8')],
                    })
                    first_chunk = False
                result = json.dumps({"error": "Internal Server Error", "message": str(exc)})

        # Ensure result is bytes
        if isinstance(result, str):
            result_bytes = result.encode('utf8')
        elif isinstance(result, bytes):
            result_bytes = result
        else:
            result_bytes = str(result).encode('utf8')

        await send({
            'type': 'http.response.body',
            'body': result_bytes,
            'more_body': False,
        })

    return app


def EventSource(output_queue):
    async def handle_eventsource(_, state):
        async def writer(send, receive):
            while True:
                # Create tasks for the ASGI receive and the queue.
                task_receive = asyncio.create_task(receive())
                task_queue = asyncio.create_task(output_queue.get())

                try:
                    done, pending = await asyncio.wait(
                        {task_receive, task_queue},
                        return_when=asyncio.FIRST_COMPLETED
                    )
                except asyncio.CancelledError:
                    break
                if task_queue in done:
                    result = done.pop().result()
                    await send({
                        'type': 'http.response.body',
                        'body': f"data: {result}\n\n".encode('utf8'),
                        'more_body': True,
                    })
                else:
                    task_queue.cancel()
                    break

        yield SpecialResponse(
            {
                'type': 'http.response.start',
                'status': 200,
                'headers': [
                    (b'content-type', b'text/event-stream; charset=UTF-8'),
                    (b'cache-control', b'no-cache'),],
            },
            b"event: ping\ndata: {}\n\n",
            writer
        )
    return handle_eventsource
