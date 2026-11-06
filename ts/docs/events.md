# mumulib/events

Import it with the rest of the library, `import { events } from 'mumulib'`, or
alone, `import { source, at } from 'mumulib/events'`, which brings nothing
else with it but what it uses.

`events.source(url)` listens to the event stream at `url` as
`new EventSource(url)` would -- `onmessage`, `onopen`, `onerror`,
`addEventListener`, `close`, `readyState` -- but every source on a page
shares one connection: the Python server's hub, `/mumulib/events.sse`, which
subscribes to each and sends everything back on one stream. A browser opens
six connections to a host, and an event stream holds one for as long as it
is open; over the hub a page holds one, however many it listens to.

```typescript
import { events } from 'mumulib'

const terminal = events.source('api/terminal.sse')
terminal.onmessage = (event) => write(event.data)
terminal.addEventListener('turn_ended', () => beep())
const shots = events.source('api/screenshots.sse')
```

Sources made at once open one stream; adding or closing one opens it again
with the topics there are. A page below a prefix -- an app mounted at
`/cb/` -- says so first, `events.at('/cb/')`. `examples/use_events` is a
page listening to three.

## events api

```ts
source(url: string): Source
at(prefix: string): void
```

`source`: an `EventSource`'s shape for the stream at url, over the hub's. `at`: where the hub is, the app's prefix, `/` unless said.
