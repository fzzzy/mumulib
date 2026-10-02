"""Notes: a Vite page, served by Python, and the data it reads and writes.

    make run SERVER=notes          then http://127.0.0.1:5959/
    make production SERVER=notes   the same, built, without Vite running

The page is ts/pages/notes/, a Vite entry: Page("notes/index.html") serves
its HTML exactly as Vite made it. Python does not fill it; past the HTML the
page is TypeScript's, and asks the tree for what it shows:

    GET    /                    the page
    GET    /notes.json          the notes, a Persist: its file, as it is
    PUT    /notes/last.json     "Milk": added, and the file written
    DELETE /notes/0.json        removed -- null in its place -- and written
    GET    /mumulib/changes.sse /notes, as each write to them is made

The page binds the notes, with mumulib's sync.bind: it fetches /notes.json
into its state, and again whenever /notes is announced, so every page open
shows everyone's notes. A write is a request, and nothing else: the page
does not change its own copy, and shows its own write when it is announced,
as anyone's.

make run sets MUMULIB_DEVELOPMENT=1 and starts the pages' Vite dev server on
5757: the page is then asked of it, and the URLs Vite writes in it name it
in full, so the browser loads the TypeScript from Vite and reloads as it
changes. make production builds the pages into ts/build/pages, and Python
serves them, and everything Vite built, under /mumulib-vite/.

The notes are kept in var/data/notes.json. Delete it to start again.
"""

from pathlib import Path

from mumulib.persist import Persist
from mumulib.server import EventSource, consumers_app
from mumulib.static import Page

# Where Vite builds the pages: ts/build/pages in the repository
PAGES = Path(__file__).resolve().parents[2] / "ts" / "build" / "pages"

notes = Persist(["Write the Vite example", "Run it built, in production"])

app_root = {"index": Page("notes/index.html"), "notes": notes}

# Every change announced on it: the page binds the notes, and fetches them
# again when a write to them, anyone's, is announced
changes = EventSource()

app = consumers_app(app_root, changes=changes, vite=PAGES)
