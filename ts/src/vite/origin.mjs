/**
 * Vite's dev server, named in full in the HTML it writes: for a page that
 * another server -- mumulib's Python one -- serves from its own origin.
 *
 *     // vite.config.ts
 *     import { originPlugin } from 'mumulib/vite-plugin-origin'
 *     export default defineConfig({
 *       base: '/mumulib-vite/',
 *       plugins: [originPlugin('http://127.0.0.1:5757')],
 *       server: { host: '127.0.0.1', port: 5757, strictPort: true },
 *     })
 *
 * In development Vite writes the URLs in an HTML entry root-relative,
 * `/mumulib-vite/notes/main.ts`, whatever `base` or `server.origin` say.
 * Served from another origin, they would be asked of that server. After
 * Vite's own transform, this puts the dev server's origin in front of each:
 * wherever the base appears quoted, `"/mumulib-vite/`. A base that
 * distinctive is in nothing else on a page, so the HTML is not parsed, or
 * matched by pattern, to find them. So it needs one: with Vite's default,
 * `/`, every quoted root-relative URL would be rewritten, the page's links
 * to its own server's pages among them, and the dev server refuses to start. The browser then fetches Vite's client,
 * the page's modules and its stylesheets from Vite, and the client opens
 * its hot reloading websocket to Vite, the host it was loaded from. It also
 * sets `server.origin`, so the asset URLs Vite writes into modules and CSS
 * name it too.
 *
 * An entry's own URLs are root-relative, `<script src="/notes/main.ts">`,
 * which Vite writes under the base. A relative one, `src="./main.ts"`, Vite
 * leaves as it is, and it would resolve against the other server's page: so
 * a relative `src`, or a relative `href` on a `<link>`, is an error, in
 * development and in a build alike, naming the entry and the URL. Links to
 * other pages, `<a href>`, are the page's own, and left alone.
 *
 * Nothing else needs it: imports inside the modules are root-relative and
 * resolve against the module's own URL, and Vite answers CORS for a page on
 * another of localhost's ports by default. It changes nothing in a build,
 * whose files the other server serves itself, under the base.
 *
 * Plain JavaScript, typed with JSDoc, so that it ships as it is.
 */

// Each src, and each <link>'s href: what a page loads, not where it links
const LOADS =
  /<(?:link\b[^>]*?\shref|[a-z][\w-]*\b[^>]*?\ssrc)\s*=\s*["']?([^"'\s>]+)/gi

/**
 * The URLs html loads relative to the page: neither root-relative nor with
 * a scheme of their own, as data: and https: have.
 *
 * @param {string} html
 * @returns {string[]}
 */
export function relativeLoads(html) {
  return [...html.matchAll(LOADS)]
    .map((match) => match[1])
    .filter((url) => !url.startsWith('/') && !/^[a-z][a-z0-9+.-]*:/i.test(url))
}

/**
 * html with each quoted URL under base naming origin in full.
 *
 * @param {string} html
 * @param {string} base
 * @param {string} origin
 * @returns {string}
 */
export function withOrigin(html, base, origin) {
  // split and join: replaceAll is ES2021, and the library targets ES2020
  return ['"', "'"].reduce(
    (text, quote) =>
      text.split(`${quote}${base}`).join(`${quote}${origin}${base}`),
    html
  )
}

/**
 * @param {string} origin The dev server's origin, as the browser reaches it
 * @returns {import('vite').Plugin[]}
 */
export function originPlugin(origin = 'http://127.0.0.1:5757') {
  let base = '/'
  return [
    {
      name: 'mumulib-origin:root-relative',
      // Before Vite's transform, on the entry as it was written
      transformIndexHtml: {
        order: 'pre',
        handler(html, { filename }) {
          const relative = relativeLoads(html)
          if (relative.length) {
            throw new Error(
              `${filename} loads ${relative.join(', ')} by a relative URL: ` +
                'write it root-relative, /<page>/<file>, which Vite puts ' +
                'under the base'
            )
          }
          return html
        },
      },
    },
    {
      name: 'mumulib-origin',
      apply: 'serve',
      config: () => ({ server: { origin } }),
      configResolved(config) {
        base = config.base
        if (base === '/') {
          throw new Error(
            'originPlugin needs a base of its own, such as /mumulib-vite/: ' +
              'it puts the dev server in front of every quoted URL under ' +
              'the base, and under /, that is every root-relative URL on ' +
              "the page, its links to the other server's pages too"
          )
        }
      },
      // After Vite's transform, which has written them under the base
      transformIndexHtml: {
        order: 'post',
        handler: (html) =>
          base.startsWith('/') ? withOrigin(html, base, origin) : html,
      },
    },
  ]
}
