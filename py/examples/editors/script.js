// The editors' one script, linked from every page: the tables kept up to
// date. Whenever the server says something changed -- anyone's change, from
// any page -- /editors/ is fetched again and its tables put in place of these.
new EventSource('/editors/changes.sse').onmessage = async () => {
  const html = await (await fetch('/editors/')).text()
  const page = new DOMParser().parseFromString(html, 'text/html')
  for (const table of document.querySelectorAll('table[id]')) {
    const fresh = page.getElementById(table.id)
    if (fresh) table.replaceWith(fresh)
  }
}
