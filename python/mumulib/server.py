
import json
from types import MappingProxyType

from consumers import consume
from mumutypes import SpecialResponse


def custom_serializer(obj):
    if isinstance(obj, MappingProxyType):
        return dict(obj)
    return None


async def parse_json(scope, receive):
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
        scope["state"]["parsed_body"] = json.loads(body_text)


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

        scope["state"]["url"] = scope["path"]
        scope["state"]["method"] = scope["method"]

        for (key, value) in scope["headers"]:
            if key.lower() == b"content-type" and value.lower() == b'application/json':
                await parse_json(scope, receive)

        result = await consume(root, scope["path"].split("/")[1:], scope["state"], send)
        if result is None:
            await send({
                'type': 'http.response.start',
                'status': 404,
                'headers': [(b'content-type', b'text/plain')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Not Found',
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
                'headers': [(b'content-type', b'text/plain')],
            })
            result = bytes(json.dumps(result, default=custom_serializer), 'utf8') + b"\n"
        await send({
            'type': 'http.response.body',
            'body': result,
            'more_body': False,
        })

    return app


# test_app = consumers_app({"hello": "world"})
# test_app = consumers_app(("hello", "world"))
test_app = consumers_app(["goodbye", "mr chips"])
# test_app = consumers_app(MappingProxyType({"immutable": "dict"}))

test_app = consumers_app(
    {
        "hello": "world",
        "tuple": ("this", "is", "a", "tuple"),
        "list": ["this", "is", "a", "list"],
        "immutable": MappingProxyType({"cannot": "touch this"})
    }
)

