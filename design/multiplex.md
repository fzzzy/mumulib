# Multiplexed event streams

Status: built. Started 2026-10-20.

How a page that listens to several event streams does so over one
connection: `/mumulib/events.sse?topic=a&topic=b`, which subscribes to each
topic over HTTP and sends what each says back on the one stream, each event
labelled with the topic it came from.

## Why

A browser speaking HTTP/1.1 opens at most six connections to a host, across
all its tabs, and every open event stream holds one for as long as it is
open. A page with three streams -- Claude Browse's terminal page, with
`api/terminal.sse`, `api/screenshots.sse` and `api/speech.sse`, and its port
in agent_daedalus -- and a second such page, or a chat beside it with its
own, uses them all up; the next request of any kind, a plain `fetch`, waits
for a stream to close, which it never does. To the user, the page hangs.

HTTP/2 multiplexes every request over one connection and makes the limit
moot, but browsers speak it only over TLS, and uvicorn does not speak it at
all: too much to ask of a local development server.

## What the code did before

- An app given `changes=` serves `/mumulib/changes.sse`, one EventSource,
  ahead of the tree: `/mumulib/` is already the library's own prefix. Its
  events are unnamed, the JSON of what was put.
- Any `.sse` URL in the tree is an event stream from whatever its thing's
  producer is: an `EventSource`, or a producer of the app's own, as
  agent_daedalus's terminals are.
- A page opens one `EventSource` per stream. mumulib's own pages open one,
  `/mumulib/changes.sse`, through `live.js` or `sync.ts`; apps built on it
  open several.
- Named events are in use: `event: earlier` for screenshots already taken,
  `event: turn_ended`, `event: turn`, beside the unnamed `message` ones.

## Decisions

### 1. One stream, at /mumulib/events.sse

A page's streams come over one, at `/mumulib/events.sse`, under the prefix
the library already keeps for itself, so it cannot collide with an app's own
`events.sse`. Mercure's is `/.well-known/mercure`; this is the same idea,
named for where mumulib keeps its own things.

### 2. Topics are event streams' URLs, each a topic= in the query

`/mumulib/events.sse?topic=threads/t1/api/terminal.sse&topic=api/speech.sse`

A topic is the URL of an event stream. A relative one is the app's own,
resolved against where the hub is -- below whatever prefix the app is
mounted at, as `/mumulib/events.sse` itself is -- so
`threads/t1/api/terminal.sse` is the app's; an absolute one,
`https://other.example/news.sse`, is another server's (decision 3). Each is
its own `topic=`, repeated, as Mercure's are: a comma could be in a URL, and
a repeated key needs no escaping rule of its own.

Nothing about a stream changes to be a topic: whatever answers GET on a
`.sse` URL, an `EventSource` or a producer, is one.

### 3. Each topic is subscribed to over HTTP, so a hub can gather any server's

The hub subscribes to each topic as a browser would: a GET to its URL, over
HTTP, read as it streams. A topic of the app's own is a request back to its
own server; one of another server's is a request to that server. So a page
can hear several servers over its one connection, and a hub can be put in
front of streams wherever they are -- the hubs' streams distribute.

A request to the hub's own origin carries the page's own headers -- its
cookies and its authorization -- so a topic answers the page as it would
have answered it directly. Another server is reached only if the app names
its origin, `multiplexed(app, origins=["https://other.example"])`, and
without the page's cookies or authorization, which are its own server's:
otherwise a page could have the server fetch any URL it liked.

### 4. The hub is middleware, so it wraps any ASGI app

`multiplexed(app)` answers `/mumulib/events.sse` and passes everything else
to app. `consumers_app` wraps itself in it, so every mumulib app has the hub
with nothing to ask for; `consumers_app(..., multiplex=False)` leaves it
out. An app built otherwise -- agent_daedalus's FastAPI app, with mumulib's
mounted inside it -- wraps itself, and its own streams become topics too.

### 5. Each event is labelled with its topic, by SSE's own event name

