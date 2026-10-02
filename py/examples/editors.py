"""Editors: characters, parties and deploys, each edited in a plain HTML form.

    make run SERVER=editors      then http://127.0.0.1:8001/editors/

Every page is built here, in Stan, with tags.page, and each object is a
Resource whose state is its data -- the JSON of it, and what its edit page's
slots are filled from. A form posts to the object's own URL, Resource's url
slot, and its handle_POST reads it with self.form, checks it, keeps it, and
answers 303 See Other, back to /editors/:

    GET  /editors/                          the three tables
    GET  /editors/characters/c1.html        a character's edit page
    POST /editors/characters/c1.html        name=...&prompt=...&agent_args=...
    GET  /editors/parties/p1.html           a party's, its members a <select>
    POST /editors/parties/p1.html           name=...&members[]=c1&members[]=c2
    GET  /editors/deploys/d1.html           a deploy's, its status shown
    POST /editors/deploys/d1.html           name=...&party=p2
    GET  /editors/characters.json           {"c1": {"name": ..., ...}, ...}
    GET  /editors/characters/c1/state.json  {"name": ..., ...}, read-only
    GET  /editors/style.css                 editors/style.css
    GET  /mumulib/changes.sse               the URL of each change, as it is made
    GET  /mumulib/live.js                   the script that follows them

Each object has an id that never changes, so its URL does not either, and
renaming is a post to the URL it already had. A party's members and a
deploy's party are ids, so they follow a rename.

An edit link is a link, and a form a form. Every page links mumulib's
live.js, which consumers_app serves, given changes. Each row of the index
watches its own object, and each edit page's heading watches the page's own
URL: when anyone, from any page, changes an object, the pages watching it
are fetched again and those elements alone put in place.
"""

from pathlib import Path
from typing import Any

from mumulib.mumutypes import HTTPResponse, State
from mumulib.resource import Resource
from mumulib.server import EventSource, consumers_app
from mumulib.tags import Stan, page
from mumulib.tags import every as t

STYLESHEET = "/editors/style.css"
NAV = t.p[t.a(href="/editors/")["Editors"]]


def buttons() -> Stan:
    """Save posts the form; Cancel goes back, saving nothing."""
    return t.p[t.button["Save"], " ", t.a(href="/editors/")["Cancel"]]


def edit_page(title: str, *fields: Any) -> Stan:
    """An edit page: the object's name, kept up to date, and a form posting
    to its own URL, Resource's url slot. The heading is live with no URL, so
    it watches the page's own -- the object's -- and someone else's edit of
    the object shows here; the form, being typed in, is not."""
    return page(
        title,
        NAV,
        t.h1(id="heading", live=True, slt="name")["A name"],
        t.form(attr="action=url", method="post")[t.h2[title], *fields, buttons()],
        stylesheets=[STYLESHEET],
        live=True,
    )


def name_field() -> Stan:
    return t.label[
        "Name", t.input(attr="value=name", type="text", name="name", required=True)
    ]


class Character(Resource):
    """A character: state {"name", "prompt", "agent_args"}."""

    template = edit_page(
        "Edit character",
        name_field(),
        t.label["System prompt", t.textarea(slt="prompt", name="prompt")["A prompt"]],
        t.label[
            "Agent args",
            t.input(attr="value=agent_args", type="text", name="agent_args"),
        ],
    )

    async def handle_POST(self, request: State) -> Any:
        form = self.form(request)
        if not form.text("name"):
            raise HTTPResponse(400, "A character needs a name.\n")
        self.state.update(
            name=form.text("name"),
            prompt=form.text("prompt"),
            agent_args=form.text("agent_args"),
        )
        self.see_other("/editors/")


class Party(Resource):
    """A party: state {"name", "members"}, the members character ids."""

    template = edit_page(
        "Edit party",
        name_field(),
        t.label[
            "Members",
            t.select(slt="member_options", name="members[]", multiple=True),
        ],
    )

    def slot_member_options(self, request: State) -> list[Stan]:
        # One option for each character, chosen if it is a member
        return [
            t.option(value=cid, selected=cid in self.state["members"])[c.state["name"]]
            for cid, c in characters.items()
        ]

    async def handle_POST(self, request: State) -> Any:
        form = self.form(request)
        # members[] is a list, and none chosen sends none: []
        members = form.texts("members")
        if not form.text("name"):
            raise HTTPResponse(400, "A party needs a name.\n")
        unknown = [cid for cid in members if cid not in characters]
        if unknown:
            raise HTTPResponse(400, f"No character {unknown[0]!r}.\n")
        self.state.update(name=form.text("name"), members=members)
        self.see_other("/editors/")


