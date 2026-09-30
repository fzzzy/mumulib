"""The smallest mumulib server: a dict whose index is one string.

    make server                       # this one; SERVER=<name> for another

The dict is the site, and its "index" entry is what / and every index URL
serve. They differ only in their extension, which is the type it comes back
as:

    /             Hello, world!       text/html (/ is /index.html)
    /index.txt    Hello, world!       text/plain
    /index.json   "Hello, world!"     application/json

A published dict can be changed through its URLs -- PUT writes an entry and
DELETE removes one -- so this one is behind a guard that lets only GET in.
"""

from mumulib.mumutypes import ASGIApp, Receive, Scope, Send
from mumulib.server import consumers_app


def get_only(app: ASGIApp) -> ASGIApp:
    """`app`, answering anything but GET with 405 Method Not Allowed."""

    async def guarded(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] != "GET":
            await send(
                {
                    "type": "http.response.start",
                    "status": 405,
                    "headers": [
                        (b"allow", b"GET"),
                        (b"content-type", b"text/plain; charset=UTF-8"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": b"Only GET\n"})
            return
        await app(scope, receive, send)

    return guarded


app = get_only(consumers_app({"index": "Hello, world!"}))
