"""Resources: objects that say what is below them, and how they answer.

A subclass of Resource names its children as attributes, child_<name>, and
answers a request that ends at it with render(request), which calls
handle_<METHOD>(request): handle_GET renders its template, and every other
method is refused unless the subclass says how to answer it. Its state is a
dict given to the constructor, and read at its child state.json.

    class Profile(Resource):
        template = "<h1>Ada</h1>"
        child_name = "Ada"

    class Site(Resource):
        child_index = "<h1>Home</h1>"
        child_profile = Profile()

    app = consumers_app(Site())      # /, /profile.html, /profile/name.txt

A resource is not a container: it is named as a file, /profile.html or
/profile.json, and render can answer each type as it likes -- the request
says which, in "content_type" and "extension". Its children are walked into like
anything else, and each can be anything publishable, a Resource included.
"""

import inspect
from collections.abc import AsyncIterator, Iterator
from typing import Any, NoReturn, cast

from mumulib.consumers import GetOnly, add_consumer, consume, refuse
from mumulib.mumutypes import Chunk, Send, SpecialResponse, State
from mumulib.producers import add_json_form, add_producer, can_produce, produce
from mumulib.tags import Stan

# The public API: the class to subclass.
__all__ = ["Resource"]

# The methods a Resource has a handler for, and refuses unless one is given
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")


class Resource:
    """A published object with children of its own and a way to answer.

    Every subclass is registered as it is defined, with the consumer and
    producer below: mumulib finds both by exact type, so Resource being
    registered would not reach a subclass. Resource is registered too.

    Its state is a dict, given to the constructor: Resource({"name": "Ada"}).
    It is published read-only as the child state -- /<resource>/state.json
    -- and is the resource's JSON inside any other JSON, and what a
    template's slots are filled from when there is no slot_ for them. The
    request a handler is given is another thing, and is called request here
    to keep the two apart.
    """

    template: Any = ""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = {} if state is None else state

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _register(cls)

    async def get_child(self, segments: list[str], request: State, send: Send) -> Any:
        """The child the next segment names, or None: its child_ attribute,
        or for state, with no child_state, the resource's state, read-only.

        The prefix keeps what can be reached to what was meant to be:
        /__class__.html is child___class__, which is nothing. The state is
        read at /<resource>/state.json, and below it, /state/name.txt; it is
        written only by the resource's own handlers, which say what may be.
        """
        name = segments[0]
        child = getattr(self, f"child_{name}", None)
        if child is None and name == "state":
            if len(segments) == 1 and request.get("method", "GET").upper() != "GET":
                # The state itself is not replaced: GetOnly guards below it,
                # and here, its own name in this resource, is refused too
                return refuse("GET")
            return GetOnly(self.state)
        return child

    async def render(self, request: State) -> Any:
        """The answer to a request that ends here: its method's handler's.

        What it returns is produced as though it had been published there,
        of the URL's type: a string as it is, a dict as JSON at .json. A
        handler may be async or not; what it returns is awaited if it can be.
        """
        method = str(request.get("method", "GET")).upper()
        handler = getattr(self, f"handle_{method}", None)
        if handler is None:
            self.refuse()
        return await _settled(handler(request))

    async def handle_GET(self, request: State) -> Any:
        """The template: as it is, or a parsed one filled from slot_ names and
        the state. The state as data is a child of its own, state.json."""
        if isinstance(self.template, Stan):
            return await self.fill(self.template, request)
        return self.template

    async def fill(self, template: Stan, request: State) -> Stan:
        """A copy of template, each slot in it filled from this resource's
        slot_<name> -- a method called with the request, async or not, or a
        plain value -- or, with no slot_, from the state's entry by that
        name. A slot with neither keeps what the template has there; one
        given None is emptied. A slot inside a pattern is the pattern's,
        filled when it is copied, not here.

        A slot takes what it is given as fill_slots does: text escaped as
        it is written out, a tree or a list of them as markup, and anything
        else as the HTML a producer makes of it.
        """
        page = template.copy()
        for name in slot_names(page):
            filler = getattr(self, f"slot_{name}", _MISSING)
            if filler is not _MISSING:
                value = await _settled(filler(request) if callable(filler) else filler)
            elif name in self.state:
                value = self.state[name]
            else:
                continue
            _check_html(name, value)
            if value is None:
                page.clear_slots(name)
            else:
                page.fill_slots(name, value)
        return page

    def pattern(self, name: str, /, **slots: Any) -> Stan:
        """A copy of the template's pattern name, data-pat, with slots
        filled: one item for a list, say."""
        if not isinstance(self.template, Stan):
            raise TypeError("only a parsed template has patterns")
        copy = self.template.clone_pat(name, **slots)
        if copy is None:
            raise ValueError(f"the template has no pattern {name!r}")
        return copy

    async def handle_HEAD(self, request: State) -> Any:
        self.refuse()

    async def handle_POST(self, request: State) -> Any:
        self.refuse()

    async def handle_PUT(self, request: State) -> Any:
        self.refuse()

    async def handle_PATCH(self, request: State) -> Any:
        self.refuse()

    async def handle_DELETE(self, request: State) -> Any:
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

    def see_other(self, url: str) -> NoReturn:
        """303 See Other, to url: what a form post that has done what it was
        asked answers with, so the browser goes on to get url rather than
        staying at the post, which a reload would make again."""
        raise SpecialResponse(
            {
                "type": "http.response.start",
                "status": 303,
                "headers": [(b"location", url.encode("utf-8"))],
            },
            b"",
        )

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
    parent: Resource, segments: list[str], request: State, send: Send
) -> Any:
    child = await parent.get_child(segments, request, send)
    if child is None:
        return None
    return await consume(child, segments[1:], request, send)


async def produce_resource(thing: Resource, request: State) -> AsyncIterator[Chunk]:
    async for chunk in produce(await thing.render(request), request):
        yield chunk


# Stands for "this resource has no slot_ by that name"
_MISSING = object()


async def _settled(value: Any) -> Any:
    """value, awaited if it is awaitable: what a handler or slot_ that may
    be async or not came to."""
    if inspect.isawaitable(value):
        return await value
    return value


def _check_html(name: str, value: Any) -> None:
    """Refuses, while a response can still say so, a slot's value that
    would have no HTML once the page is being written out."""
    values: list[Any] = cast(list[Any], value) if isinstance(value, list) else [value]
    for each in values:
        if each is None or isinstance(each, (str, int, float, Stan)):
            continue
        if isinstance(each, bool) or not can_produce(each, "text/html"):
            raise TypeError(f"slot {name!r}: a {type(each).__name__} has no HTML form")


def slot_names(node: Stan) -> list[str]:
    """The slots in a tree, content and attribute alike, in document order
    and each once -- but not those inside a pattern, which are its own."""
    return list(dict.fromkeys(_slot_names(node)))


def _slot_names(node: Stan) -> Iterator[str]:
    for child in node.children:
        if not isinstance(child, Stan) or "data-pat" in child.attributes:
            continue
        slot = child.attributes.get("data-slot")
        if slot:
            yield slot
        for pair in str(child.attributes.get("data-attr", "")).split(","):
            _, eq, attrslot = pair.partition("=")
            if eq and attrslot:
                yield attrslot
        yield from _slot_names(child)


def _register(cls: type[Resource]) -> None:
    add_consumer(cls, consume_resource, own_methods=True)
    add_producer(cls, produce_resource)
    # Inside any JSON, a resource is its state
    add_json_form(cls, lambda resource: resource.state)


_register(Resource)
