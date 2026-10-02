# State sync

Status: part one built (`sync.bind`); part two, links, deferred. Started
2026-10-01.

How the server's state tree and the TypeScript `state` module are kept the
same, automatically.

## What the code does today

- Inside other JSON, a resource is its whole state, inlined, through
  `add_json_form`; there are no links between documents.
- No JSON key is reserved, and nothing checks the shape of a `PUT` body.
- The TypeScript `state` module keeps a state tree in the browser, changed by
  `set_state` and `set_path`; nothing connects it to the server's.

## Decisions

### 1. Server to client is automatic

A path in the client's `state` tree is bound to a container URL. When the
change stream announces that URL, the client fetches it again and puts what
it gets at the bound path with `set_path`. It is live updates' idea --
something watching a URL -- with a state path watching instead of an element,
and URLs are compared as live updates compare them: as paths, without an
extension, a query or a fragment, a trailing slash kept, and exactly.

### 2. Client to server is explicit REST

The client changes the server's state by asking: a `PUT` or a `PATCH`, sent
by the app. Changes to the client's own tree are never pushed to the server
by themselves.

### 3. The server is the authority, and nothing is optimistic

The client never changes its bound tree itself. Its own write comes back to
it as anyone's does -- announced, fetched, applied -- so its state is always
the server's, never ahead of it: no rollback, no change applied twice, no
race between the two. It costs a round trip before the user sees their own
change; optimism can be added later, for one interaction, if that ever
matters.

### 4. A URL not seen before is fetched eagerly

A bound tree's links are where one document ends and another begins. When
the client meets a link to a URL it has not seen before, it fetches it then
and there, rather than waiting until it is needed.

### 5. A link is a richer type than a string

A link to another document has to be told apart from a field whose value is
a string that looks like a URL, so it is not a bare string.

### 6. One tagged-value shape for every richer type: JSON-LD's

JSON has no type for a link, a date or anything else beyond its own, so
richer types are carried by one general mechanism, borrowed from JSON-LD:
an object whose keys start with `@`. A link is a node reference,
`{"@id": "/users/42"}`. Others come the same way when they are needed --
JSON-LD's typed value, `{"@value": "2026-10-01", "@type": "..."}`, for a
date, say. Every key starting with `@` is reserved for these.

### 7. The shape is reserved, and only the serializer makes it

The tagged shape is never user content. The JSON serializer is the only thing
that produces it, so a tagged value in the output always came from the
serializer and means what its tag says.

### 8. Writes that contain it are refused, everywhere

A write whose content contains the reserved shape -- any key starting with
`@`, at any depth -- is refused, with a 400, not escaped. Escaping would let
user data use the shape too, at the cost of a transform on every read and
write; refusing is much simpler.

It is checked on every write: `PUT`, `PATCH` and a sub-URL `PUT`, into a
persist and into plain dicts and lists in memory alike. Allowing it anywhere
would let the shape into stored content.

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

### 11. A link is expanded, on the client, into the state it names

Links follow decision 6: a resource or persist inside other JSON is a link,
`{"@id": url}`, not its state inlined. On the client a link is the special
case: it is expanded, recursively, into the state its URL names, and that
is what keeps the client's tree in the server's shape.

### 12. Clients do not write links

Every `@` key is refused in a write (decision 8), so a client cannot make a
link: a reference it writes is plain data, an id, as the editors example's
party members are, and a persist never holds a link.

### 13. To start, no resource or persist holds another

Links in a saved file would have to be hydrated back into the objects they
name when it is loaded, which needs more design. To start, no resource or
persist contains another container.

## Part one: no container in a container

State sync is built in two parts. Part one has no container -- a resource
or a persist, anything Located -- inside another, so it has no links:
decisions 4 to 9, the `@` shape and links, and decisions 11 and 12, are part
two's.

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

Built first, as part of part one: a string or a number answers `.txt` and
`.json` alone, and is not found as anything else -- as `.html` it would be
served as markup, a visitor's included. HTML of a program's own is a
`tags.Markup`, served at `.html`. A resource's template is HTML alone, not
found as `.txt`. A file is served at its extension on disk alone.

## Part two: deferred

Part two -- a resource or persist inside another's state, as a link --
waits. What part one has, plain JSON with references as plain ids looked up
by whoever needs them, is much simpler, and is to be used until it causes a
problem; part two is designed then, against that problem.

## Open questions

1. **Links to objects not yet located.** A link needs the object's URL,
   which it learns when a request first reaches it; until then it has none.
2. **Hydrating links in a saved file**, when it is loaded: to be refined.
