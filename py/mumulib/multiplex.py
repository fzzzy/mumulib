"""The event stream hub: a page's event streams over one connection.

    app = multiplexed(app)                      # consumers_app does it itself
    GET /mumulib/events.sse?topic=news.sse&topic=threads/t1/terminal.sse

A browser opens at most six connections to a host, and an event stream holds
one for as long as it is open: a page with several, beside another, has none
left for anything else, and hangs. Over the hub a page holds one.

Each topic is an event stream's URL, a relative one the app's own -- resolved
against where the hub is, below whatever prefix the app is mounted at -- and
an absolute one another server's. The hub subscribes to each over HTTP, as a
browser would, and sends each event it hears back on the page's one stream,
named for the topic and its own name, a space between:

    event: threads/t1/terminal.sse turn_ended
    data: {}

An unnamed event is the topic's "message". The hub adds two of its own: a
topic's "open", as it is subscribed to, and again each time it is subscribed
to again; and its "error", with the status as its data, for a topic that
answered anything but an event stream, which is not tried again. A topic
whose stream ends, or whose server cannot be reached, is subscribed to again,
after its retry: if it gave one. Every other topic goes on as it was, and so
does the page's stream.

A request to the hub's own origin carries the page's cookies and
authorization, so a topic answers the page as it would have directly.
Another origin is reached only if the app names it, origins=[...], and
without them. See design/multiplex.md.
"""

import asyncio
import urllib.parse
from collections.abc import Iterable
from typing import Any

import httpx2

from mumulib.mumutypes import ASGIApp, Receive, Scope, Send
from mumulib.streams import CLOSE, close, disconnected, open_streams

__all__ = ["HUB", "MOST_TOPICS", "multiplexed"]

# Where the hub is, below the app's prefix
HUB = "/mumulib/events.sse"

# How many topics one stream may name: a page has a handful
MOST_TOPICS = 32

# How long before a topic is subscribed to again, in seconds, unless it
# says, as an EventSource waits
RETRY = 2.0

# How often a quiet stream says it is there, in seconds: a page gone is
# found out when one cannot be sent
PING = 15.0

# The page's own headers a topic of its own origin is sent, as the page
# would have sent them
FORWARDED = (b"cookie", b"authorization")


