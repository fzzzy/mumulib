# State sync

Status: built (`sync.bind`). Nested persistence, links between containers,
is [nested-persistence.md](nested-persistence.md), tentative. Started
2026-10-01.

How the server's state tree and the TypeScript `state` module are kept the
same, automatically.

## What the code did before

- Inside other JSON, a resource was its whole state, inlined, through
  `add_json_form`; there were no links between documents.
- No JSON key was reserved, and nothing checked the shape of a `PUT` body.
- The TypeScript `state` module kept a state tree in the browser, changed by
  `set_state` and `set_path`; nothing connected it to the server's.

State sync was designed in two parts. Part one, here, has no container --
a resource or a persist, anything Located -- inside another, so it has no
links; it is built. Part two, links between them, is its own design now,
[nested-persistence.md](nested-persistence.md), tentative. The decisions
here keep the numbers they were made with; the missing ones, 4 to 8, 11 and
12, are part two's, renumbered there.

## Part one: no container in a container (built)

### 1. Server to client is automatic

A path in the client's `state` tree is bound to a container's URL, a
resource's or a persist's (decision 10). When the
change stream announces that URL, the client fetches it again and puts what
it gets at the bound path with `set_path`. It is live updates' idea --
something watching a URL -- with a state path watching instead of an element,
and URLs are compared as live updates compare them: as paths, without an
extension, a query or a fragment, a trailing slash kept, and exactly.

### 2. Client to server is explicit REST

The client changes the server's state by asking: a `PUT` or a `DELETE` --
or a `PATCH`, when [patch.md](patch.md) is built -- sent by the app.
Changes to the client's own tree are never pushed to the server by
themselves.

### 3. The server is the authority, and nothing is optimistic

The client never changes its bound tree itself. Its own write comes back to
it as anyone's does -- announced, fetched, applied -- so its state is always
the server's, never ahead of it: no rollback, no change applied twice, no
race between the two. It costs a round trip before the user sees their own
change; optimism can be added later, for one interaction, if that ever
matters.

### 9. The same shape on both sides

A bound client path holds the server document's own shape -- the same keys,
the same structure -- so a path means the same thing on each side, and
binding one to the other needs no translation. That holds as long as it
works without unforeseen problems; if building it turns some up, this is
revisited.

### 10. A bound URL is a resource or a persist, on purpose

A write announces the nearest resource or persist at or above it
([persistence.md](persistence.md), decision 8), so a plain dict or list
inside one is never announced itself. Only a resource or a persist is
bound.

### 13. To start, no resource or persist holds another

Links in a saved file would have to be hydrated back into the objects they
name when it is loaded, which needs more design
([nested-persistence.md](nested-persistence.md)). To start, no resource or
persist contains another container.

### 14. A bound document holds no resource or persist

A resource's state and a persist's document are plain JSON: dicts, lists
and scalars, nested as deep as they like. A resource or a persist anywhere
inside one is not allowed. Plain dicts and lists still hold resources and
persists, to build the tree, as the editors example's `characters` does;
they are never bound (decision 10).

### 15. A resource's `.json` is its state

A resource is named as a file: `/editors/characters/c1.html` is its page,
its template, and `/editors/characters/c1.json` is its state, as
`Resource`'s own `handle_GET` answers. It is not also a child, `state.json`:
one URL for each representation. So binding is the same for a resource and
a persist: fetch `<url>.json`, the URL a write to it announces with
`.json` on it.

### 16. In plain JSON, only a resource or a persist is its URL

A plain dict or list answers `.json` as JSON, nested as it is, at any
depth: dicts, lists and scalars as themselves. Only a resource or a persist
in it -- anything Located -- is written as the URL of its `.json`, by where
it is: `{"c1": "/editors/characters/c1.json"}`, a plain string. A client
finds there what to bind.

### 17. The client binds a URL to a path

`bind(path, url)` fetches `<url>.json`, puts it at `path` with `set_path`,
and fetches it again whenever the change stream announces `url`, compared
as live updates compare URLs. A page has one change stream. With no links,
nothing is fetched eagerly.

### 18. Writes stay explicit REST

A client changes the server's state with a `PUT` or a `DELETE` on a URL
inside a persist, or with a request a resource's own handler answers. Its
own change comes back to it through the announcement, as anyone's does
(decision 3).

### 19. Text is text, and a template is HTML

Built first, as part of part one ([persistence.md](persistence.md), decision
6): a string or a number answers `.txt` and
`.json` alone, and is not found as anything else -- as `.html` it would be
served as markup, a visitor's included. HTML of a program's own is a
`tags.Markup`, served at `.html`. A resource's template is HTML alone, not
found as `.txt`. A file is served at its extension on disk alone.
