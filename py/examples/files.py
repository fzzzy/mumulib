"""A site served from files: an open file, and a directory.

    make server SERVER=files

The dict's index is a file object, as open() gives it, so / is index.html.
Its "static" entry is a pathlib.Path to a directory, so /static/style.css is
the file static/style.css -- the URL's extension part of the name, and the
type it is served as. Nothing outside the directory, and nothing hidden in
it, is found. A directory lists what is in it: /static/ as links, and
/static.json as {name: URL}.

The whole of it is in GetOnly: nothing but GET gets in.
"""

from pathlib import Path

from mumulib import consumers, server

SITE = Path(__file__).parent / "files"

app = server.consumers_app(
    consumers.GetOnly(
        {
            # Read afresh from its name on every request, so it can be edited
            # while the server runs
            "index": open(SITE / "index.html", "rb"),
            "static": SITE / "static",
        }
    )
)