def origin(url: str) -> str:
    """A URL's scheme, host and port, as a browser compares origins."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


def labelled(topic: str, name: str, lines: Iterable[str]) -> bytes:
    """An event as the page hears it: named for its topic and its own name."""
    data = "".join(f"data: {line}\n" for line in lines)
    return f"event: {topic} {name}\n{data}\n".encode()


def where(scope: Scope) -> str:
    """Where the hub is, as the page asked for it: the base a relative
    topic is resolved against."""
    headers = dict(scope.get("headers", []))
    host = headers.get(b"host", b"").decode()
    if not host:
        server = scope.get("server") or ("localhost", None)
        host = server[0] if server[1] is None else f"{server[0]}:{server[1]}"
    return f"{scope.get('scheme', 'http')}://{host}{scope.get('root_path', '')}/"


class Hub:
    """One page's stream: its topics followed, and what they say sent on."""

    def __init__(
        self,
        scope: Scope,
        topics: list[str],
        origins: frozenset[str],
        max_backlog: int,
    ) -> None:
        self.base = where(scope)
        self.own = origin(self.base)
        self.topics = topics
        self.origins = origins
        headers = dict(scope.get("headers", []))
        self.forwarded = {
            name.decode(): headers[name].decode()
            for name in FORWARDED
            if name in headers
        }
        self.buffer: asyncio.Queue[Any] = asyncio.Queue(maxsize=max_backlog)

    def put(self, event: bytes) -> None:
        """An event for the page; one that has fallen too far behind to catch
        up is told to close, and its EventSource reconnects."""
        try:
            self.buffer.put_nowait(event)
        except asyncio.QueueFull:
            open_streams.discard(self.buffer)
            close(self.buffer)

    async def follow(self, client: httpx2.AsyncClient, topic: str) -> None:
        """One topic, subscribed to, and again each time it ends, until it
        answers anything but a stream, or the page goes."""
        url = urllib.parse.urljoin(self.base, topic)
        target = origin(url)
        if target != self.own and target not in self.origins:
            self.put(labelled(topic, "error", ["403"]))
            return
        if target == self.own and urllib.parse.urlsplit(url).path.endswith(HUB):
            # The hub itself: a stream of streams, without end
            self.put(labelled(topic, "error", ["400"]))
            return
        headers = {"accept": "text/event-stream"}
        if target == self.own:
            headers |= self.forwarded
        retry = RETRY
        while True:
            try:
                async with client.stream("GET", url, headers=headers) as response:
                    kind = response.headers.get("content-type", "")
                    if response.status_code != 200 or not kind.startswith(
                        "text/event-stream"
                    ):
                        self.put(labelled(topic, "error", [str(response.status_code)]))
                        return
                    self.put(labelled(topic, "open", [""]))
                    retry = await self.relay(topic, response, retry)
            except httpx2.TransportError:
                # Not reached, or cut off: subscribed to again, as one ended
                pass
            await asyncio.sleep(retry)

    async def relay(self, topic: str, response: httpx2.Response, retry: float) -> float:
        """A topic's events, as its stream says them, each sent on labelled,
        until it ends: how long it asks to be waited for before the next."""
        name, data = "", list[str]()
        async for line in response.aiter_lines():
            if not line:
                # An event ends with a blank line, and one with no data is
                # none, as an EventSource has it
                if data:
                    self.put(labelled(topic, name or "message", data))
                name, data = "", []
                continue
            if line.startswith(":"):
                continue
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                name = value
            elif field == "data":
                data.append(value)
            elif field == "retry" and value.isdigit():
                retry = int(value) / 1000
        return retry

    async def serve(self, receive: Receive, send: Send) -> None:
        """The page's stream: each topic followed, and what they say sent,
        until the page goes, or is closed."""
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/event-stream; charset=UTF-8"),
                    (b"cache-control", b"no-cache"),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": b"retry: 2000\n\n",
                "more_body": True,
            }
        )
        open_streams.add(self.buffer)
        gone = asyncio.ensure_future(disconnected(receive))
        timeout = httpx2.Timeout(None, connect=10)
        async with httpx2.AsyncClient(timeout=timeout) as client:
            following = [
                asyncio.create_task(self.follow(client, topic)) for topic in self.topics
            ]
            # The next event, waited for across pings, and taken once it comes
            item = asyncio.ensure_future(self.buffer.get())
            try:
                while True:
                    done, _ = await asyncio.wait(
                        {item, gone}, timeout=PING, return_when=asyncio.FIRST_COMPLETED
                    )
                    if gone in done:
                        return
                    if item not in done:
                        await send(
                            {
                                "type": "http.response.body",
                                "body": b": ping\n\n",
                                "more_body": True,
                            }
                        )
                        continue
                    event = item.result()
                    if event is CLOSE:
                        return
                    item = asyncio.ensure_future(self.buffer.get())
                    await send(
                        {"type": "http.response.body", "body": event, "more_body": True}
                    )
            finally:
                open_streams.discard(self.buffer)
                gone.cancel()
                item.cancel()
                for task in following:
                    task.cancel()
                await asyncio.gather(*following, return_exceptions=True)


async def refuse(send: Send, why: str) -> None:
    """A stream that cannot be: 400, and why."""
    await send(
        {
            "type": "http.response.start",
            "status": 400,
            "headers": [(b"content-type", b"text/plain; charset=UTF-8")],
        }
    )
    await send({"type": "http.response.body", "body": f"{why}\n".encode()})


def multiplexed(
    app: ASGIApp, origins: Iterable[str] = (), max_backlog: int = 1000
) -> ASGIApp:
    """app, with the hub at /mumulib/events.sse, below its prefix: see the
    module's doc. origins are the other servers whose streams may be topics,
    each a scheme, host and port: "https://other.example"."""
    allowed = frozenset(origin(o) for o in origins)

    async def hubbed(scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] != "GET"
            or scope["path"].removeprefix(scope.get("root_path", "")) != HUB
        ):
            await app(scope, receive, send)
            return
        query = urllib.parse.parse_qs(scope.get("query_string", b"").decode())
        # Each once, however often it is named
        topics = list(dict.fromkeys(query.get("topic", [])))
        if not topics:
            await refuse(send, "a stream of no topics: name each as topic=")
            return
        if len(topics) > MOST_TOPICS:
            await refuse(send, f"at most {MOST_TOPICS} topics on one stream")
            return
        if any(not topic or any(c.isspace() for c in topic) for topic in topics):
            await refuse(send, "a topic is a URL: not empty, and no spaces")
            return
        await Hub(scope, topics, allowed, max_backlog).serve(receive, send)

    return hubbed
