# PATCH

Status: design to come, after the rest of persistence is built. Started
2026-10-01.

Changing several fields of a container in one atomic write. Moved here from
the persistence design, to be designed and built last.

## Decided so far

- `PATCH` on a container changes several of its fields in one atomic write:
  the whole container committed, as every write is (persistence decision 7).
- Its language is JSON Patch (RFC 6902) to start with: a list of operations
  -- `add`, `remove`, `replace`, `move`, `copy`, `test` -- each at a JSON
  Pointer (RFC 6901) into the document, applied in order, all or none. The
  same as AG-UI's `STATE_DELTA`. We see whether we like it.

## To decide

- Written here, RFC 6902 and RFC 6901 with their `~0` and `~1` escapes, for
  the learning -- or the `jsonpatch` library?
