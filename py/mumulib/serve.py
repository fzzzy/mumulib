"""Hypercorn, with a shutdown that does not wait on the browser.

    python -m mumulib.serve fixtures.notes:app --workers 0 \\
        --insecure-bind 127.0.0.1:5758 \\
        --bind 127.0.0.1:5759 --certfile dev.pem --keyfile dev-key.pem

Its command line is Hypercorn's own: plain HTTP on one port and HTTPS on
another, over which browsers speak HTTP/2 -- every request and event stream
of every tab on one connection, where HTTP/1.1 allows six.

Hypercorn shuts down by closing its listening sockets and awaiting each
asyncio server's wait_closed() -- which, since Python 3.12, waits for every
connection the server has open to close: a browser's idle keep-alive, a
page's event streams, a websocket, none of which a browser closes while the
page is open. Only after that would its graceful timeout begin, so with a
page open it never stops. Here the clients are closed first, and a shutdown
takes no longer than the graceful timeout.

To restart as Python changes, run it under watchfiles, one process --
--workers 0 -- so that the signal watchfiles sends reaches the app, whose
streams end on it, as consumers_app's do:

    watchfiles --filter python "python -m mumulib.serve ... --workers 0" py

Hypercorn's own --reload does not signal the app, and waits on its streams.
"""

import asyncio
import sys

_wait_closed = asyncio.Server.wait_closed


async def _wait_closed_closing_clients(self: asyncio.Server) -> None:
    """The server's connections closed, then waited for: at once."""
    self.close_clients()
    await _wait_closed(self)


def main() -> int:
    """Hypercorn's command line, served with this shutdown."""
    try:
        from hypercorn.__main__ import main as hypercorn
    except ImportError:
        print("mumulib.serve needs Hypercorn: pip install hypercorn", file=sys.stderr)
        return 1
    asyncio.Server.wait_closed = _wait_closed_closing_clients  # type: ignore[method-assign]
    return hypercorn()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
