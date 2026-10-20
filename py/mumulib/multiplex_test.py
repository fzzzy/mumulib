"""The event stream hub, over HTTP, against a server of the tests' own: two
EventSources, a JSON resource, and a stream or two written by hand."""

import asyncio
import socket
import tempfile
import threading
import time
import unittest
from typing import Any
from unittest import mock

import httpx2
import uvicorn

from mumulib import multiplex, streams
from mumulib.multiplex import (
    HUB,
    MOST_TOPICS,
    Hub,
    labelled,
    multiplexed,
    origin,
    where,
)
from mumulib.mumutypes import Receive, Scope, Send
from mumulib.server import EventSource, consumers_app

news = EventSource()
weather = EventSource()


async def by_hand(scope: Scope, receive: Receive, send: Send, body: bytes) -> None:
    """A stream that says body, and ends."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/event-stream")],
        }
    )
    await send({"type": "http.response.body", "body": body})


def outer(inner: Any, loops: list[asyncio.AbstractEventLoop]) -> Any:
    """The tests' server: two streams of its own, and the app; and its event
    loop, kept as it starts, to put on its EventSources in, as put must be."""

    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        if not loops:
            loops.append(asyncio.get_running_loop())
        if scope["type"] == "http" and scope["path"] == "/named.sse":
            # Named events, a comment, an event of two lines, one with no
            # data, an id, a retry: that is no number and then a short one:
            # it ends, and is subscribed to again
            await by_hand(
                scope,
                receive,
                send,
                b": a comment\nretry: soon\nretry: 50\nid: 7\nevent: turn\ndata: {}\n\n"
                b"data: one\ndata: two\n\nevent: nothing\n\n",
            )
            return
        if scope["type"] == "http" and scope["path"] == "/cookie.sse":
            cookie = dict(scope["headers"]).get(b"cookie", b"none")
            await by_hand(
                scope, receive, send, b"retry: 600000\ndata: " + cookie + b"\n\n"
            )
            return
        await inner(scope, receive, send)

    return app


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Served:
    """The tests' server, in a thread of its own, its hub naming origins."""

    def __init__(self, port: int | None = None, origins: tuple[str, ...] = ()) -> None:
        self.port = port or free_port()
        self.loops: list[asyncio.AbstractEventLoop] = []
        inner = consumers_app(
            {"news": news, "weather": weather, "plain": {"a": 1}},
            data=tempfile.mkdtemp(),
            multiplex=False,
        )
        app = multiplexed(outer(inner, self.loops), origins=origins)
        config = uvicorn.Config(
            app, host="127.0.0.1", port=self.port, log_level="error"
        )
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        for _ in range(250):
            if self.server.started:
                break
            time.sleep(0.02)

    async def put(self, source: EventSource, item: Any) -> None:
        """item put on source once the hub is listening to it."""
        for _ in range(250):
            if source.listeners:
                break
            await asyncio.sleep(0.02)

        async def put() -> None:
            source.put(item)

        asyncio.run_coroutine_threadsafe(put(), self.loops[0]).result(5)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


async def read(lines: Any, count: int, wait: float = 5) -> list[tuple[str, str]]:
    """The next count events a page hears: each its name and its data."""
    found: list[tuple[str, str]] = []
    name, data = "", list[str]()

    async def go() -> None:
        nonlocal name, data
        async for line in lines:
            if not line:
                if data:
                    found.append((name, "\n".join(data)))
                name, data = "", []
                if len(found) == count:
                    return
                continue
            field, _, value = line.partition(":")
            value = value.removeprefix(" ")
            if field == "event":
                name = value
            elif field == "data":
                data.append(value)

    await asyncio.wait_for(go(), wait)
    return found


