// mumulib's live.js: keeps a page's data-live elements up to date.
//
// consumers_app(root, changes=...) serves this at /mumulib/live.js, and the
// change stream at /mumulib/changes.sse, which names the URL of everything a
// request changes. Whenever anything changes, the page's own URL is fetched
// again, and each data-live element with an id is replaced by the element
// with that id in the fresh page. tags.page(..., live=True) links it.
//
// A page with no data-live element opens no stream at all.
const live = () => document.querySelectorAll('[data-live][id]')

if (live().length) {
  new EventSource('/mumulib/changes.sse').onmessage = async () => {
    const response = await fetch(location.href)
    if (!response.ok) return
    const html = await response.text()
    const fresh = new DOMParser().parseFromString(html, 'text/html')
    for (const element of live()) {
      const replacement = fresh.getElementById(element.id)
      if (replacement) element.replaceWith(replacement)
    }
  }
}
