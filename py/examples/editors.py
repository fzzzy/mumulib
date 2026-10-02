"""Editors: characters, parties and deploys, each edited in a plain HTML form.

    make run SERVER=editors      then http://127.0.0.1:5959/editors/

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
    GET  /editors/characters.json           {"c1": "/editors/characters/c1.json", ...}
    GET  /editors/characters/c1.json        {"name": ..., ...}, read-only
    GET  /editors/style.css                 editors/style.css
    GET  /mumulib/changes.sse               the URL of each change, as it is made
    GET  /mumulib/live.js                   the script that follows them

Each object is persistent: its state is kept in a file named by its URL,
var/data/editors/characters/c1.json, loaded the first time a request reaches
it, and written by its handle_POST, with await self.save(). Until then, the
state it was made with here is what it answers with. var/data is beside
where the server runs -- the repository's root, for make run -- and
deleting it starts again.

Each object has an id that never changes, so its URL does not either, and
renaming is a post to the URL it already had. A party's members and a
deploy's party are ids, so they follow a rename.

An edit link is a link, and a form a form. Every page links mumulib's
live.js, which consumers_app serves, given changes. Each row of the index
watches its own object, and each edit page's heading watches the page's own
URL: when anyone, from any page, changes an object, the pages watching it
are fetched again and those elements alone put in place.
"""

import pathlib
import typing

from mumulib import mumutypes, resource, server, tags

STYLESHEET = "/editors/style.css"
NAV = tags.text_content.p[tags.inline_text_semantics.a(href="/editors/")["Editors"]]


def buttons() -> tags.Stan:
    """Save posts the form; Cancel goes back, saving nothing."""
    return tags.text_content.p[
        tags.forms.button["Save"],
        " ",
        tags.inline_text_semantics.a(href="/editors/")["Cancel"],
    ]


def edit_page(title: str, *fields: typing.Any) -> tags.Stan:
    """An edit page: the object's name, kept up to date, and a form posting
    to its own URL, Resource's url slot. The heading is live with no URL, so
    it watches the page's own -- the object's -- and someone else's edit of
    the object shows here; the form, being typed in, is not."""
    return tags.page(
        title,
        NAV,
        tags.content_sectioning.h1(id="heading", live=True, slt="name")["A name"],
        tags.forms.form(attr="action=url", method="post")[
            tags.content_sectioning.h2[title], *fields, buttons()
        ],
        stylesheets=[STYLESHEET],
        live=True,
    )


def name_field() -> tags.Stan:
    return tags.forms.label[
        "Name",
        tags.forms.input(attr="value=name", type="text", name="name", required=True),
    ]


class Character(resource.Resource):
    """A character: state {"name", "prompt", "agent_args"}."""

    template = edit_page(
        "Edit character",
        name_field(),
        tags.forms.label[
            "System prompt",
            tags.forms.textarea(slt="prompt", name="prompt")["A prompt"],
        ],
        tags.forms.label[
            "Agent args",
            tags.forms.input(attr="value=agent_args", type="text", name="agent_args"),
        ],
    )

    async def handle_POST(self, request: mumutypes.State) -> typing.Any:
        form = self.form(request)
        if not form.text("name"):
            raise mumutypes.HTTPResponse(400, "A character needs a name.\n")
        self.state.update(
            name=form.text("name"),
            prompt=form.text("prompt"),
            agent_args=form.text("agent_args"),
        )
        await self.save()
        self.see_other("/editors/")


class Party(resource.Resource):
    """A party: state {"name", "members"}, the members character ids."""

    template = edit_page(
        "Edit party",
        name_field(),
        tags.forms.label[
            "Members",
            tags.forms.select(slt="member_options", name="members[]", multiple=True),
        ],
    )

    def slot_member_options(self, request: mumutypes.State) -> list[tags.Stan]:
        # One option for each character, chosen if it is a member
        return [
            tags.forms.option(value=cid, selected=cid in self.state["members"])[
                c.state["name"]
            ]
            for cid, c in characters.items()
        ]

    async def handle_POST(self, request: mumutypes.State) -> typing.Any:
        form = self.form(request)
        # members[] is a list, and none chosen sends none: []
        members = form.texts("members")
        if not form.text("name"):
            raise mumutypes.HTTPResponse(400, "A party needs a name.\n")
        unknown = [cid for cid in members if cid not in characters]
        if unknown:
            raise mumutypes.HTTPResponse(400, f"No character {unknown[0]!r}.\n")
        self.state.update(name=form.text("name"), members=members)
        await self.save()
        self.see_other("/editors/")