An event from a topic goes out named for the topic and its own name, a
space between: `event: api/speech.sse message` for an unnamed one,
`event: threads/t1/api/terminal.sse turn_ended` for a named one. A space is
never in a URL's path, so the two are told apart without escaping. Its data
is the topic's, line for line; its `id:` is dropped (decision 9); a topic's
comments and `retry:` are its own, and not passed on.

### 6. The client keeps its EventSource shape

`events` in TypeScript, as mumulib's other modules are:

```ts
import { events } from 'mumulib'

const terminal = events.source('api/terminal.sse')
terminal.onmessage = (e) => ...
terminal.addEventListener('turn_ended', () => ...)
terminal.close()
```

`events.source(url)` returns an object with `EventSource`'s own --
`onmessage`, `onerror`, `onopen`, `addEventListener`, `close`, `readyState`,
`url` -- so a page swaps one constructor call. The topic is url resolved
against the page, then made relative to the app, which the module learns
from where `/mumulib/events.sse` is: said before the first source,
`events.at('/cb/')`, or `/`. Every source on a page shares one real
`EventSource`.

### 7. Subscribing again is reopening

Asking for a topic, or closing one, reopens the shared stream with the new
list, once per turn of the event loop however many changed: a page that
opens three as it loads makes one connection. Each topic starts again from
the beginning, which every stream here already does on its own -- the
terminal's history, the last turn, the screenshots kept -- so a reopened
page loses nothing, and nothing is replayed by id.

No POST to change a stream's topics while it is open, as Mercure's
subscription API has: not until reopening is shown to be too slow.

### 8. A topic that ends is subscribed to again, by the hub

A topic's stream that ends -- its server restarted the thing behind it, or
it closed one that fell behind -- is subscribed to again by the hub, after
its `retry:` if it gave one, two seconds if not, as a browser would. The
page hears `<topic> open` again, as an `EventSource`'s `open`. The shared
stream stays open throughout.

### 9. A topic that is not a stream says so, once

A topic whose GET answers anything but 200 with `text/event-stream` -- not
found, refused, not a stream, another origin the app did not name -- is not
retried. The page hears `<topic> error`, with the status as its data, and
the client's object for it fires `error` and moves to `CLOSED`, as an
`EventSource` given a 404 does. Every other topic goes on as it was: one
topic's failing is its own, and the shared stream stays open.

A server that cannot be reached at all is not an answer: that topic is
subscribed to again, as one that ended is (decision 8).

### 10. One page's hub is one buffer, and a slow page is closed

Every topic's events go into the stream's one buffer, as an
`EventSource`'s do. A page that falls `max_backlog` events behind is closed,
and reconnects -- every topic with it -- as `EventSource` already is.

### 11. A page's topics are bounded

At most 32 topics on one stream: a 400 past that. A page has a handful.

## Not now

- Authorisation of topics beyond what each topic's own GET does with the
  request's cookies and headers (decision 3): there is none of its own.
- Publishing to a topic through the hub: topics are published as they are
  now, by putting on an `EventSource` or by a producer.
- `Last-Event-ID`, per topic or for the stream: decision 7.

## As built

- `py/mumulib/multiplex.py`: `multiplexed(app, origins=, max_backlog=)`, the
  hub, subscribing over HTTP with httpx2, now a dependency.
  `consumers_app(..., multiplex=True)` wraps itself in it.
- `py/mumulib/streams.py`: what every event stream shares, an
  `EventSource`'s and the hub's -- those open, how one is told to end, how
  one waits for its client to go -- so the server ends the hub's as it
  stops, too.
- `ts/src/events.ts`: `events.source(url)` and `events.at(prefix)`.
- `sync.bind` listens to the change stream through it. `live.js` does not:
  it is a script of its own, served by Python, not part of the bundle, and
  opens its own stream as before.
- Tested in `multiplex_test.py`, against a server of its own over HTTP, and
  in `events.spec.ts`, against a stand-in hub and the editors example's
  real one.
