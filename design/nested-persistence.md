# Nested persistence

Status: tentative. Deferred until state sync's part one causes a problem.
Started 2026-10-01.

A resource or a persist inside another's state -- a container in a
container -- carried as a link, on the server, on disk and in the client.
[State sync](state-sync.md)'s part one has none: a state is plain JSON, and
a reference is a plain id, looked up by whoever needs it. That is much
simpler, and is to be used until it causes a problem; this is designed
then, against that problem. What follows is what was decided before it was
deferred, as state sync's part two, renumbered here.

## Decisions, tentative

### 1. A URL not seen before is fetched eagerly

A bound tree's links are where one document ends and another begins. When
the client meets a link to a URL it has not seen before, it fetches it then
and there, rather than waiting until it is needed.

### 2. A link is a richer type than a string

A link to another document has to be told apart from a field whose value is
a string that looks like a URL, so it is not a bare string.

### 3. One tagged-value shape for every richer type: JSON-LD's

JSON has no type for a link, a date or anything else beyond its own, so
richer types are carried by one general mechanism, borrowed from JSON-LD:
an object whose keys start with `@`. A link is a node reference,
`{"@id": "/users/42"}`. Others come the same way when they are needed --
JSON-LD's typed value, `{"@value": "2026-10-01", "@type": "..."}`, for a
date, say. Every key starting with `@` is reserved for these.

### 4. The shape is reserved, and only the serializer makes it

The tagged shape is never user content. The JSON serializer is the only thing
that produces it, so a tagged value in the output always came from the
serializer and means what its tag says.

### 5. Writes that contain it are refused, everywhere

A write whose content contains the reserved shape -- any key starting with
`@`, at any depth -- is refused, with a 400, not escaped. Escaping would let
user data use the shape too, at the cost of a transform on every read and
write; refusing is much simpler.

It is checked on every write: `PUT`, `PATCH` and a sub-URL `PUT`, into a
persist and into plain dicts and lists in memory alike. Allowing it anywhere
would let the shape into stored content.

### 6. A link is expanded, on the client, into the state it names

Links follow decision 3: a resource or persist inside other JSON is a link,
`{"@id": url}`, not its state inlined. On the client a link is the special
case: it is expanded, recursively, into the state its URL names, and that
is what keeps the client's tree in the server's shape.

### 7. Clients do not write links

Every `@` key is refused in a write (decision 5), so a client cannot make a
link: a reference it writes is plain data, an id, as the editors example's
party members are, and a persist never holds a link.

## Open questions

1. **Links to objects not yet located.** A link needs the object's URL,
   which it learns when a request first reaches it; until then it has none.
2. **Hydrating links in a saved file**, when it is loaded: to be refined.