class TestTheHub(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.served = Served()
        cls.base = f"http://127.0.0.1:{cls.served.port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.served.stop()

    async def asyncSetUp(self) -> None:
        self.client = httpx2.AsyncClient(timeout=httpx2.Timeout(10))

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def stream(self, *topics: str, cookie: str | None = None) -> Any:
        query = "&".join(f"topic={t}" for t in topics)
        headers = {"cookie": cookie} if cookie else {}
        request = self.client.build_request(
            "GET", f"{self.base}{HUB}?{query}", headers=headers
        )
        response = await self.client.send(request, stream=True)
        self.addAsyncCleanup(response.aclose)
        return response

    async def test_each_topic_is_heard_labelled_on_one_stream(self) -> None:
        response = await self.stream("news.sse", "weather.sse")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.headers["content-type"].startswith("text/event-stream")
        )
        lines = response.aiter_lines()
        opened = await read(lines, 4)
        # Each opened, and each EventSource's own first ping
        self.assertCountEqual(
            opened,
            [
                ("news.sse open", ""),
                ("news.sse ping", "{}"),
                ("weather.sse open", ""),
                ("weather.sse ping", "{}"),
            ],
        )
        await self.served.put(news, {"headline": "hub built"})
        self.assertEqual(
            await read(lines, 1), [("news.sse message", '{"headline": "hub built"}')]
        )
        await self.served.put(weather, "rain")
        self.assertEqual(await read(lines, 1), [("weather.sse message", '"rain"')])

    async def test_named_events_keep_their_names_and_an_ended_topic_comes_back(
        self,
    ) -> None:
        response = await self.stream("named.sse")
        lines = response.aiter_lines()
        heard = await read(lines, 6)
        self.assertEqual(
            heard,
            [
                ("named.sse open", ""),
                ("named.sse turn", "{}"),
                ("named.sse message", "one\ntwo"),
                # Ended, and subscribed to again after its retry: of 50ms
                ("named.sse open", ""),
                ("named.sse turn", "{}"),
                ("named.sse message", "one\ntwo"),
            ],
        )

    async def test_a_topic_that_is_no_stream_says_so_and_the_rest_go_on(self) -> None:
        response = await self.stream("missing.sse", "plain.json", "news.sse")
        lines = response.aiter_lines()
        heard = await read(lines, 4)
        self.assertCountEqual(
            heard,
            [
                ("missing.sse error", "404"),
                ("plain.json error", "200"),
                ("news.sse open", ""),
                ("news.sse ping", "{}"),
            ],
        )
        await self.served.put(news, "still here")
        self.assertEqual(await read(lines, 1), [("news.sse message", '"still here"')])

    async def test_the_pages_cookie_goes_to_its_own_origin(self) -> None:
        response = await self.stream("cookie.sse", cookie="who=me")
        heard = await read(response.aiter_lines(), 2)
        self.assertEqual(
            heard, [("cookie.sse open", ""), ("cookie.sse message", "who=me")]
        )

    async def test_another_origin_is_refused_unless_named(self) -> None:
        # localhost and 127.0.0.1 are other origins to each other, as a
        # browser has them
        elsewhere = f"http://localhost:{self.served.port}/news.sse"
        response = await self.stream(elsewhere, f"{HUB.lstrip('/')}?topic=news.sse")
        heard = await read(response.aiter_lines(), 2)
        self.assertCountEqual(
            heard,
            [
                (f"{elsewhere} error", "403"),
                (f"{HUB.lstrip('/')}?topic=news.sse error", "400"),
            ],
        )

    async def test_a_stream_that_cannot_be_is_400(self) -> None:
        for query in ["", "topic=", "topic=a%20b.sse"]:
            response = await self.client.get(f"{self.base}{HUB}?{query}")
            self.assertEqual(response.status_code, 400, query)
        many = "&".join(f"topic=t{n}.sse" for n in range(MOST_TOPICS + 1))
        response = await self.client.get(f"{self.base}{HUB}?{many}")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"at most 32", response.content)

    async def test_a_topic_named_twice_is_followed_once(self) -> None:
        response = await self.stream("weather.sse", "weather.sse")
        lines = response.aiter_lines()
        opened = await read(lines, 2)
        self.assertEqual(opened, [("weather.sse open", ""), ("weather.sse ping", "{}")])
        await self.served.put(weather, "sun")
        await self.served.put(weather, "snow")
        heard = await read(lines, 2)
        self.assertEqual(
            heard, [("weather.sse message", '"sun"'), ("weather.sse message", '"snow"')]
        )

    async def test_everything_else_is_the_apps(self) -> None:
        response = await self.client.get(f"{self.base}/plain.json")
        self.assertEqual(response.json(), {"a": 1})


