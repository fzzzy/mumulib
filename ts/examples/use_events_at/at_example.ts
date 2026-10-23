// events.at: an app mounted below a prefix, here /examples, its hub below it
// too. The prefix comes from the query, ?at=, as the test gives it, with its
// slash or without. The hub is the test's own, src/events.spec.ts.
import { events } from 'mumulib'

events.at(new URLSearchParams(location.search).get('at') ?? '/')

const heard = document.querySelector<HTMLPreElement>('#heard')!
const say = (line: string) => (heard.textContent += `${line}\n`)

// Below the prefix: the app's own. Outside it, and on another origin:
// another server's, by its whole URL
const own = events.source('/examples/use_events_at/own.sse')
own.onmessage = (event) => say(`own ${event.data}`)
const outside = events.source('/outside.sse')
outside.onmessage = (event) => say(`outside ${event.data}`)
const remote = events.source('https://feeds.example/remote.sse')
remote.onmessage = (event) => say(`remote ${event.data}`)

// For the test: each closed, one of them twice
Object.assign(window, {
  closeAll: () => {
    for (const source of [own, outside, remote, own]) source.close()
  },
})
document.body.dataset.listening = 'true'
