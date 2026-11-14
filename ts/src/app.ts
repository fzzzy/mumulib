/**
 * The app: the one component on a page that has state of its own, and whose
 * template is the page itself. mountApp(Page) takes the body's markup, as
 * the page has it, sample content and all, as the app's template, and draws
 * the app there from then on -- or another element's, mountApp(Page, root),
 * for an app in part of a page -- no shadow root, so the page's own styles
 * reach it. It hands its state to the components in it as a component hands
 * its state to those inside it, by `data-prop`. They ask for changes with
 * events, which come back up to the app's methods by `data-on`, and the app
 * changes its state, which draws the page again.
 *
 *     <body>
 *       <my-opener data-prop="open=open" data-on="toggle=toggle"></my-opener>
 *       <div data-slot="panels">
 *         <my-panel data-pat="foreach" data-on="close=close"></my-panel>
 *       </div>
 *     </body>
 *
 *     class Page extends App<{ open: boolean }> {
 *       static state = { open: false }
 *       // What comes and goes is a list of none or one.
 *       get panels() {
 *         return this.state.open ? [{ key: 'panel' }] : []
 *       }
 *       toggle(): void {
 *         this.update({ open: !this.state.open })
 *       }
 *       close(): void {
 *         this.update({ open: false })
 *       }
 *     }
 *     mountApp(Page)
 *
 * Everything a Mumu component has, the app has: slots, data-attr,
 * data-prop, foreach lists, `on<Event>` methods, refs, onMount, onRender.
 * And beside them:
 *
 * - `this.update(change)` changes its state: the change is merged into it,
 *   by mumulib's state, and the page drawn again, once for the whole change.
 * - `data-on="close=closeDialog,retry=retry"` on any element of the page, in
 *   a foreach row too, calls the method named when the event named reaches
 *   it -- a component's own events, which `emit` sends out of every
 *   component around it, as well as the browser's.
 * - The state is frozen: the state object, and each value in it, one level
 *   down. A change is a new value, as a component sees only a new value as a
 *   change; frozen, an array pushed onto or an object assigned to throws
 *   where it happens, rather than showing nothing.
 * - There is one app on a page: mounting a second while the first is in the
 *   page throws.
 * - Define the page's custom elements before mounting it: the app sets their
 *   properties as it first draws.
 */
import { Mumu, mumuView } from './mumu.js'
import * as mumuState from './state.js'

// What a dialog's method is called with: its form's values, by name.
export type { FormArgs } from './controls.js'

/** A value frozen, if it is an object; its own values are not. */
function frozen<T>(value: T): T {
  return value !== null && typeof value === 'object'
    ? Object.freeze(value)
    : value
}

/** A change with each of its values frozen. */
function freezeValues<S extends object>(change: Partial<S>): Partial<S> {
  const out: Record<string, unknown> = {}
  for (const [key, value] of Object.entries(change)) out[key] = frozen(value)
  return Object.freeze(out) as Partial<S>
}

export class App<
  S extends object,
  R extends object = Record<string, HTMLElement>,
> extends Mumu<S, R> {
  /** Change the state: merged into it, each value frozen, and drawn. */
  protected update(change: Partial<S>): void {
    void mumuState.set_state(freezeValues(change))
  }
}

type AppClass = typeof App<object, object>

/** The `event=method` pairs of an element's data-on. */
function handlersOf(el: Element): Map<string, string> {
  const found = new Map<string, string>()
  for (const pair of (el.getAttribute('data-on') ?? '').split(',')) {
    const eq = pair.indexOf('=')
    const event = pair.slice(0, eq).trim()
    const method = pair.slice(eq + 1).trim()
    if (eq !== -1 && event && method) found.set(event, method)
  }
  return found
}

/** The elements with a data-on under node, in its templates' rows too. */
function withDataOn(node: ParentNode): Element[] {
  const found = Array.from(node.querySelectorAll('[data-on]'))
  for (const template of Array.from(node.querySelectorAll('template'))) {
    found.push(...withDataOn(template.content))
  }
  return found
}

/**
 * Every event any data-on in the page names, each checked against the app's
 * methods: one naming no method would never be called.
 */
function dataOnEvents(cls: AppClass, root: Element): Set<string> {
  const events = new Set<string>()
  for (const el of withDataOn(root)) {
    for (const [event, method] of handlersOf(el)) {
      if (
        typeof (cls.prototype as unknown as Record<string, unknown>)[method] !==
        'function'
      ) {
        throw new Error(
          `${cls.name} has no method ${method}, which data-on="${event}=${method}" calls`,
        )
      }
      events.add(event)
    }
  }
  return events
}

// Where the app on the page is drawn, while there is one.
let current: Element | null = null
// Whether the state has been given the app's own, the first time one mounts.
let seeded = false

/**
 * Draw the app in root -- the body, unless another element is given -- whose
 * markup is its template, from the state from now on. Its scripts go in the
 * head, then, a module script being deferred anyway: what is in the body is
 * the app's. The first app mounted starts the state from its `static state`;
 * one mounted again, after the first has left the page, draws the state as
 * it is.
 */
export function mountApp(cls: AppClass, root: Element = document.body): void {
  if (current?.isConnected) {
    throw new Error('There is one app on a page, and one is mounted already')
  }
  if (!(cls.prototype instanceof App))
    throw new Error(`${cls.name} is not an App`)
  current = root

  // data-on, read before the first render puts rows in: each event heard
  // once, at root, as it goes down -- so one that does not bubble is heard
  // too -- and handed to the method the nearest element on its way names.
  const events = dataOnEvents(cls, root)
  // A bound control's change is a change of the app's state: by update(),
  // which an app may have go through something else -- a store, say.
  const view = mumuView<Record<string, unknown>>(cls, root, (change) =>
    (view.delegate as unknown as App<object>)['update'](change),
  )
  const delegate = view.delegate as unknown as Record<
    string,
    (event: Event) => void
  >
  for (const event of events) {
    root.addEventListener(
      event,
      (e) => {
        for (const node of e.composedPath()) {
          if (node === root) return
          // Only the page's own elements: not those inside a component.
          if (
            !(node instanceof Element) ||
            node.getRootNode() !== root.getRootNode()
          )
            continue
          const method = handlersOf(node).get(event)
          if (method) {
            delegate[method].call(delegate, e)
            return
          }
        }
      },
      true,
    )
  }

  const keys = Object.keys(cls.state)
  void mumuState.onstate(async (s: Record<string, unknown>) => {
    // An app that has left the page draws nothing: mumulib's state cannot
    // forget a callback yet.
    if (current !== root) return
    const change: Record<string, unknown> = {}
    for (const key of keys) if (key in s) change[key] = frozen(s[key])
    view.set(change)
  })
  if (!seeded) {
    seeded = true
    void mumuState.set_state(freezeValues(cls.state as Partial<object>))
  } else {
    void mumuState.set_state(null)
  }
}
