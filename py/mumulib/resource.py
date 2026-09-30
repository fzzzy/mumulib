"""Resources: objects that say what is below them, and how they answer.

A subclass of Resource names its children as attributes, child_<name>, and
answers a request that ends at it with render(state), which calls
handle_<METHOD>(state): handle_GET renders its template, and every other
method is refused unless the subclass says how to answer it.

    class Profile(Resource):
        template = "<h1>Ada</h1>"
        child_name = "Ada"

    class Site(Resource):
        child_index = "<h1>Home</h1>"
        child_profile = Profile()

    app = consumers_app(Site())      # /, /profile.html, /profile/name.txt

A resource is not a container: it is named as a file, /profile.html or
/profile.json, and render can answer each type as it likes -- state says
which, in "content_type" and "extension". Its children are walked into like
anything else, and each can be anything publishable, a Resource included.
"""

from collections.abc import AsyncIterator
from typing import Any, NoReturn

from mumulib.consumers import add_consumer, consume
from mumulib.mumutypes import Chunk, Send, SpecialResponse, State
from mumulib.producers import add_producer, produce

# The public API: the class to subclass.
__all__ = ["Resource"]

# The methods a Resource has a handler for, and refuses unless one is given
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")


class Resource:
    """A published object with children of its own and a way to answer.

    Every subclass is registered as it is defined, with the consumer and
    producer below: mumulib finds both by exact type, so Resource being
    registered would not reach a subclass. Resource is registered too.
    """

    template: Any = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _register(cls)

    async def get_child(self, segments: list[str], state: State, send: Send) -> Any:
        """The child the next segment names, or None: its child_ attribute.

        The prefix keeps what can be reached to what was meant to be:
        /__class__.html is child___class__, which is nothing.
        """
        return getattr(self, f"child_{segments[0]}", None)

    def render(self, state: State) -> Any:
        """The answer to a request that ends here: its method's handler's.

        What it returns is produced as though it had been published there,
        of the URL's type: a string as it is, a dict as JSON at .json.
        """
        method = str(state.get("method", "GET")).upper()
        handler = getattr(self, f"handle_{method}", None)
        if handler is None:
            self.refuse()
        return handler(state)

    def handle_GET(self, state: State) -> Any:
        return self.template

    def handle_HEAD(self, state: State) -> Any:
        self.refuse()

    def handle_POST(self, state: State) -> Any:
        self.refuse()

    def handle_PUT(self, state: State) -> Any:
        self.refuse()

    def handle_PATCH(self, state: State) -> Any:
        self.refuse()

    def handle_DELETE(self, state: State) -> Any:
        self.refuse()

    def allowed(self) -> list[str]:
        """The methods this resource answers: GET, and those it handles."""
        return [
            method
            for method in METHODS
            if method == "GET"
            or getattr(type(self), f"handle_{method}")
            is not getattr(Resource, f"handle_{method}")
        ]

    def refuse(self) -> NoReturn:
        """405 Method Not Allowed, saying which methods are."""
        raise SpecialResponse(
            {
                "type": "http.response.start",
                "status": 405,
                "headers": [
                    (b"allow", ", ".join(self.allowed()).encode()),
                    (b"content-type", b"text/plain; charset=UTF-8"),
                ],
            },
            b"Method Not Allowed\n",
        )


async def consume_resource(
    parent: Resource, segments: list[str], state: State, send: Send
) -> Any:
    child = await parent.get_child(segments, state, send)
    if child is None:
        return None
    return await consume(child, segments[1:], state, send)


async def produce_resource(thing: Resource, state: State) -> AsyncIterator[Chunk]:
    async for chunk in produce(thing.render(state), state):
        yield chunk


def _register(cls: type[Resource]) -> None:
    add_consumer(cls, consume_resource, own_methods=True)
    add_producer(cls, produce_resource)


_register(Resource)
