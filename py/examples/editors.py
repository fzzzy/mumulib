"""Editors: the data behind ts/examples/editors, a character, party and deploy
editor, each object edited in place.

    make run SERVER=editors      then http://127.0.0.1:8000/examples/editors/

The page is served by Vite with the rest of the TypeScript examples, and
Vite passes /editors on to this server. Everything is under /editors:

    GET  /editors/characters.json           {"c1": {"name": ..., "prompt": ...,
                                              "agent_args": ...}, ...}
    PUT  /editors/characters/c1.json        the whole character, replaced
    GET  /editors/parties.json              {"p1": {"name": ..., "members":
                                              ["c1", ...]}, ...}
    PUT  /editors/parties/p1.json           the whole party, replaced
    GET  /editors/deploys.json              {"d1": {"name": ..., "party": "p1",
                                              "status": "running"}, ...}
    PUT  /editors/deploys/d1.json           {"name": ..., "party": ...} only
    GET  /editors/changes.sse               the URL of each change, as it is made

Each object has an id that never changes, so its URL does not either:
renaming a character is a PUT to the URL it already had, and a party's
members are ids, so they follow it.

Characters and parties are plain dicts, published for reading and writing
alike: a PUT replaces an entry, whatever it holds. Deploys are guarded by a
Resource instead, since a deploy's status is the server's to say: a PUT may
change its name and its party, and is refused anything else.
"""

from typing import Any, cast

from mumulib.mumutypes import HTTPResponse, Send, State
from mumulib.resource import Resource
from mumulib.server import EventSource, consumers_app

characters: dict[str, Any] = {
    "c1": {
        "name": "Code Reviewer",
        "prompt": "You review code for correctness first, then clarity.",
        "agent_args": "--ant --notools",
    },
    "c2": {
        "name": "Researcher",
        "prompt": "You find sources, and say which claims they support.",
        "agent_args": "--oai",
    },
    "c3": {
        "name": "Shell Helper",
        "prompt": "You suggest one shell command at a time, and explain it.",
        "agent_args": "--ant --shell",
    },
}

parties: dict[str, Any] = {
    "p1": {"name": "Reviewers", "members": ["c1", "c2"]},
    "p2": {"name": "Operators", "members": ["c3"]},
}


class Deploy(Resource):
    """One deploy: read whole, and given a new name or party by PUT."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record

    async def handle_GET(self, state: State) -> Any:
        return self.record

    async def handle_PUT(self, state: State) -> Any:
        body = state.get("parsed_body")
        changes = cast(dict[str, Any], body) if isinstance(body, dict) else {}
        name, party = changes.get("name"), changes.get("party")
        if set(changes) - {"name", "party"} or not isinstance(name, str) or not name:
            raise HTTPResponse(400, 'Send {"name": a string, "party": an id}\n')
        if party not in parties:
            raise HTTPResponse(400, f"No party {party!r}\n")
        self.record["name"], self.record["party"] = name, party
        return self.record


class Deploys(Resource):
    """The deploys: their data whole at /editors/deploys.json, and each one
    at /editors/deploys/<id>.json, a Deploy over its record."""

    def __init__(self, records: dict[str, dict[str, Any]]) -> None:
        self.records = records

    async def get_child(self, segments: list[str], state: State, send: Send) -> Any:
        record = self.records.get(segments[0])
        return Deploy(record) if record is not None else None

    async def handle_GET(self, state: State) -> Any:
        return self.records


deploys = Deploys(
    {
        "d1": {"name": "Nightly review", "party": "p1", "status": "running"},
        "d2": {"name": "Ops on call", "party": "p2", "status": "stopped"},
    }
)

changes = EventSource()

app = consumers_app(
    {
        "editors": {
            "characters": characters,
            "parties": parties,
            "deploys": deploys,
            "changes": changes,
        }
    },
    changes=changes,
)
