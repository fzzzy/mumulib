
import json
import traceback

from mumulib.consumers import consume
from mumulib.mumutypes import SpecialResponse, HTTPResponse
from mumulib.producers import produce


async def parse_json(receive):
    body = b''

    # Receive request body chunks
    while True:
        message = await receive()

        # Check if we've reached the end of the body
        if message['type'] == 'http.request':
            # Accumulate body chunks
            body += message.get('body', b'')

            # Check if this is the last body chunk
            if not message.get('more_body', False):
                break

    # Process the full body
    body_text = body.decode('utf-8')
    if len(body_text):
        return json.loads(body_text)


def consumers_app(root):
    async def app(scope, receive, send):
        if scope['type'] == 'lifespan':
                while True:
                    message = await receive()
                    if message['type'] == 'lifespan.startup':
                        await send({'type': 'lifespan.startup.complete'})
                    elif message['type'] == 'lifespan.shutdown':
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
            content_type = "text/html"

        for (key, value) in scope["headers"]:
            if key.lower() == b"content-type":
                lowervalue = value.lower()
                if lowervalue == b'application/json':
                    state["parsed_body"] = await parse_json(receive)
                elif lowervalue == b'application/x-www-form-urlencoded':
                    print("application/x-www-form-urlencoded")
                elif lowervalue == b'multipart/form-data':
                    print("multipart/form-data")
                else:
                    print("Unknown content type: %s" % value)

        result = await consume(root, scope["path"].split("/")[1:], state, send)
        if result is None:
            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [(b'content-type', b'application/json; charset=UTF-8')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'{"error": "Not Found"}',
                'more_body': False,
            })
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
                traceback.print_exc(exc)
                resp = HTTPResponse(500, str(exc))
                if first_chunk:
                    await send(resp.asgi_send_dict)
                    first_chunk = False
                result = resp.leaf_object
        await send({
            'type': 'http.response.body',
            'body': str(result).encode('utf8'),
            'more_body': False,
        })

    return app