class Deploy(resource.Resource):
    """A deploy: state {"name", "party", "status"}. Its status is the
    server's, shown on its page and not taken from any form."""

    template = edit_page(
        "Edit deploy",
        name_field(),
        tags.forms.label["Party", tags.forms.select(slt="party_options", name="party")],
        tags.text_content.p[
            "Status: ", tags.inline_text_semantics.span(slt="status")["running"]
        ],
    )

    def slot_party_options(self, request: mumutypes.State) -> list[tags.Stan]:
        return [
            tags.forms.option(value=pid, selected=pid == self.state["party"])[
                p.state["name"]
            ]
            for pid, p in parties.items()
        ]

    async def handle_POST(self, request: mumutypes.State) -> typing.Any:
        form = self.form(request)
        name, party = form.text("name"), form.text("party")
        if not name:
            raise mumutypes.HTTPResponse(400, "A deploy needs a name.\n")
        if party not in parties:
            raise mumutypes.HTTPResponse(400, f"No party {party!r}.\n")
        self.state.update(name=name, party=party)
        await self.save()
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


class Editors(resource.Resource):
    """/editors/: a table of each kind, every row a copy of its pattern. Each
    row is live, watching its own object, kept up to date by live.js."""

    template = tags.page(
        "Editors",
        NAV,
        tags.table_content.table(id="characters")[
            tags.table_content.caption["Characters"],
            tags.table_content.thead[
                tags.table_content.tr[
                    tags.table_content.th["Name"],
                    tags.table_content.th["Prompt"],
                    tags.table_content.th["Agent args"],
                ]
            ],
            tags.table_content.tbody(slt="character_rows")[
                tags.table_content.tr(
                    pat="character_row", attr={"id": "row_id", "data-live": "watch"}
                )[
                    tags.table_content.td[
                        tags.inline_text_semantics.a(slt="name", attr="href=edit")
                    ],
                    tags.table_content.td(slt="prompt"),
                    tags.table_content.td[
                        tags.inline_text_semantics.code(slt="agent_args")
                    ],
                ]
            ],
        ],
        tags.table_content.table(id="parties")[
            tags.table_content.caption["Parties"],
            tags.table_content.thead[
                tags.table_content.tr[
                    tags.table_content.th["Name"], tags.table_content.th["Members"]
                ]
            ],
            tags.table_content.tbody(slt="party_rows")[
                tags.table_content.tr(
                    pat="party_row", attr={"id": "row_id", "data-live": "watch"}
                )[
                    tags.table_content.td[
                        tags.inline_text_semantics.a(slt="name", attr="href=edit")
                    ],
                    tags.table_content.td(slt="members"),
                ]
            ],
        ],
        tags.table_content.table(id="deploys")[
            tags.table_content.caption["Deploys"],
            tags.table_content.thead[
                tags.table_content.tr[
                    tags.table_content.th["Name"],
                    tags.table_content.th["Party"],
                    tags.table_content.th["Status"],
                ]
            ],
            tags.table_content.tbody(slt="deploy_rows")[
                tags.table_content.tr(
                    pat="deploy_row", attr={"id": "row_id", "data-live": "watch"}
                )[
                    tags.table_content.td[
                        tags.inline_text_semantics.a(slt="name", attr="href=edit")
                    ],
                    tags.table_content.td(slt="party"),
                    tags.table_content.td(slt="status"),
                ]
            ],
        ],
        stylesheets=[STYLESHEET],
        live=True,
    )

    def slot_character_rows(self, request: mumutypes.State) -> list[tags.Stan]:
        return [
            self.pattern("character_row", **row("characters", cid), **c.state)
            for cid, c in characters.items()
        ]

    def slot_party_rows(self, request: mumutypes.State) -> list[tags.Stan]:
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

    def slot_deploy_rows(self, request: mumutypes.State) -> list[tags.Stan]:
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


class Site(resource.Resource):
    """/editors: every child a class attribute, child_<name> being found as
    any attribute is. Its slash is child_index, the tables; the rest are
    the three kinds, and the stylesheet, a file served as it is."""

    child_index = Editors()
    child_characters = characters
    child_parties = parties
    child_deploys = deploys
    child_style = pathlib.Path(__file__).parent / "editors" / "style.css"


# Every change announced on it; consumers_app serves it, and live.js
changes = server.EventSource()

app = server.consumers_app({"editors": Site()}, changes=changes)
