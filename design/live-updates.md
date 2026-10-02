# Live updates

Status: decided, not yet built. Started 2026-10-01.

How a page's elements keep themselves up to date when the server's state
changes, using `consumers_app(changes=...)` and mumulib's `live.js`.

## What the code does today

- Every successful mutation -- a `POST`, `PUT`, `PATCH` or `DELETE` answered
  with a 2xx, or with a form post's 303 See Other -- puts **one** URL on the
  change stream: the request's URL without its extension
  (`/editors/characters/c1`), or for a 201 the new object's `Location`,
  likewise without its extension. A slash (`/editors/`) is put as itself.
- `consumers_app(changes=...)` serves the stream at `/mumulib/changes.sse` and
  the script at `/mumulib/live.js`.
- `live.js` opens the stream only if the page has `data-live` elements with
  an `id`. On **every** event, whatever URL it carries, it fetches the
  page's own URL again and replaces each `data-live` element by the element
  with the same `id` in the fresh page. `data-live` carries no value.

## The design

### Each live element watches one URL

A live element is marked `data-live`, and has an `id`. It watches one URL:

- `data-live="<url>"` watches that URL;
- `data-live` with no value watches the **current page's URL**.

### URLs are compared exactly, as paths

Both the watched URL and the URL an event carries are compared as paths on
the page's origin, without an extension, a query or a fragment. A trailing
slash is kept, so `/editors/` and `/editors` are different URLs. A match is
exact: no prefixes and no hierarchy, so an event announcing `/users/42/name`
does not match an element watching `/users/42`, nor one watching `/users`.

So on `/editors/characters/c1.html`, a `data-live` with no value watches
`/editors/characters/c1`.

### What an event announces

Which URL a change announces is the persistence design's
([persistence.md](persistence.md), decision 8): a write inside a persist
announces that persist's URL, wherever in it the write was made, and a write
with no persist above it announces `/`. So a `PUT` to `/users/42/name`,
`/users/42` being a persist, announces `/users/42`, and the element watching
`/users/42` is refreshed: matching stays exact, and the persist is what is
announced.

### A match refetches the current page

When an event's URL matches what one or more live elements watch:

1. the **current page** is fetched again, once for the event, whatever URL
   the elements watch -- the watched URL says when to refresh, not where
   from;
2. each **matching** element is replaced by the element with the same `id`
   in the fetched page; an element with no counterpart there is left as it
   is;
3. elements that did not match are left as they are.

An event that matches nothing fetches nothing.

### The stream opens only when there is something to watch

As today: a page with no live element opens no stream.

## What it means for the editors example

The index's tables have no URL of their own that an edit announces -- an
edit announces the persist it is inside -- so each **row** is the live
element, watching its own object: the row for `c1` is
`<tr id="character-c1" data-live="/editors/characters/c1">`. An edit inside
the persist `/editors/characters/c1` refetches `/editors/` and replaces that
row alone.

A row shows what it watches, and nothing else is kept up to date by it: a
party's row lists its members' names but watches the party, so renaming a
character refreshes that character's row, and the party's row only when the
party itself next changes.
