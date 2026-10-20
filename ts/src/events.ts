/**
 * Events
 *
 * A page's event streams over one connection: mumulib's hub,
 * /mumulib/events.sse, which subscribes to each stream named as a topic
 * and sends what each says on one stream, each event named for its topic
 * and its own name -- design/multiplex.md.
 *
 * Functions:
 * - source(url: string): Source
 *   Listens to the event stream at url as `new EventSource(url)` would, and
 *   returns what it would: onmessage, onopen, onerror, addEventListener,
 *   close, readyState, url. Every source on a page shares one EventSource,
 *   the hub's, reopened with the topics there are whenever one is added or
 *   closed, once for however many change at once.
 * - at(prefix: string)
 *   Where the hub is: the prefix the app is mounted at, '/' unless said.
 *   Said before the first source, as a page below one -- /cb/ -- must.
 *
 * A url on the page's origin, below the prefix, is the app's own topic,
 * named relative to it; any other, by its whole URL, another server's,
 * which the app must have named for the hub to reach.
 */

const HUB = 'mumulib/events.sse'

// The prefix the hub is below, and the stream to it, if any is open
let prefix = '/'
let stream: EventSource | undefined
// Each topic, and the sources listening to it
const topics = new Map<string, Set<Source>>()
// What the open stream is listening for, each topic and name its event's
const heard = new Set<string>()
// Whether the stream is to be opened again, once this turn is done
let reopening = false

type Listener = (event: Event) => void

// A source's own handlers, as an EventSource has them
const HANDLED = ['open', 'message', 'error'] as const

/** One event stream, heard over the hub's: an EventSource's shape. */
class Source extends EventTarget {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSED = 2
  readonly CONNECTING = 0
  readonly OPEN = 1
  readonly CLOSED = 2

  readyState = 0
  readonly withCredentials = false
  // The names it listens for, beyond its own handlers', for the stream to
  // listen for again each time it is opened
  readonly names = new Set<string>()
  onopen: Listener | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: Listener | null = null

  constructor(
    readonly url: string,
    readonly topic: string
  ) {
    super()
  }

  // As an EventSource's: a named event's listener is given a MessageEvent
  addEventListener(
    type: string,
    listener: (this: Source, event: MessageEvent<string>) => unknown,
    options?: boolean | AddEventListenerOptions
  ): void
  addEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject | null,
    options?: boolean | AddEventListenerOptions
  ): void
  addEventListener(
    type: string,
    listener:
      | ((this: Source, event: MessageEvent<string>) => unknown)
      | EventListenerOrEventListenerObject
      | null,
    options?: boolean | AddEventListenerOptions
  ): void {
    super.addEventListener(type, listener as EventListener | null, options)
    this.names.add(type)
    listen(this.topic, type)
  }

  close(): void {
    if (this.readyState === Source.CLOSED) return
    this.readyState = Source.CLOSED
    const sources = topics.get(this.topic)
    sources?.delete(this)
    if (sources?.size === 0) {
      topics.delete(this.topic)
      reopen()
    }
  }

  // An event of its topic's, as its EventSource would have had it
  hear(event: Event): void {
    this.dispatchEvent(event)
    if (event.type === 'open') this.onopen?.call(this, event)
    else if (event.type === 'error') this.onerror?.call(this, event)
    else if (event.type === 'message') {
      this.onmessage?.call(this, event as MessageEvent<string>)
    }
  }
}

// The topic url names: the app's own, relative to the prefix, or another's
function topicOf(url: string): string {
  const found = new URL(url, location.href)
  const below = new URL(prefix, location.href).pathname
  if (found.origin === location.origin && found.pathname.startsWith(below)) {
    return found.pathname.slice(below.length) + found.search
  }
  return found.href
}

// What a topic's sources hear of an event the hub sent
function deliver(topic: string, name: string, data: string): void {
  for (const source of [...(topics.get(topic) ?? [])]) {
    if (name === 'open') {
      source.readyState = Source.OPEN
      source.hear(new Event('open'))
    } else if (name === 'error') {
      // Not a stream, and not tried again, as an EventSource given a 404
      source.readyState = Source.CLOSED
      topics.get(topic)?.delete(source)
      source.hear(new Event('error'))
    } else {
      source.hear(new MessageEvent(name, { data, origin: location.origin }))
    }
  }
  if (name === 'error') topics.delete(topic)
}

// The open stream listening for a topic's event of a name
function listen(topic: string, name: string): void {
  const label = `${topic} ${name}`
  if (stream === undefined || heard.has(label)) return
  heard.add(label)
  stream.addEventListener(label, (event) => {
    deliver(topic, name, (event as MessageEvent<string>).data)
  })
}

// The stream opened again with the topics there are, once this turn is done
function reopen(): void {
  if (reopening) return
  reopening = true
  setTimeout(() => {
    reopening = false
    stream?.close()
    stream = undefined
    heard.clear()
    if (topics.size === 0) return
    const query = [...topics.keys()]
      .map((topic) => `topic=${encodeURIComponent(topic)}`)
      .join('&')
    stream = new EventSource(
      `${new URL(prefix, location.href).pathname}${HUB}?${query}`
    )
    // The connection to the hub lost: each source waits, as its own would
    stream.onerror = () => {
      for (const sources of topics.values()) {
        for (const source of sources) {
          source.readyState = Source.CONNECTING
          source.hear(new Event('error'))
        }
      }
    }
    for (const [topic, sources] of topics) {
      for (const name of HANDLED) listen(topic, name)
      for (const source of sources) {
        for (const name of source.names) listen(topic, name)
      }
    }
  }, 0)
}

function source(url: string): Source {
  const topic = topicOf(url)
  const made = new Source(url, topic)
  const sources = topics.get(topic) ?? new Set<Source>()
  const known = topics.has(topic)
  sources.add(made)
  topics.set(topic, sources)
  if (!known) reopen()
  return made
}

function at(where: string): void {
  prefix = where.endsWith('/') ? where : `${where}/`
}

export { source, at, Source }
