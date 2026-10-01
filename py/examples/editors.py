"""Editors: characters, parties and deploys, each edited in a plain HTML form.

    make run SERVER=editors      then http://127.0.0.1:8001/editors/

Every page is built here, in Stan, and each object is a Resource whose state
is its data -- and so its JSON, and what its edit page's slots are filled
from. A form posts to the object's own URL, and its handle_POST checks what
was sent, keeps it, and answers 303 See Other, back to /editors/:

    GET  /editors/                          the three tables
    GET  /editors/characters/c1.html        a character's edit page
    POST /editors/characters/c1.html        name=...&prompt=...&agent_args=...
    GET  /editors/parties/p1.html           a party's, its members a <select>
    POST /editors/parties/p1.html           name=...&members[]=c1&members[]=c2
    GET  /editors/deploys/d1.html           a deploy's, its status shown
    POST /editors/deploys/d1.html           name=...&party=p2
    GET  /editors/characters.json           {"c1": {"name": ..., ...}, ...}
    GET  /editors/changes.sse               the URL of each change, as it is made

Each object has an id that never changes, so its URL does not either, and
renaming is a post to the URL it already had. A party's members and a
deploy's party are ids, so they follow a rename.

It works with no script at all: an edit link is a link, and a form a form.
The pages' one script makes it nicer, in the way htmx does: an edit link's
page is fetched and its <form> taken out and shown in a dialog, and when the
server says something changed -- anyone's change, from any page -- /editors/
is fetched and its tables put in place of these.
"""

from typing import Any, cast

from mumulib.mumutypes import HTTPResponse, State
from mumulib.resource import Resource
from mumulib.server import EventSource, consumers_app
from mumulib.tags import Stan
from mumulib.tags import every as t

STYLE = """
body { font-family: serif; margin: 2em; }
table { border-collapse: collapse; margin-bottom: 2em; min-width: 40em; }
caption { text-align: left; font-weight: bold; padding: 0.5em 0; }
th, td { border: 1px solid #888; padding: 0.4em 0.6em; text-align: left; }
label { display: block; margin-bottom: 1em; }
input[type=text], textarea, select { display: block; width: 28em; font: inherit; }
textarea { height: 8em; }
"""

# The one script: forms in a dialog, and tables kept up to date. A <script>
# is written as it is, not escaped, so nothing of a visitor's goes in it.
SCRIPT = """
const dialog = document.getElementById('editor')

// An edit link: its page fetched, and its form shown in the dialog. The form
// still posts as a form does, and the page that answers is this one again.
document.addEventListener('click', async (event) => {
  const link = event.target.closest('a[data-edit]')
  if (!link || !dialog) return
  event.preventDefault()
  const html = await (await fetch(link.href)).text()
  const page = new DOMParser().parseFromString(html, 'text/html')
  dialog.replaceChildren(page.querySelector('form'))
  dialog.showModal()
})

// Something changed, here or anywhere: the tables, fetched again
new EventSource('/editors/changes.sse').onmessage = async () => {
  const html = await (await fetch('/editors/')).text()
  const page = new DOMParser().parseFromString(html, 'text/html')
  for (const table of document.querySelectorAll('table[id]')) {
    const fresh = page.getElementById(table.id)
    if (fresh) table.replaceWith(fresh)
  }
}
"""


def page(title: str, *content: Any) -> Stan:
    """A whole page: its title, what it holds, the dialog, and the script."""
    return t.html[
        t.head[
            t.meta(charset="utf-8"),
            t.title[title],
            t.style[STYLE],
        ],
        t.body[
            t.p[t.a(href="/editors/")["Editors"]],
            *content,
            t.dialog(id="editor"),
            t.script[SCRIPT],
        ],
    ]


def buttons() -> Stan:
    """Save posts the form; Cancel closes the dialog it is in, saving nothing."""
    return t.p[
        t.button["Save"],
        " ",
        t.button(formmethod="dialog", formnovalidate="formnovalidate")["Cancel"],
    ]


def option(value: str, label: str, chosen: bool) -> Stan:
    """An <option>, selected if chosen: selected is so whenever it is there,
    so it is left out, not set false."""
    return t.option(value=value, **({"selected": ""} if chosen else {}))[label]


def fields(request: State) -> dict[str, Any]:
    """What a form posted, by name."""
    body = request.get("parsed_body")
    return cast(dict[str, Any], body) if isinstance(body, dict) else {}


def text(posted: dict[str, Any], name: str) -> str:
    """One text field, or nothing if it was not sent as one."""
    value = posted.get(name, "")
    return value.strip() if isinstance(value, str) else ""


