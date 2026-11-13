"""Live elements: parts of a server-built page that keep themselves up to date.

    make server SERVER=live

The page is built here, by a function, each time it is asked for. Given
changes, consumers_app announces the URL of what each write changed, and
serves live.js, which tags.page(..., live=True) links. An element with an
id and data-live watches one URL; when a change announces it, live.js
fetches the page again and puts the fresh element with that id in place of
the old one. Nothing else on the page is touched.

    GET    /                              the page
    GET    /counters/apples.json          {"count": 0}
    PUT    /counters/apples/count.json    4: announced as /counters/apples
    PUT    /title.json                    "Fruit": announced as /
    GET    /mumulib/changes.sse           each URL, as it is announced
    GET    /mumulib/live.js               the script that follows them

Each counter is a Persist, which knows its own URL, so a write anywhere in
it announces that URL: its row watches it, data-live="/counters/apples",
and is the only thing replaced. The title is a plain entry of the root, with
nothing above it that knows its URL, so a write to it announces /. The
heading is data-live with no value, which watches the page's own URL, and
the page is at /.

The page reads each counter as any client would, with a GET of its URL,
made to the app itself rather than over a socket. Reaching a Persist is what
reads its file, so the page never shows a counter as it was made, before
its file was read: after a restart, say, when no request has yet reached
it. The title is the root's own, kept in no file, and read as it is.

The page's one script of its own PUTs: a button its next count, and the
form its title. The page then waits to hear the change, as every other page
open does. The form is outside every live element, so what is being typed
in it is never replaced.

The counters are kept in var/data/counters/. Delete it to start again.
"""

import json
from typing import Any

from mumulib import mumutypes, persist, server, tags

every = tags.every

SCRIPT = tags.Markup("""
// A button PUTs its value, and the form its title. Neither changes the page:
// live.js puts the change in place when it is announced.
const put = (url, value) =>
  fetch(url, {
    method: "PUT",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(value),
  });
document.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-url]");
  if (button) put(button.dataset.url, Number(button.dataset.value));
});
document.addEventListener("submit", (event) => {
  event.preventDefault();
  put("/title.json", new FormData(event.target).get("title"));
});
""")


async def get(path: str) -> Any:
    """What a GET of path answers, as JSON: asked of the app itself."""
    sent: list[mumutypes.Message] = []

    async def receive() -> mumutypes.Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: mumutypes.Message) -> None:
        sent.append(message)

    scope: mumutypes.Scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": [],
    }
    await app({**scope, "state": {}}, receive, send)
    return json.loads(b"".join(m.get("body", b"") for m in sent[1:]))


def row(name: str, count: int) -> tags.Stan:
    """One counter's row: watching its own URL, with a button for one more."""
    return every.li(id=name, live=f"/counters/{name}")[
        name,
        ": ",
        every.output[str(count)],
        " ",
        every.button(
            **{"data-url": f"/counters/{name}/count.json", "data-value": count + 1}
        )["+1"],
    ]


async def page(state: mumutypes.State) -> tags.Stan:
    """The page, from the title and the counters as they are now."""
    rows = [
        row(name, (await get(f"/counters/{name}.json"))["count"]) for name in counters
    ]
    return tags.page(
        root["title"],
        # A bare data-live: it watches the page's own URL, /
        every.h1(id="title", live=True)[root["title"]],
        every.ul[rows],
        every.form[
            every.label["Title ", every.input(name="title", value=root["title"])],
            every.button["Rename"],
        ],
        every.script[SCRIPT],
        live=True,
    )


counters = {
    name: persist.Persist({"count": 0}) for name in ("apples", "pears", "plums")
}

root: dict[str, Any] = {"index": page, "title": "Fruit", "counters": counters}

changes = server.EventSource()

app = server.consumers_app(root, changes=changes)
