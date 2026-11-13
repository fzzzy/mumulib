// events.source: three event streams over the hub's one, each heard as its
// own EventSource would be. The hub here is the test's own --
// src/events.spec.ts answers /mumulib/events.sse -- as mumulib's Python
// server would.
import { events } from 'mumulib'

const heard = document.querySelector<HTMLPreElement>('#heard')!
const say = (line: string) => (heard.textContent += `${line}\n`)

// The app's own, by an absolute path and a relative one
const news = events.source('/news.sse')
news.onopen = () => say(`news open ${news.readyState}`)
news.onmessage = (event) => say(`news ${event.data}`)

const weather = events.source('weather.sse')
// A named event's listener is given a MessageEvent, as an EventSource's is
weather.addEventListener('forecast', (event: MessageEvent<string>) =>
  say(`weather forecast ${event.data}`)
)

// One that is no stream: an error, and closed, as an EventSource's would be
const missing = events.source('/missing.sse')
missing.onerror = () => say(`missing error ${missing.readyState}`)

// For the test: one closed, and the stream opened again without it
Object.assign(window, { closeWeather: () => weather.close() })
document.body.dataset.listening = 'true'
