# Live updates

Status: design in progress. Started 2026-10-01.

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

## Decisions

### 1. `data-live` with no URL: the current page's URL

An element marked `data-live` with no value is refreshed only when the
**current page's URL** is seen on the stream. When it is, it is refreshed as
today: the page is fetched again, and the element is replaced by the element
with the same `id` in it.

The page's URL is compared without its extension, as events carry it: on
`/editors/characters/c1.html` the element is refreshed by
`/editors/characters/c1`. _(To confirm: see open questions 1 and 2.)_

### 2. `data-live="<url>"`: that URL

An element marked `data-live="<url>"` is refreshed only when **that URL** is
seen on the stream, matched exactly. When it is, it is replaced by the
version of it fetched from the server. _(What is fetched, and what replaces
the element: see open questions 3 and 4.)_

Matching is exact on purpose: no prefixes, no hierarchy. A change to
`/users/42/name` does not refresh an element bound to `/users/42`, nor one
bound to `/users`. Push exact matching as far as it goes, and add anything
more only when a real use case forces it.

## Open questions

1. **How URLs compare.** Proposed: both sides as paths, without the
   extension, query or fragment, on the same origin; a trailing slash is
   kept, so `/editors/` is not `/editors`. Is a page at `/editors/` refreshed
   by `/editors/` alone?

2. **The editors example under rule 1.** Its index tables have no URL, so
   they would be refreshed only when `/editors/` is announced -- and an edit
   announces the object it changed, `/editors/characters/c1`. Under these
   rules the index no longer updates. Options:
   - bind each table to a URL that is announced (rule 2), which needs one of
     the next two;
   - announce more than one URL per change: `Character.handle_POST` also
     announces `/editors/characters`, and the characters table binds to it
     (the "composite resource" route -- more announcements per change, which
     we had wanted to put off);
   - bind each row to its own object (`data-live="/editors/characters/c1"`),
     each row fetched alone -- though the parties table also shows character
     names, so it depends on every character too.

3. **What rule 2 fetches.** The event carries a URL without an extension;
   something has to choose the representation. Proposed: `<url>.html`, or the
   slash as it is.

4. **What replaces the element.** The fetched document could be a whole page
   (an edit page is) or a fragment. Proposed: the element in the fetched
   document with the same `id` as the live one, as rule 1 does; failing that,
   nothing. Alternative: the fetched body's first element, so a resource can
   serve just the fragment.

5. **Several elements, one URL.** If many elements are bound to the same URL,
   fetch it once and replace them all from the one response.

6. **When the stream opens.** As today, only when the page has a live
   element.

## Later, not now

- More than one URL per change (a handler announcing a list).
- Conditional writes (a version or ETag) for when last-write-wins is wrong.
- State shared between server processes: today state lives in one process's
  memory, so a mumulib app runs as one worker.
- Transitions when an element is replaced.
