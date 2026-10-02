# State sync

Status: design in progress. Started 2026-10-01.

How the server's state tree and the TypeScript `state` module are kept the
same, automatically.

## What the code does today

- Inside other JSON, a resource is its whole state, inlined, through
  `add_json_form`; there are no links between documents.
- No JSON key is reserved, and nothing checks the shape of a `PUT` body.
- The TypeScript `state` module keeps a state tree in the browser, changed by
  `set_state` and `set_path`; nothing connects it to the server's.

## Decisions

### 1. A URL not seen before is fetched eagerly

When the client meets a link to a URL it has not seen before, it fetches it
then and there, rather than waiting until it is needed.

### 2. A link is a richer type than a string

A link to another document has to be told apart from a field whose value is
a string that looks like a URL, so it is not a bare string.

### 3. One tagged-value shape for every richer type

JSON has no type for a link, a date or anything else beyond its own, so
richer types are carried by one general mechanism: an object of a reserved
shape that says which type it is and carries its value. A link is its first
type; others, dates among them, come through the same shape when they are
needed.

### 4. The shape is reserved, and only the serializer makes it

The tagged shape is never user content. The JSON serializer is the only thing
that produces it, so a tagged value in the output always came from the
serializer and means what its tag says.

### 5. Writes that contain it are refused

A write whose content contains the reserved shape is refused, with a 400 --
not escaped. Escaping would let user data use the shape too, at the cost of
a transform on every read and write; refusing is much simpler.

## Open questions

1. **The reserved shape.** Which keys make an object a tagged value? For
   example: a link as `{"@id": "/users/42"}`, as JSON-LD has it, a date as
   `{"@date": "2026-10-01"}`, and every key starting with `@` reserved; or
   one tag key for every type, `{"@type": "link", "@value": "/users/42"}`.
2. **Where the ban is checked.** On every write into a persist -- `PUT`,
   `PATCH` and a sub-URL `PUT` -- at any depth of what is written? And into
   plain dicts and lists in memory too, or persists alone?
