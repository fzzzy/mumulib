"""A site served from files: an open file, and a directory.

    make server SERVER=files

The dict's index is a file object, as open() gives it, so / is index.html.
Its "static" entry is a pathlib.Path to a directory, so /static/style.css is
the file static/style.css -- the URL's extension part of the name, and the
type it is served as. Nothing outside the directory, and nothing hidden in
it, is found. A directory lists what is in it: /static/ as links, and
/static.json as {name: URL}.

Its "data" entry is a dict with a dict in it, listed the same way: /data/
links /data/motto.txt and /data/more/, whose own index links its parent,
/data/, and /data/more/list/. /data/page.html is a Markup, its HTML, linked
as .html where the strings are .txt. /data.json is the whole of it, as JSON.

The whole of it is in GetOnly: nothing but GET gets in.
"""

import pathlib

from mumulib import consumers, server, tags

SITE = pathlib.Path(__file__).parent / "files"

app = server.consumers_app(
    consumers.GetOnly(
        {
            # Read afresh from its name on every request, so it can be edited
            # while the server runs
            "index": open(SITE / "index.html", "rb"),
            "static": SITE / "static",
            # Plain data, nested: its slash lists it as a directory's is,
            # each dict its own index, and each string or number its text
            "data": {
                "motto": "Served from files, and from a dict",
                "answer": 42,
                # HTML of the program's own, at .html alone: a plain string
                # is text, never markup
                "page": tags.Markup("<h1>A page</h1><p>Markup, in a dict.</p>"),
                "more": {"deeper": "Down a level", "list": ["one", "two"]},
            },
        }
    )
)
