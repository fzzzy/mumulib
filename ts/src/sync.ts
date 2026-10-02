/**
 * Sync
 *
 * A path in the state tree bound to a URL on mumulib's Python server, and
 * kept the same as it: design/state-sync.md, part one.
 *
 * Functions:
 * - bind(path: string, url: string)
 *   Fetches <url>.json -- a resource's state, or a persist's document --
 *   puts it at path with state.set_path, and fetches it again whenever the
 *   change stream, /mumulib/changes.sse, announces url -- compared as paths
 *   on this origin, without an extension, a query or a fragment, a trailing
 *   slash kept. Resolves once the first fetch is in place.
 *
 * The client never changes a bound path itself. It writes with a PUT or a
 * DELETE, or a request a resource's handler answers, and its own change
 * comes back as anyone's does: announced, fetched, put in place. A page has
 * one change stream, opened by its first bind.
 */

import { set_path } from './state.js'

const CHANGES = '/mumulib/changes.sse'

type Binding = { path: string; url: string; fetches: number }

const bindings: Binding[] = []
let stream: EventSource | undefined

// A URL as the change stream compares them
function watched(url: string): string {
  const path = new URL(url, location.href).pathname
  if (path.endsWith('/')) return path
  const slash = path.lastIndexOf('/')
  const dot = path.lastIndexOf('.')
  return dot > slash + 1 ? path.slice(0, dot) : path
}

async function refresh(binding: Binding): Promise<void> {
  // Each fetch numbered: one overtaken by a later fetch is dropped, so an
  // older state never lands after a newer one
  const fetch_number = ++binding.fetches
  const response = await fetch(`${binding.url}.json`)
  if (!response.ok) {
    throw new Error(`${binding.url}.json answered ${response.status}`)
  }
  const document: unknown = await response.json()
  if (fetch_number === binding.fetches) {
    await set_path(binding.path, document)
  }
}

function listen(): void {
  stream = new EventSource(CHANGES)
  stream.onmessage = (event: MessageEvent<string>) => {
    const changed = watched(JSON.parse(event.data) as string)
    for (const binding of bindings) {
      if (binding.url === changed) {
        refresh(binding).catch((error: unknown) => console.error(error))
      }
    }
  }
}

async function bind(path: string, url: string): Promise<void> {
  if (!path) throw new Error('bind needs a path in the state tree')
  const binding = { path, url: watched(url), fetches: 0 }
  if (binding.url.endsWith('/')) {
    throw new Error(`${url} is a slash: bind a resource or a persist`)
  }
  bindings.push(binding)
  if (stream === undefined) listen()
  await refresh(binding)
}

export { bind }
