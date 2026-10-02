# State sync

Status: decided, not yet built. Started 2026-10-01.

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

## Open questions

1. **Links to objects not yet located.** A link needs the object's URL,
   which it learns when a request first reaches it; until then it has none.
2. **Hydrating links in a saved file**, when it is loaded: to be refined.
