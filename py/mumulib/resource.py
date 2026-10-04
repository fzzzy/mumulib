"""Resources: objects that say what is below them, and how they answer.

A subclass of Resource names its children as attributes, child_<name>, and
answers a request that ends at it with render(request), which calls
handle_<METHOD>(request): handle_GET renders its template as HTML, and its
state as JSON, and every other method is refused unless the subclass says
how to answer it. Its state is a dict given to the constructor.

    class Profile(Resource):
        template = "<h1>Ada</h1>"
        child_name = "Ada"

    class Site(Resource):
        child_index = Markup("<h1>Home</h1>")
        child_profile = Profile()

    app = consumers_app(Site())      # /, /profile.html, /profile/name.txt

A resource is not a container: it is named as a file, /profile.html or
/profile.json, and render can answer each type as it likes -- the request
says which, in "content_type" and "extension". Its children are walked into like
anything else, and each can be anything publishable, a Resource included.
"""

import inspect
import json
from collections.abc import AsyncIterator, Iterator
from typing import Any, NoReturn, cast

from mumulib.consumers import (
    Located,
    add_consumer,
    consume,
    plain,
    read_file,
    write_file,
)
from mumulib.mumutypes import Chunk, NotFoundResponse, Send, SpecialResponse, State
from mumulib.producers import (
    add_producer,
    can_produce,
    custom_serializer,
    produce,
)
from mumulib.tags import Markup, Stan, attr_slots
from mumulib.xml_producer import XmlOf

# The public API: the class to subclass.
__all__ = ["Resource", "Form"]

# The methods a Resource has a handler for, and refuses unless one is given
METHODS = ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")


class Form:
    """What a form posted, by name: Resource.form(request) makes one."""

    def __init__(self, fields: dict[str, Any]) -> None:
        self.fields = fields

    def text(self, name: str) -> str:
        """One field, stripped: "" if it was not sent, or not as text."""
        value = self.fields.get(name, "")
        return value.strip() if isinstance(value, str) else ""

    def texts(self, name: str) -> list[str]:
        """Every value sent by that name, as a <select multiple> or several
        checkboxes send them: name[] or name, and none at all is []."""
        value = self.fields.get(f"{name}[]", self.fields.get(name, []))
        values = cast(list[Any], value) if isinstance(value, list) else [value]
        return [v for v in values if isinstance(v, str)]


class Resource(Located):
    """A published object with children of its own and a way to answer.

    Every subclass is registered as it is defined, with the consumer and
    producer below: mumulib finds both by exact type, so Resource being
    registered would not reach a subclass. Resource is registered too.

    Its state is a dict, given to the constructor: Resource({"name": "Ada"}).
    It is the resource's JSON, /<resource>.json, read-only -- written only
    by its handlers -- and what a template's slots are filled from when
    there is no slot_ for them. The
    request a handler is given is another thing, and is called request here
    to keep the two apart.

    It is Located: url is where it is published, without an extension --
    /editors/characters/c1 -- learnt when a request first reaches it, and
    None until then. Unlike the url slot, which is the request's own URL.

    And it is persistent. Its file, named by its URL in the app's data
    directory, is its state as JSON: when a request first reaches it, a file
    there is loaded as self.state, in place of the constructor's -- an
    existing file wins -- and with none, the constructor's state is kept,
    and answered from memory, until the first save makes one. A handler
    that changes the state saves it, with await self.save(): nothing else
    does, and a change not saved is gone when the process is.
    """

    template: Any = ""

    def __init__(self, state: dict[str, Any] | None = None) -> None:
        self.state: dict[str, Any] = {} if state is None else state

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        _register(cls)

    async def load(self) -> None:
        """Its file, if it has one, as self.state; else the state it has."""
        if self.file is None:
            return
        text = await read_file(self.file)
        if text is not None:
            self.state = json.loads(text)

    async def save(self) -> None:
        """Write self.state to its file, whole, as its .json answers.

        Atomic: the file is the state before or the state after, never part
        of either. A resource no request has reached yet has no file, and
        nowhere to be saved: saving one is an error.
        """
        if self.file is None:
            raise RuntimeError(
                f"{type(self).__name__} has no file to be saved in: a request "
                "has not reached it, or the app has no data directory"
            )
        plain(self.state, self.url or type(self).__name__)
        # The state as it is now, made on the loop; written in a thread
        text = json.dumps(self.state, default=custom_serializer)
        await write_file(self.file, text)

    async def get_child(self, segments: list[str], request: State, send: Send) -> Any:
        """The child the next segment names, its child_ attribute, or None.

        The prefix keeps what can be reached to what was meant to be:
        /__class__.html is child___class__, which is nothing.
        """
        return getattr(self, f"child_{segments[0]}", None)

    def cached_for(self, segments: list[str], state: State) -> bool:
        """A GET of its .json, when that is its state -- Resource's own
        handle_GET -- is its file's, and cached by it; what it computes, its
        page and a subclass's own JSON, is not."""
        return (
            not segments
            and state.get("method") == "GET"
            and state.get("extension") in ("json", "xml")
            and type(self).handle_GET is Resource.handle_GET
        )

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
        """Its state, as JSON or XML; as HTML its template, a parsed one filled from
        slot_ names and the state, or a string of it, the resource's own
        markup. As anything else it is not found: a page is not text."""
        extension = request.get("extension", "html")
        if extension in ("json", "xml"):
            plain(self.state, self.url or type(self).__name__)
            # As XML, named by what it is: <Character type="object">
            if extension == "xml":
                return XmlOf(self.state, type(self).__name__)
            return self.state
        if extension != "html":
            raise NotFoundResponse()
        if isinstance(self.template, Stan):
            return await self.fill(self.template, request)
        if isinstance(self.template, str):
            return Markup(self.template)
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

    def slot_url(self, request: State) -> str:
        """The url slot: this request's own URL. A form with
        attr="action=url" posts back to the page it is on, its resource's
        handle_POST; a subclass's slot_url, or nothing using url, and this
        is not used."""
        return str(request.get("url", ""))

    def form(self, request: State) -> Form:
        """What the request's form posted -- or its JSON body sent, if an
        object -- by name; empty if neither."""
        body = request.get("parsed_body")
        return Form(cast(dict[str, Any], body) if isinstance(body, dict) else {})

    def pattern(self, name: str, /, **slots: Any) -> Stan:
        """A copy of the template's pattern name, data-pat, with slots
        filled: one item for a list, say."""
        if not isinstance(self.template, Stan):
            raise TypeError("only a parsed template has patterns")
        copy = self.template.clone_pat(name, **slots)
        if copy is None:
            raise ValueError(f"the template has no pattern {name!r}")
        return copy

    async def handle_POST(self, request: State) -> Any:
        self.refuse()

    async def handle_PUT(self, request: State) -> Any:
        self.refuse()

    async def handle_PATCH(self, request: State) -> Any:
        self.refuse()

    async def handle_DELETE(self, request: State) -> Any:
        self.refuse()

    def allowed(self) -> list[str]:
        """The methods this resource answers: GET and HEAD, and those it
        handles. A HEAD is answered as a GET, so there is no handle_HEAD."""
        return [
            method
            for method in METHODS
            if method in ("GET", "HEAD")
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
        for _, attrslot in attr_slots(child):
            yield attrslot
        yield from _slot_names(child)


def _register(cls: type[Resource]) -> None:
    add_consumer(cls, consume_resource, own_methods=True)
    add_producer(cls, produce_resource)


_register(Resource)
