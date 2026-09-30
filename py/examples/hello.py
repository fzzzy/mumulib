"""The smallest mumulib server: a dict whose index is one string.

    make server                       # this one; SERVER=<name> for another

The dict is the site, and its "index" entry is what / and every index URL
serve. They differ only in their extension, which is the type it comes back
as:

    /             Hello, world!       text/html (/ is /index.html)
    /index.txt    Hello, world!       text/plain
    /index.json   "Hello, world!"     application/json

A published dict can be changed through its URLs -- PUT writes an entry and
DELETE removes one -- so this one is behind mumulib's get_only, which lets
only GET in.
"""

from mumulib.server import consumers_app, get_only

app = get_only(consumers_app({"index": "Hello, world!"}))