class TestAnotherOrigin(unittest.IsolatedAsyncioTestCase):
    async def test_a_named_origin_is_reached_without_the_pages_cookie(self) -> None:
        # The same server, named for its other origin -- localhost, where the
        # page asked 127.0.0.1 -- allowed, but not sent the page's cookie,
        # which is its own server's
        port = free_port()
        served = Served(port, origins=(f"http://localhost:{port}",))
        try:
            async with httpx2.AsyncClient(timeout=10) as client:
                topic = f"http://localhost:{port}/cookie.sse"
                request = client.build_request(
                    "GET",
                    f"http://127.0.0.1:{port}{HUB}?topic={topic}",
                    headers={"cookie": "who=me"},
                )
                response = await client.send(request, stream=True)
                heard = await read(response.aiter_lines(), 2)
                await response.aclose()
            self.assertEqual(
                heard, [(f"{topic} open", ""), (f"{topic} message", "none")]
            )
        finally:
            served.stop()

    async def test_a_server_not_there_is_tried_again_not_given_up(self) -> None:
        nowhere = free_port()
        served = Served(origins=(f"http://127.0.0.1:{nowhere}",))
        try:
            with mock.patch.object(multiplex, "RETRY", 0.05):
                async with httpx2.AsyncClient(timeout=10) as client:
                    topic = f"http://127.0.0.1:{nowhere}/news.sse"
                    request = client.build_request(
                        "GET",
                        f"http://127.0.0.1:{served.port}{HUB}?topic={topic}&topic=news.sse",
                    )
                    response = await client.send(request, stream=True)
                    # Only the reachable one is heard: the other says no error
                    heard = await read(response.aiter_lines(), 2)
                    await response.aclose()
            self.assertEqual(heard, [("news.sse open", ""), ("news.sse ping", "{}")])
        finally:
            served.stop()


class TestTheParts(unittest.IsolatedAsyncioTestCase):
    def test_an_event_is_labelled_with_its_topic(self) -> None:
        self.assertEqual(
            labelled("api/news.sse", "message", ["a", "b"]),
            b"event: api/news.sse message\ndata: a\ndata: b\n\n",
        )

    def test_an_origin_is_its_scheme_host_and_port(self) -> None:
        self.assertEqual(
            origin("HTTP://Example.com:8080/a.sse?x"), "http://example.com:8080"
        )

    def test_where_the_hub_is_is_as_the_page_asked_for_it(self) -> None:
        scope = {"scheme": "http", "headers": [(b"host", b"h:1")], "root_path": "/cb"}
        self.assertEqual(where(scope), "http://h:1/cb/")
        self.assertEqual(where({"server": ("s", 2)}), "http://s:2/")
        self.assertEqual(where({"server": ("s", None)}), "http://s/")
        self.assertEqual(where({}), "http://localhost/")

    def test_a_page_too_far_behind_is_closed(self) -> None:
        hub = Hub({}, ["a.sse"], frozenset(), max_backlog=1)
        hub.put(b"one")
        hub.put(b"two")
        self.assertIs(hub.buffer.get_nowait(), streams.CLOSE)

    async def test_a_quiet_stream_is_pinged_and_one_closed_ends(self) -> None:
        sent: list[dict[str, Any]] = []
        received: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        async def receive() -> dict[str, Any]:
            return await received.get()

        hub = Hub({}, [], frozenset(), max_backlog=10)
        with mock.patch.object(multiplex, "PING", 0.02):
            serving = asyncio.ensure_future(hub.serve(receive, send))
            for _ in range(100):
                if any(m.get("body") == b": ping\n\n" for m in sent):
                    break
                await asyncio.sleep(0.01)
            streams.close(hub.buffer)
            await asyncio.wait_for(serving, 2)
        self.assertIn(b": ping\n\n", [m.get("body") for m in sent])
        self.assertNotIn(hub.buffer, streams.open_streams)

    async def test_a_page_gone_ends_its_stream(self) -> None:
        received: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

        async def send(message: dict[str, Any]) -> None:
            pass

        async def receive() -> dict[str, Any]:
            return await received.get()

        hub = Hub({}, [], frozenset(), max_backlog=10)
        serving = asyncio.ensure_future(hub.serve(receive, send))
        await asyncio.sleep(0.05)
        await received.put({"type": "http.disconnect"})
        await asyncio.wait_for(serving, 2)
        self.assertNotIn(hub.buffer, streams.open_streams)
