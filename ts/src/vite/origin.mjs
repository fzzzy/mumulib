/**
 * Vite's dev server, named in full in the HTML it writes: for a page that
 * another server -- mumulib's Python one -- serves from its own origin.
 *
 *     // vite.config.ts
 *     import { originPlugin } from 'mumulib/vite-plugin-origin'
 *     export default defineConfig({
 *       base: '/vite/',
 *       plugins: [originPlugin('http://127.0.0.1:5757')],
 *       server: { host: '127.0.0.1', port: 5757, strictPort: true },
 *     })
 *
 * In development Vite writes the URLs in an HTML entry root-relative,
 * `/vite/src/main.ts`, whatever `base` or `server.origin` say. Served from
 * another origin, they would be asked of that server. This puts the dev
 * server's origin in front of each `src` and `href` starting with the base,
 * after Vite's own transform, and resolves each relative one as the entry's
 * own URL on the dev server would. So the browser fetches Vite's client, the
 * page's modules and its stylesheets from Vite, and the client then opens
 * its hot reloading websocket to Vite, the host it was loaded from. It also
 * sets `server.origin`, so the asset URLs Vite writes into modules and CSS
 * name it too.
 *
 * Nothing else needs it: imports inside the modules are root-relative and
 * resolve against the module's own URL, and Vite answers CORS for a page on
 * another of localhost's ports by default. It does nothing to a build, whose
 * files the other server serves itself, under the base.
 *
 * Plain JavaScript, typed with JSDoc, so that it ships as it is.
 */

/**
 * url as the dev server's, in full: one under the base, or relative to the
 * page, as the page reached on the dev server would resolve it. Anything
 * else -- a full URL, another root-relative path, a fragment, data: -- is
 * null, and left as it was written.
 *
 * @param {string} url
 * @param {URL} page
 * @param {string} base
 * @returns {string | null}
 */
function named(url, page, base) {
  if (url.startsWith(base) && base.startsWith('/')) {
    return new URL(url, page).href
  }
  if (url === '' || url.startsWith('/') || url.startsWith('#')) return null
  if (/^[a-z][a-z0-9+.-]*:/i.test(url)) return null
  return new URL(url, page).href
}

/**
 * @param {string} origin The dev server's origin, as the browser reaches it
 * @returns {import('vite').Plugin}
 */
export function originPlugin(origin = 'http://127.0.0.1:5757') {
  let base = '/'
  return {
    name: 'mumulib-origin',
    apply: 'serve',
    config: () => ({ server: { origin } }),
    configResolved(config) {
      base = config.base
    },
    transformIndexHtml: {
      order: 'post',
      handler(html, { path }) {
        // The entry's own URL on the dev server: path is without the base
        const page = new URL(base.replace(/\/$/, '') + path, origin)
        return html.replace(
          /(\s(?:src|href)=)(["'])([^"']*)\2/g,
          (attribute, name, quote, url) => {
            const full = named(url, page, base)
            return full === null ? attribute : `${name}${quote}${full}${quote}`
          }
        )
      },
    },
  }
}
