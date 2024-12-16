
import json

from consumers import consume
from mumutypes import SpecialResponse
from producers import produce


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
        # Just hard code json for now
        state["accept"] = ["application/json"]

        for (key, value) in scope["headers"]:
            if key.lower() == b"content-type" and value.lower() == b'application/json':
                state["parsed_body"] = await parse_json(receive)

        result = await consume(root, scope["path"].split("/")[1:], state, send)
        if result is None:
            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [(b'content-type', b'application/json')],
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
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'application/json')],
            })
            async for chunk in produce(result, state):
                await send({
                    'type': 'http.response.body',
                    'body': chunk,
                    'more_body': True,
                })
            result = b'\n'
        await send({
            'type': 'http.response.body',
            'body': result,
            'more_body': False,
        })

    return app

