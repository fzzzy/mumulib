/**
 * Sync
 *
 * A path in the state tree bound to a URL on mumulib's Python server, and
 * kept the same as it: design/state-sync.md, part one.
 *
 * Functions:
 * - bind(path: string, url: string, options?: { exact?: boolean })
 *   Fetches <url>.json -- a resource's state, or a persist's document --
 *   puts it at path with state.set_path, and fetches it again whenever the
 *   change stream, /mumulib/changes.sse, announces url, or a URL inside it
 *   -- /presence/p7 for /presence: a change inside what was fetched is a
 *   change of it. With exact, url alone. Compared as paths on this origin,
 *   without an extension, a query or a fragment, a trailing slash kept.
 *   Resolves once the first fetch is in place.
 *
 * The client never changes a bound path itself. It writes with a PUT or a
 * DELETE, or a request a resource's handler answers, and its own change
 * comes back as anyone's does: announced, fetched, put in place. A page has
 * one change stream, opened by its first bind.
 */

import { source, type Source } from './events.js'
import { set_path } from './state.js'

const CHANGES = '/mumulib/changes.sse'

type Binding = { path: string; url: string; exact: boolean; fetches: number }

type BindOptions = {
  // Fetched again for url's own announcements alone, not those inside it
  exact?: boolean
}

const bindings: Binding[] = []
let stream: Source | undefined

// Whether an announcement, as watched makes it, is a change of a binding:
// its URL, or one inside it -- /presence/p7, /presence/ for /presence, and
// not /presences
function changes(binding: Binding, changed: string): boolean {
  if (changed === binding.url) return true
  return !binding.exact && changed.startsWith(`${binding.url}/`)
}

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
  // Over the page's one stream, the hub's, with whatever else it hears
  stream = source(CHANGES)
  stream.onmessage = (event: MessageEvent<string>) => {
    const changed = watched(JSON.parse(event.data) as string)
    for (const binding of bindings) {
      if (changes(binding, changed)) {
        refresh(binding).catch((error: unknown) => console.error(error))
      }
    }
  }
}

async function bind(
  path: string,
  url: string,
  options: BindOptions = {},
): Promise<void> {
  if (!path) throw new Error('bind needs a path in the state tree')
  const binding = {
    path,
    url: watched(url),
    exact: options.exact ?? false,
    fetches: 0,
  }
  if (binding.url.endsWith('/')) {
    throw new Error(`${url} is a slash: bind a resource or a persist`)
  }
  bindings.push(binding)
  if (stream === undefined) listen()
  await refresh(binding)
}

export { bind }
export type { BindOptions }
