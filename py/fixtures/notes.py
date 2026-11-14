"""Notes: a Vite page, served by Python, and the data it reads and writes.

    make run SERVER=notes          then http://127.0.0.1:5758/
    make production SERVER=notes   the same, built, without Vite running

The page is ts/pages/notes/, a Vite entry: Page("notes/index.html") serves
its HTML exactly as Vite made it. Python does not fill it; past the HTML the
page is TypeScript's, and asks the tree for what it shows. Two plain objects
are published, and nothing else: the notes, a dict kept in a file, and who
is here, a dict kept only in memory.

    GET    /                         the page
    GET    /notes.json               the notes, a Persist: its file, as it is
    PUT    /notes/k3f9.json          {"text": "Milk", "order": "a1"}: added,
                                     and the file written
    PUT    /notes/k3f9/order.json    "a0V": moved, and written
    PUT    /notes/k3f9/text.json     "Oat milk": edited, and written
    DELETE /notes/k3f9.json          removed, and written
    GET    /presence.json            who is here, by a player's id
    PUT    /presence/p7.json         {"name": ..., "color": ..., "focus":
                                     "k3f9"}, with Authorization: Bearer
                                     <key>: here, and seen now
    DELETE /presence/p7.json         with the same key: the page closed
    GET    /mumulib/changes.sse      /notes or /presence, as each write to
                                     them is made

Each note is named by an id the page makes, and never renumbered: its
place is its order, a string, and the notes are shown sorted by it and then
by id. Moving a note writes its order alone -- a string between its new
neighbours' -- so a write never touches another note, and two people's
writes clash only over one note.

The notes need no code: whatever is written is kept. Who is here does --
the server must say when each player was seen, by its own clock, not each
page's, and forget a player not seen for a minute. That is a Resource: the
presence, which keeps a plain dict of who is here as its state, and a
Player below it for each id, which keeps the server's rules and hands the
keeping to that dict. A page makes a key for its player and sends it with
every write, and only a write with the key the player was first put with
is let through: anyone can see who is here, and no page can move or remove
another's player. Neither is ever saved, so who is here is not kept across
a restart. Each page puts its player as its focus moves and every thirty
seconds, and deletes it as it closes.

The page binds both, with mumulib's sync.bind: it fetches each into its
state, and again whenever it is announced, so every page open shows
everyone's notes and everyone. A write is a request, and nothing else: the
page does not change its own copy, and shows its own write when it is
announced, as anyone's.

make run sets MUMULIB_DEVELOPMENT=1 and starts the pages' Vite dev server on
5757: the page is then asked of it, and the URLs Vite writes in it name it
in full, so the browser loads the TypeScript from Vite and reloads as it
changes. make production builds the pages into ts/build/pages, and Python
serves them, and everything Vite built, under /mumulib-vite/.

The notes are kept in var/data/notes.json. Delete it to start again.
"""

import pathlib
import time
from typing import Any

from mumulib import mumutypes, persist, server, static
from mumulib.resource import Resource

# Where Vite builds the pages: ts/build/pages in the repository
PAGES = pathlib.Path(__file__).resolve().parents[2] / "ts" / "build" / "pages"

notes = persist.Persist(
    {
        "first": {"text": "Write the Vite example", "order": "a"},
        "second": {"text": "Run it built, in production", "order": "b"},
    }
)

# How long a player not seen is still here
STALE_MS = 60_000


class Presence(Resource):
    """Who is here: each player by id, as its page last put it, and when
    the server last heard from it. Its state is the plain dict of them --
    GET /presence.json is Resource's own answer -- and each player's key is
    kept beside it, never shown."""

    def __init__(self) -> None:
        super().__init__()
        self.keys: dict[str, str] = {}

    async def get_child(
        self, segments: list[str], request: dict[str, Any], send: Any
    ) -> Player:
        # /presence/p7.json: the player p7, here or not yet
        return Player(self, segments[0])

    def forget_quiet(self, now: int) -> None:
        """Forget whoever has not been seen for a minute."""
        for player, entry in list(self.state.items()):
            if now - entry["seen"] >= STALE_MS:
                del self.state[player]
                del self.keys[player]


class Player(Resource):
    """One player, written only with the key its first PUT gave it:
    Authorization: Bearer <key>, on every PUT and DELETE after."""

    def __init__(self, presence: Presence, player: str) -> None:
        super().__init__(presence.state.get(player, {}))
        self.presence, self.player = presence, player

    def check_key(self, request: dict[str, Any]) -> None:
        """Refuse a request without this player's key, once it has one; and
        a key given as the first, the key it has from then on."""
        auth = request["headers"].get("authorization", "")
        key = auth.removeprefix("Bearer ") if auth.startswith("Bearer ") else ""
        if not key:
            raise mumutypes.HTTPResponse(401, "Send Authorization: Bearer <key>\n")
        if self.presence.keys.setdefault(self.player, key) != key:
            raise mumutypes.HTTPResponse(403, "That is another page's player.\n")

    async def handle_PUT(self, request: dict[str, Any]) -> dict[str, Any]:
        now = int(time.time() * 1000)
        # Forgetting the quiet first: a key a forgotten player had is free
        self.presence.forget_quiet(now)
        form = self.form(request)
        name, color = form.text("name"), form.text("color")
        if not name or not color:
            raise mumutypes.HTTPResponse(400, "A player needs a name and a color.\n")
        self.check_key(request)
        focus = form.fields.get("focus")
        self.state = {
            "name": name[:60],
            "color": color[:32],
            "focus": focus if isinstance(focus, str) else None,
            # By the server's clock, not the page's
            "seen": now,
        }
        self.presence.state[self.player] = self.state
        return self.state

    async def handle_DELETE(self, request: dict[str, Any]) -> None:
        if self.player not in self.presence.state:
            raise mumutypes.HTTPResponse(404, "No such player.\n")
        self.check_key(request)
        del self.presence.state[self.player]
        del self.presence.keys[self.player]
        raise mumutypes.HTTPResponse(204, "")


presence = Presence()

app_root = {
    "index": static.Page("notes/index.html"),
    "notes": notes,
    "presence": presence,
}

# Every change announced on it: the page binds the notes and the presence,
# and fetches each again when a write to it, anyone's, is announced
changes = server.EventSource()

app = server.consumers_app(app_root, changes=changes, vite=PAGES)