class Deploy(Resource):
    """A deploy: state {"name", "party", "status"}. Its status is the
    server's, shown on its page and not taken from any form."""

    template = edit_page(
        "Edit deploy",
        name_field(),
        t.label["Party", t.select(slt="party_options", name="party")],
        t.p["Status: ", t.span(slt="status")["running"]],
    )

    def slot_party_options(self, request: State) -> list[Stan]:
        return [
            t.option(value=pid, selected=pid == self.state["party"])[p.state["name"]]
            for pid, p in parties.items()
        ]

    async def handle_POST(self, request: State) -> Any:
        form = self.form(request)
        name, party = form.text("name"), form.text("party")
        if not name:
            raise HTTPResponse(400, "A deploy needs a name.\n")
        if party not in parties:
            raise HTTPResponse(400, f"No party {party!r}.\n")
        self.state.update(name=name, party=party)
        self.see_other("/editors/")


characters: dict[str, Character] = {
    "c1": Character(
        {
            "name": "Code Reviewer",
            "prompt": "You review code for correctness first, then clarity.",
            "agent_args": "--ant --notools",
        }
    ),
    "c2": Character(
        {
            "name": "Researcher",
            "prompt": "You find sources, and say which claims they support.",
            "agent_args": "--oai",
        }
    ),
    "c3": Character(
        {
            "name": "Shell Helper",
            "prompt": "You suggest one shell command at a time, and explain it.",
            "agent_args": "--ant --shell",
        }
    ),
}

parties: dict[str, Party] = {
    "p1": Party({"name": "Reviewers", "members": ["c1", "c2"]}),
    "p2": Party({"name": "Operators", "members": ["c3"]}),
}

deploys: dict[str, Deploy] = {
    "d1": Deploy({"name": "Nightly review", "party": "p1", "status": "running"}),
    "d2": Deploy({"name": "Ops on call", "party": "p2", "status": "stopped"}),
}


def row(kind: str, key: str) -> dict[str, str]:
    """A row's own slots: its id, the object it watches, and its edit link.
    Each row is live, and refreshed when its own object changes."""
    return {
        "row_id": f"{kind}-{key}",
        "watch": f"/editors/{kind}/{key}",
        "edit": f"/editors/{kind}/{key}.html",
    }


class Editors(Resource):
    """/editors/: a table of each kind, every row a copy of its pattern. Each
    row is live, watching its own object, kept up to date by live.js."""

    template = page(
        "Editors",
        NAV,
        t.table(id="characters")[
            t.caption["Characters"],
            t.thead[t.tr[t.th["Name"], t.th["Prompt"], t.th["Agent args"]]],
            t.tbody(slt="character_rows")[
                t.tr(pat="character_row", attr={"id": "row_id", "data-live": "watch"})[
                    t.td[t.a(slt="name", attr="href=edit")],
                    t.td(slt="prompt"),
                    t.td[t.code(slt="agent_args")],
                ]
            ],
        ],
        t.table(id="parties")[
            t.caption["Parties"],
            t.thead[t.tr[t.th["Name"], t.th["Members"]]],
            t.tbody(slt="party_rows")[
                t.tr(pat="party_row", attr={"id": "row_id", "data-live": "watch"})[
                    t.td[t.a(slt="name", attr="href=edit")],
                    t.td(slt="members"),
                ]
            ],
        ],
        t.table(id="deploys")[
            t.caption["Deploys"],
            t.thead[t.tr[t.th["Name"], t.th["Party"], t.th["Status"]]],
            t.tbody(slt="deploy_rows")[
                t.tr(pat="deploy_row", attr={"id": "row_id", "data-live": "watch"})[
                    t.td[t.a(slt="name", attr="href=edit")],
                    t.td(slt="party"),
                    t.td(slt="status"),
                ]
            ],
        ],
        stylesheets=[STYLESHEET],
        live=True,
    )

    def slot_character_rows(self, request: State) -> list[Stan]:
        return [
            self.pattern("character_row", **row("characters", cid), **c.state)
            for cid, c in characters.items()
        ]

    def slot_party_rows(self, request: State) -> list[Stan]:
        return [
            self.pattern(
                "party_row",
                **row("parties", pid),
                name=p.state["name"],
                members=", ".join(
                    characters[m].state["name"] for m in p.state["members"]
                ),
            )
            for pid, p in parties.items()
        ]

    def slot_deploy_rows(self, request: State) -> list[Stan]:
        return [
            self.pattern(
                "deploy_row",
                **row("deploys", did),
                name=d.state["name"],
                party=parties[d.state["party"]].state["name"],
                status=d.state["status"],
            )
            for did, d in deploys.items()
        ]


class Site(Resource):
    """/editors: every child a class attribute, child_<name> being found as
    any attribute is. Its slash is child_index, the tables; the rest are
    the three kinds, and the stylesheet, a file served as it is."""

    child_index = Editors()
    child_characters = characters
    child_parties = parties
    child_deploys = deploys
    child_style = Path(__file__).parent / "editors" / "style.css"


# Every change announced on it; consumers_app serves it, and live.js
changes = EventSource()

app = consumers_app({"editors": Site()}, changes=changes)
