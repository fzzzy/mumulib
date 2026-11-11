# mumulib/vite-plugin-origin

`mumulib/vite-plugin-origin` is for pages another server serves -- mumulib's
Python server, with `static.Page` -- while Vite's dev server serves their
modules. In development, Vite writes the URLs in an HTML entry
root-relative, `/mumulib-vite/notes/main.ts`, which from the other server's
origin would be asked of it. `originPlugin(origin)` puts the dev server's
origin in front of each, wherever the base appears quoted -- a base as
distinctive as `/mumulib-vite/` is in nothing else on a page -- so the
browser fetches Vite's client and the page's modules from Vite, and hot
reloading connects to it. It needs that base: under Vite's default, `/`,
every root-relative URL on the page would be sent to Vite, links to the
other server's pages too, so the dev server refuses to start with it.

```ts
import { originPlugin } from 'mumulib/vite-plugin-origin'

export default defineConfig({
  base: '/mumulib-vite/',
  plugins: [originPlugin('http://127.0.0.1:5757')],
  server: { host: '127.0.0.1', port: 5757, strictPort: true },
})
```

An entry loads by root-relative URLs, `<script src="/notes/main.ts">`, which
Vite puts under the base. A relative `src`, or a relative `href` on a
`<link>`, would resolve against the other server's page, so the plugin
refuses the entry, naming it and the URL, in development and in a build
alike. It changes nothing else in a build.

`rootRelativePlugin()` is that check alone, for a server that serves the
page at its own path and passes the base on to Vite -- one origin, with
nothing to put in front -- as mumulib's Python does in development. This
repository's `ts/vite.pages.config.mts` uses it, for `ts/pages`.

```ts
import { rootRelativePlugin } from 'mumulib/vite-plugin-origin'

export default defineConfig({
  base: '/mumulib-vite/',
  plugins: [rootRelativePlugin()],
  server: { host: '127.0.0.1', port: 5757, strictPort: true },
})
```
