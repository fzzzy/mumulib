"""The smallest mumulib server: a dict whose index is one piece of HTML.

    make server                       # this one; SERVER=<name> for another

The dict is the site, and its "index" entry is what / serves, as HTML. It
is Markup, HTML of its own: a plain string is text, at .txt and .json, and
never served as HTML, where a visitor's could be markup.

    /             Hello, world!       text/html

/ is the only URL: an index is its slash, and the root has no name of its
own for data. files.py shows extensions choosing the type.

A published dict can be changed through its URLs -- PUT writes an entry and
DELETE removes one -- so this one is wrapped in GetOnly, which hands GET on
to the dict and refuses anything else.
"""

from mumulib import consumers, server, tags

app = server.consumers_app(consumers.GetOnly({"index": tags.Markup("Hello, world!")}))