class Character(Resource):
    """A character: state {"name", "prompt", "agent_args"}."""

    template = page(
        "Edit character",
        t.form(attr="action=url", method="post")[
            t.h2["Edit character"],
            t.label[
                "Name",
                t.input(attr="value=name", type="text", name="name", required=""),
            ],
            t.label[
                "System prompt",
                t.textarea(slt="prompt", name="prompt")["A prompt"],
            ],
            t.label[
                "Agent args",
                t.input(attr="value=agent_args", type="text", name="agent_args"),
            ],
            buttons(),
        ],
    )

    def slot_url(self, request: State) -> str:
        # The form posts to this page's own URL
        return str(request["url"])

    async def handle_POST(self, request: State) -> Any:
        posted = fields(request)
        name = text(posted, "name")
        if not name:
            raise HTTPResponse(400, "A character needs a name.\n")
        self.state.update(
            name=name,
            prompt=text(posted, "prompt"),
            agent_args=text(posted, "agent_args"),
        )
        self.see_other("/editors/")


class Party(Resource):
    """A party: state {"name", "members"}, the members character ids."""

    template = page(
        "Edit party",
        t.form(attr="action=url", method="post")[
            t.h2["Edit party"],
            t.label[
                "Name",
                t.input(attr="value=name", type="text", name="name", required=""),
            ],
            t.label[
                "Members",
                t.select(slt="member_options", name="members[]", multiple=""),
            ],
            buttons(),
        ],
    )

    def slot_url(self, request: State) -> str:
        return str(request["url"])

    def slot_member_options(self, request: State) -> list[Stan]:
        # One option for each character, chosen if it is a member
        return [
            option(cid, character.state["name"], cid in self.state["members"])
            for cid, character in characters.items()
        ]

    async def handle_POST(self, request: State) -> Any:
        posted = fields(request)
        name = text(posted, "name")
        # members[] is a list, and absent when none is chosen
        members = posted.get("members[]", [])
        if not name:
            raise HTTPResponse(400, "A party needs a name.\n")
        unknown = [cid for cid in members if cid not in characters]
        if unknown:
            raise HTTPResponse(400, f"No character {unknown[0]!r}.\n")
        self.state.update(name=name, members=members)
        self.see_other("/editors/")


class Deploy(Resource):
    """A deploy: state {"name", "party", "status"}. Its status is the
    server's, shown on its page and not taken from any form."""

    template = page(
        "Edit deploy",
        t.form(attr="action=url", method="post")[
            t.h2["Edit deploy"],
            t.label[
                "Name",
                t.input(attr="value=name", type="text", name="name", required=""),
            ],
            t.label["Party", t.select(slt="party_options", name="party")],
            t.p["Status: ", t.span(slt="status")["running"]],
            buttons(),
        ],
    )

    def slot_url(self, request: State) -> str:
        return str(request["url"])

    def slot_party_options(self, request: State) -> list[Stan]:
        return [
            option(pid, party.state["name"], pid == self.state["party"])
            for pid, party in parties.items()
        ]

    async def handle_POST(self, request: State) -> Any:
        posted = fields(request)
        name, party = text(posted, "name"), text(posted, "party")
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


def edit_link(kind: str, key: str) -> str:
    return f"/editors/{kind}/{key}.html"


class Editors(Resource):
    """/editors/: a table of each kind, every row a copy of its pattern."""

    template = page(
        "Editors",
        t.table(id="characters")[
            t.caption["Characters"],
            t.thead[t.tr[t.th["Name"], t.th["Prompt"], t.th["Agent args"]]],
            t.tbody(slt="character_rows")[
                t.tr(pat="character_row")[
                    t.td[t.a(slt="name", attr="href=edit", **{"data-edit": ""})],
                    t.td(slt="prompt"),
                    t.td[t.code(slt="agent_args")],
                ]
            ],
        ],
        t.table(id="parties")[
            t.caption["Parties"],
            t.thead[t.tr[t.th["Name"], t.th["Members"]]],
            t.tbody(slt="party_rows")[
                t.tr(pat="party_row")[
                    t.td[t.a(slt="name", attr="href=edit", **{"data-edit": ""})],
                    t.td(slt="members"),
                ]
            ],
        ],
        t.table(id="deploys")[
            t.caption["Deploys"],
            t.thead[t.tr[t.th["Name"], t.th["Party"], t.th["Status"]]],
            t.tbody(slt="deploy_rows")[
                t.tr(pat="deploy_row")[
                    t.td[t.a(slt="name", attr="href=edit", **{"data-edit": ""})],
                    t.td(slt="party"),
                    t.td(slt="status"),
                ]
            ],
        ],
    )

    def slot_character_rows(self, request: State) -> list[Stan]:
        return [
            self.pattern("character_row", edit=edit_link("characters", cid), **c.state)
            for cid, c in characters.items()
        ]

    def slot_party_rows(self, request: State) -> list[Stan]:
        return [
            self.pattern(
                "party_row",
                edit=edit_link("parties", pid),
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
                edit=edit_link("deploys", did),
                name=d.state["name"],
                party=parties[d.state["party"]].state["name"],
                status=d.state["status"],
            )
            for did, d in deploys.items()
        ]


changes = EventSource()

app = consumers_app(
    {
        "editors": {
            "index": Editors(),
            "characters": characters,
            "parties": parties,
            "deploys": deploys,
            "changes": changes,
        }
    },
    changes=changes,
)
