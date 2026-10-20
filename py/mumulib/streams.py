"""What every event stream in the process shares: an EventSource's and the
hub's alike -- the set of those open, how one is told to end, and how one
waits for its client to go. The server ends them all as it stops."""

import asyncio
from typing import Any

from mumulib.mumutypes import Receive

__all__ = ["CLOSE", "close", "disconnected", "open_streams"]

# Stands in a stream's buffer for "this stream is over": put when its
# client has fallen too far behind to catch up, or the server is stopping
CLOSE = object()

# Every event stream open in the process, of every EventSource, and the hub's
open_streams: set[asyncio.Queue[Any]] = set()


def close(stream: asyncio.Queue[Any]) -> None:
    """Tell a stream to end: what it has not sent is dropped."""
    while not stream.empty():
        stream.get_nowait()
    stream.put_nowait(CLOSE)


async def disconnected(receive: Receive) -> None:
    """Returns when the client has gone: what it sends until then, if
    anything, is not for an event stream."""
    while (await receive())["type"] != "http.disconnect":
        pass
