// mumulib's live.js: keeps a page's live elements up to date.
//
// consumers_app(root, changes=...) serves this at /mumulib/live.js, and the
// change stream at /mumulib/changes.sse, which announces the URL of
// everything a request changes. tags.page(..., live=True) links it; a page
// of your own links it as any script, <script src="/mumulib/live.js" defer>.
//
// A live element has an id and data-live, and watches one URL: data-live's
// value, or with none the page's own. When a change announces that URL --
// compared as a path, without extension, query or fragment, a trailing slash
// kept, and exactly -- the page is fetched again, once for the change, and
// each element watching it is replaced by the element with the same id in
// the fresh page. Other elements are left as they are, and a change no
// element watches fetches nothing. A page with no live element opens no
// stream at all.

// A URL as live elements compare them: its path on this origin, without an
// extension on its last segment, or a query or a fragment. A trailing slash
// is kept: /editors/ is not /editors.
const watched = (url) => {
  const path = new URL(url, location.href).pathname
  if (path.endsWith('/')) return path
  const slash = path.lastIndexOf('/')
  const dot = path.lastIndexOf('.')
  return dot > slash + 1 ? path.slice(0, dot) : path
}

const live = () => document.querySelectorAll('[data-live][id]')

const watching = (element) =>
  watched(element.getAttribute('data-live') || location.href)

if (live().length) {
  new EventSource('/mumulib/changes.sse').onmessage = async (event) => {
    const changed = watched(JSON.parse(event.data))
    const stale = [...live()].filter((element) => watching(element) === changed)
    if (!stale.length) return
    const response = await fetch(location.href)
    if (!response.ok) return
    const html = await response.text()
    const fresh = new DOMParser().parseFromString(html, 'text/html')
    for (const element of stale) {
      const replacement = fresh.getElementById(element.id)
      if (replacement) element.replaceWith(replacement)
    }
  }
}
