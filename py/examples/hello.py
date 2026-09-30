"""The smallest mumulib server: a dict whose index is one string.

    make server                       # this one; SERVER=<name> for another

The dict is the site, and its "index" entry is what / serves, as HTML:

    /             Hello, world!       text/html

/ is the only URL: an index is its slash, and the root has no name of its
own for data. files.py shows extensions choosing the type.

A published dict can be changed through its URLs -- PUT writes an entry and
DELETE removes one -- so this one is wrapped in GetOnly, which hands GET on
to the dict and refuses anything else.
"""

from mumulib.consumers import GetOnly
from mumulib.server import consumers_app

app = consumers_app(GetOnly({"index": "Hello, world!"}))
