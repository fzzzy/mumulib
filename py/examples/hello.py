"""The smallest mumulib server: a dict whose index is one string.

    make server                       # this one; SERVER=<name> for another

The dict is the site, and its "index" entry is what / and every index URL
serve. They differ only in their extension, which is the type it comes back
as:

    /             Hello, world!       text/html (/ is /index.html)
    /index.txt    Hello, world!       text/plain
    /index.json   "Hello, world!"     application/json
"""

from mumulib.server import consumers_app

app = consumers_app({"index": "Hello, world!"})
