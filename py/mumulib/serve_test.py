# pyright: standard
import asyncio
import sys
import unittest
from unittest import mock

from mumulib import serve


async def held(reader, writer):
    """A connection's handler that does not end: an event stream's."""
    await asyncio.sleep(3600)


async def a_server_with_a_client_connected():
    """A listening server, closed, with a client still connected to it and
    its handler going, as a browser's event stream is."""
    server = await asyncio.start_server(held, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    _, writer = await asyncio.open_connection("127.0.0.1", port)
    await asyncio.sleep(0.05)
    server.close()
    return server, writer


class TestShutdown(unittest.TestCase):
    def test_python_waits_on_the_client(self):
        # Why: the server's own wait_closed is not over while one is open
        async def go():
            server, writer = await a_server_with_a_client_connected()
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(serve._wait_closed(server), 0.3)
            writer.close()

        asyncio.run(go())

    def test_closing_the_clients_first_it_is_over_at_once(self):
        async def go():
            server, writer = await a_server_with_a_client_connected()
            await asyncio.wait_for(serve._wait_closed_closing_clients(server), 1)
            writer.close()

        asyncio.run(go())


class TestMain(unittest.TestCase):
    def test_it_is_hypercorns_command_line_with_that_shutdown(self):
        seen = []

        def hypercorn():
            seen.append(asyncio.Server.wait_closed)
            return 0

        with (
            mock.patch("hypercorn.__main__.main", hypercorn),
            mock.patch.object(asyncio.Server, "wait_closed", serve._wait_closed),
        ):
            self.assertEqual(serve.main(), 0)
        self.assertEqual(seen, [serve._wait_closed_closing_clients])

    def test_without_hypercorn_it_says_so(self):
        with (
            mock.patch.dict(sys.modules, {"hypercorn.__main__": None}),
            mock.patch("sys.stderr") as stderr,
        ):
            self.assertEqual(serve.main(), 1)
        self.assertIn(
            "Hypercorn", "".join(c.args[0] for c in stderr.write.call_args_list)
        )
