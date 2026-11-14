/**
 * Pure components as delegates: a component is a plain class that reads its
 * state, says how it is shown, and asks for changes by emitting events. It is
 * no element, and touches no DOM. An element class kept here, out of sight,
 * stands in front of it and speaks the element protocol on its behalf.
 *
 *     <template>
 *       <button data-slot="label" data-attr="class=classes">Open</button>
 *     </template>
 *     <script>
 *       export default class Opener extends Mumu<{ open: boolean }> {
 *         static template = template
 *         static state = { open: false }
 *
 *         get label(): string {
 *           return this.state.open ? 'Close' : 'Open'
 *         }
 *         get classes(): string {
 *           return this.state.open ? 'open' : ''
 *         }
 *         onClick(): void {
 *           this.emit('toggle')
 *         }
 *       }
 *     </script>
 *
 * `mumuElement(Component)` makes the element class that stands in front of
 * a component, for customElements.define; its `delegate` is the component.
 * A class that is already an element comes back as it is -- the way out, for
 * a component that needs the element itself, a canvas say.
 *
 * State. `static state` names the element's properties and gives their
 * defaults. Setting one -- `el.open = true` -- replaces the
 * state, frozen, and renders; setting one to the value it already has does
 * neither. The component reads it as `this.state`, and
 * cannot change it: a setter in a component is an error.
 *
 * Render. Every `data-slot`, and every slot a `data-attr` names, is filled
 * with the state property of that name, or else the component's property of
 * that name -- a getter that works out what the view shows. A boolean adds
 * or removes the attribute it fills, as `disabled` wants. `data-prop` sets
 * an element's properties instead -- `data-prop="value=level"` -- which is
 * also how one component hands state to another inside it. A slot with a
 * row inside it, an element marked `data-pat="foreach"` -- or a `<template>`
 * so marked, holding the row, inert until it is copied -- takes a list: each
 * item, an object of slot values, fills a copy of the row, its `data-prop`
 * properties included -- so a row can be another component. Any slot may
 * have one, and only one; a list of objects for a slot with none is an
 * error, as is a second row in one slot. Rows are kept from one list
 * to the next, each matched to an item by the item's `key`, or by position
 * if it has none, and filled again only when its item's values change.
 * A slot is filled only when its value is not the very one it last had, so a
 * render writes only what changed.
 *
 * Events. A component method named `on` and a DOM event, in any case --
 * `onClick(event)`, `onKeyDown`, `onPointerCancel` -- is called for that event
 * anywhere in the shadow root, whether or not it bubbles. One named for no
 * event an element has is an error. `emit(name,
 * detail)` dispatches a custom event from the element, for the state's owner:
 * it bubbles out of every component it is nested in, to wherever the state
 * is kept.
 *
 * Focus. The element passes focus to what is inside it, and an element
 * marked `autofocus` in the template takes it as the component appears.
 *
 * Its own elements. `data-ref="name"` puts an element in `this.refs`, and a
 * component may do what it likes with its own elements -- it is only the
 * state it may not change. `onMount()`, if it has one, is called once, as
 * the component first appears: to open its dialog, say. `onRender()` is
 * called after every render: to redraw a canvas.
 *
 * Define the elements before anything creates one: an element made, and its
 * state set, ahead of customElements.define would hide its state properties.
 *
 *     import Opener from './opener.sfc.html'
 *     customElements.define('my-opener', mumuElement(Opener))
 */
import * as patslot from './patslot.js'
import type { Pattern } from './patslot.js'
import { show, read, isControl, form_args, claimed } from './controls.js'
import type { FormArgs } from './controls.js'

/**
 * Interaction timing, if a page installs it as `globalThis.__mumuPerf`: told
 * each step from an event to the render it causes. Nothing, otherwise.
 */
function perf():
  { step(what: string): void; handled(event: string): void } | undefined {
  return (globalThis as { __mumuPerf?: ReturnType<typeof perf> }).__mumuPerf
}

/** A row holder's rows: each by its key, with the item it was filled from. */
type Rows = Map<unknown, { row: Element; item: Record<string, unknown> }>

/** Whether two items have the same values, each the very same one. */
/**
 * A kept row put where it now belongs, keeping what is in it: the focus,
 * and a field's selection. Moved, a row is taken out of the page and put
 * back, which takes the focus from whatever in it had it -- the reader's
 * place, as another's change reorders the list. Where the browser has
 * moveBefore, the row keeps it as it moves; elsewhere it is given back.
 */
function moveRow(holder: Element, row: Element, before: Element | null): void {
  const moving = holder as Element & {
    moveBefore?: (node: Node, child: Node | null) => void
  }
  if (typeof moving.moveBefore === 'function') {
    try {
      moving.moveBefore(row, before)
      return
    } catch {
      // Not movable so -- another document, say -- and so put as any is
    }
  }
  // What has the focus, as deep as it goes: into each component's own root
  const root = holder.getRootNode() as Document | ShadowRoot
  let focused: Element | null = root.activeElement
  if (!focused || !row.contains(focused)) {
    holder.insertBefore(row, before)
    return
  }
  while (focused.shadowRoot?.activeElement) {
    focused = focused.shadowRoot.activeElement
  }
  const field =
    focused instanceof HTMLInputElement ||
    focused instanceof HTMLTextAreaElement
      ? focused
      : null
  const selection = field
    ? ([field.selectionStart, field.selectionEnd] as const)
    : null
  holder.insertBefore(row, before)
  ;(focused as HTMLElement).focus({ preventScroll: true })
  if (field && selection && selection[0] !== null) {
    field.setSelectionRange(selection[0], selection[1])
  }
}

function sameValues(
  a: Record<string, unknown>,
  b: Record<string, unknown>,
): boolean {
  const keys = Object.keys(a)
  return (
    keys.length === Object.keys(b).length &&
    keys.every((k) => k in b && a[k] === b[k])
  )
}

// Each element's fill still under way, while one is.
const filling = new WeakMap<Element, Promise<void>>()

/**
 * Fill an element's slots, after any fill of it still under way. patslot's
 * fill is asynchronous -- it waits between slots, as a slot may be a promise
 * -- so two in a row, a property set and then another, would interleave, and
 * the first's later slots land over the second's. While every render filled
 * every slot, the last render's fill put that right; one that fills only the
 * slots that changed does not, so fills go one after another. One with none
 * ahead of it starts at once, as before.
 */
function fillInOrder(el: Element, values: Record<string, Pattern>): void {
  const ahead = filling.get(el)
  // patslot's types say HTMLElement; it fills any element, SVG too.
  const fill = () => patslot.fill(el as HTMLElement, values)
  const done: Promise<void> = ahead ? ahead.then(fill) : fill()
  filling.set(el, done)
  void done.finally(() => {
    if (filling.get(el) === done) filling.delete(el)
  })
}

/** No rows: one list, so that "still none" is the same list as last time. */
const NONE: Record<string, unknown>[] = []

/**
 * Every event a component can handle, by the method named for it: `on` and
 * the event's name, in any case -- `onClick`, `onKeyDown`, `onPointerCancel`.
 * The events of elements in the HTML standard (its GlobalEventHandlers), and
 * of the standards beside it: UI Events' focus and composition, Pointer and
 * Touch Events, CSS Animations and Transitions, the Clipboard and Fullscreen
 * APIs. Chromium and WebKit agree on all of these but the touch events, which
 * a browser offers only on a touch screen, and focusin and focusout, which
 * Chromium has no handler property for though it fires them. Vendor-prefixed
 * events, and those only one engine has, are left out.
 */
const EVENTS = new Set([
  // Mouse, and the clicks any pointer makes
  'auxclick',
  'click',
  'contextmenu',
  'dblclick',
  'mousedown',
  'mouseenter',
  'mouseleave',
  'mousemove',
  'mouseout',
  'mouseover',
  'mouseup',
  'wheel',
  // Pointer Events
  'gotpointercapture',
  'lostpointercapture',
  'pointercancel',
  'pointerdown',
  'pointerenter',
  'pointerleave',
  'pointermove',
  'pointerout',
  'pointerover',
  'pointerup',
  // Touch Events
  'touchcancel',
  'touchend',
  'touchmove',
  'touchstart',
  // Keyboard, and composing text with an input method
  'keydown',
  'keypress',
  'keyup',
  'compositionend',
  'compositionstart',
  'compositionupdate',
  // Focus
  'blur',
  'focus',
  'focusin',
  'focusout',
  // Forms and editing
  'beforeinput',
  'change',
  'formdata',
  'input',
  'invalid',
  'reset',
  'select',
  'selectionchange',
  'selectstart',
  'submit',
  // Clipboard
  'copy',
  'cut',
  'paste',
  // Drag and drop
  'drag',
  'dragend',
  'dragenter',
  'dragleave',
  'dragover',
  'dragstart',
  'drop',
  // Dialogs, popovers, <details>, and invoker commands
  'beforetoggle',
  'cancel',
  'close',
  'command',
  'toggle',
  // Scrolling and size
  'resize',
  'scroll',
  'scrollend',
  // CSS Animations and Transitions
  'animationcancel',
  'animationend',
  'animationiteration',
  'animationstart',
  'transitioncancel',
  'transitionend',
  'transitionrun',
  'transitionstart',
  // Loading: images, scripts, iframes, media
  'abort',
  'error',
  'load',
  'loadeddata',
  'loadedmetadata',
  'loadstart',
  'progress',
  // Media playback
  'canplay',
  'canplaythrough',
  'cuechange',
  'durationchange',
  'emptied',
  'ended',
  'pause',
  'play',
  'playing',
  'ratechange',
  'seeked',
  'seeking',
  'stalled',
  'suspend',
  'timeupdate',
  'volumechange',
  'waiting',
  // Fullscreen, content-visibility, find-in-page, and slots
  'beforematch',
  'contentvisibilityautostatechange',
  'fullscreenchange',
  'fullscreenerror',
  'slotchange',
])

/** A component's own methods that are called but handle no event. */
const LIFECYCLE = new Set(['onMount', 'onRender'])

/** What the element gives its delegate: the state, and a way to emit. */
interface Link {
  state: object
  emit: (name: string, detail?: unknown) => void
  refs: Record<string, Element>
  /**
   * The owner of the state, if this is it -- an app -- which takes a bound
   * control's change as a change of its state. Anything else hands the
   * change up to its owner, the way it came.
   */
  commit?: (change: Record<string, unknown>) => void
}

/** A control's name that binds it to the state: `this.draft`, the state's draft. */
const BOUND = 'this.'
const BOUND_SELECTOR = '[name^="this."]'
/** What a component sends up, for its owner, as a bound control changes. */
const BIND = 'mumu-bind'

interface Bind {
  path: string[]
  value: unknown
}

/** The path in the state a control's name binds it to, if it is bound. */
function boundPath(el: Element): string[] | null {
  const name = el.getAttribute('name')
  return name?.startsWith(BOUND) ? name.slice(BOUND.length).split('.') : null
}

/** What is at a path in a value. */
function getIn(value: unknown, path: string[]): unknown {
  for (const key of path) {
    if (value === null || typeof value !== 'object') return undefined
    value = (value as Record<string, unknown>)[key]
  }
  return value
}

/**
 * A value with what is at a path in it replaced: each object along the path
 * copied, and frozen, and everything off it the very same, so that what did
 * not change is still `===` what it was.
 */
function setIn(value: unknown, path: string[], to: unknown): unknown {
  if (!path.length) return to
  const [key, ...rest] = path
  const copy = (
    Array.isArray(value) ? [...(value as unknown[])] : { ...(value as object) }
  ) as Record<string, unknown>
  copy[key] = setIn(copy[key], rest, to)
  return Object.freeze(copy)
}

/** The elements under node, itself included, matching a selector. */
function within(node: ParentNode, selector: string): Element[] {
  const found = Array.from(node.querySelectorAll(selector))
  if (node instanceof Element && node.matches(selector)) found.unshift(node)
  return found
}

const links = new WeakMap<object, Link>()

/** The element's own method for a state property's setter; no name to collide with. */
const UPDATE = Symbol('update')

export class Mumu<
  S extends object,
  R extends object = Record<string, HTMLElement>,
> {
  /** The component's `<template>`, as its .sfc.html script sees it. */
  static template: HTMLTemplateElement
  /** Each state property the element takes, with its default. */
  static state: object = {}

  /** The state as last set by its owner: read-only, and frozen. */
  protected get state(): Readonly<S> {
    return links.get(this)!.state as Readonly<S>
  }

  /** Ask for a change: a custom event from the element, for the state's owner. */
  protected emit(name: string, detail?: unknown): void {
    links.get(this)!.emit(name, detail)
  }

  /**
   * The template's elements marked `data-ref="name"`, by name: the ones the
   * component works with itself. A component may do what it likes with its
   * own elements -- read a form, open a dialog, draw on a canvas -- but not
   * with the state, which it only reads. Filled as the component first
   * appears; one inside a row pattern is not among them, there being one per
   * row.
   */
  protected get refs(): R {
    return links.get(this)!.refs as R
  }
}

type Delegate = typeof Mumu<object, object>

/**
 * The slot names a template fills -- data-slot values and data-attr slots --
 * and the row pattern, if any, inside each slot; and, apart, the slots its
 * data-prop properties are set from. What is inside a pattern is the
 * pattern's own, filled once per row, and not the template's.
 */
function slotsOf(
  markup: ParentNode,
  name: string,
): {
  slots: string[]
  rows: Map<string, Element>
  props: string[]
} {
  const names = new Set<string>()
  const props = new Set<string>()
  const rows = new Map<string, Element>()
  const own = (el: Element) => !el.closest('[data-pat]')
  for (const el of Array.from(markup.querySelectorAll('[data-slot]')).filter(
    own,
  )) {
    const slot = el.getAttribute('data-slot')!
    names.add(slot)
    // The slot's own row: not one inside another pattern in it.
    const found = Array.from(
      el.querySelectorAll('[data-pat="foreach"]'),
    ).filter((row) => !row.parentElement!.closest('[data-pat]'))
    if (found.length > 1) {
      throw new Error(
        `${name}'s slot ${slot} has ${found.length} data-pat="foreach" rows; a list has one`,
      )
    }
    if (found.length) rows.set(slot, rowOf(found[0], name, slot))
  }
  for (const el of Array.from(markup.querySelectorAll('[data-attr]')).filter(
    own,
  )) {
    for (const [, slot] of pairs(el, 'data-attr')) names.add(slot)
  }
  for (const el of Array.from(markup.querySelectorAll('[data-prop]')).filter(
    own,
  )) {
    for (const [, slot] of pairs(el, 'data-prop')) props.add(slot)
  }
  return { slots: [...names], rows, props: [...props] }
}

/**
 * A slot's row: the element marked, or, if that is a `<template>`, the one
 * element inside it. A row in a template is inert until it is copied in --
 * a component in it is not made, and does nothing -- which a page whose
 * markup is an app's template wants, its rows being in the page as it loads.
 */
function rowOf(marked: Element, name: string, slot: string): Element {
  if (!(marked instanceof HTMLTemplateElement)) return marked
  const elements = marked.content.children
  if (elements.length !== 1) {
    throw new Error(
      `${name}'s slot ${slot} has a data-pat="foreach" template with ${elements.length} elements in it; a row is one`,
    )
  }
  // Marked as a row, as one written without a template is: what fills the
  // component's own elements passes over its rows, whose are their items'.
  const row = elements[0].cloneNode(true) as Element
  row.setAttribute('data-pat', 'foreach')
  return row
}

/** An element's `name=slot` pairs, from data-attr or data-prop. */
function pairs(el: Element, attribute: string): [string, string][] {
  const found: [string, string][] = []
  for (const pair of (el.getAttribute(attribute) ?? '').split(',')) {
    const eq = pair.indexOf('=')
    const name = pair.slice(0, eq).trim()
    const slot = pair.slice(eq + 1).trim()
    if (eq !== -1 && name && slot) found.push([name, slot])
  }
  return found
}

/** The component's own properties, nearest class first, down to Mumu. */
function propertiesOf(cls: Delegate): Map<string, PropertyDescriptor> {
  const found = new Map<string, PropertyDescriptor>()
  let proto = cls.prototype as object | null
  while (proto && proto !== Mumu.prototype) {
    for (const [key, d] of Object.entries(
      Object.getOwnPropertyDescriptors(proto),
    )) {
      if (key !== 'constructor' && !found.has(key)) found.set(key, d)
    }
    proto = Object.getPrototypeOf(proto) as object | null
  }
  return found
}

/** What a component is, worked out once from its class and its markup. */
interface Shape {
  name: string
  defaults: object
  keys: string[]
  slots: string[]
  rows: Map<string, Element>
  props: string[]
  handlers: [string, string][]
  onMount: (() => void) | undefined
  onRender: (() => void) | undefined
}

/**
 * A component's shape: its state, the slots its markup fills, and the
 * methods it has for events and for its own life. A component that would
 * change its state, or has a method named for no event, is refused.
 */
function shapeOf(component: Delegate, markup: ParentNode): Shape {
  const name = component.name
  const defaults = component.state
  const keys = Object.keys(defaults)
  const properties = propertiesOf(component)
  const { slots, rows, props } = slotsOf(markup, name)

  for (const [key, d] of properties) {
    if (d.set) {
      throw new Error(
        `${name} defines a setter for ${key}: a component only reads its state, ` +
          'and asks for changes with emit()',
      )
    }
  }
  for (const key of keys) {
    if (properties.has(key))
      throw new Error(`${name} defines ${key}, which is a state property`)
  }
  // Each `on` method and the event it handles. One named for no event --
  // `onClik` -- would never be called, so it is refused here instead.
  const handlers: [string, string][] = []
  for (const [method, d] of properties) {
    if (!/^on[A-Z]/.test(method) || LIFECYCLE.has(method)) continue
    if (typeof d.value !== 'function') continue
    const event = method.slice(2).toLowerCase()
    if (!EVENTS.has(event)) {
      throw new Error(
        `${name}.${method} is named for no event: "${event}" is not one an element has`,
      )
    }
    handlers.push([event, method])
  }
  checkBindings(name, markup, rows, keys, properties)
  return {
    name,
    defaults,
    keys,
    slots,
    rows,
    props,
    handlers,
    onMount: properties.get('onMount')?.value as (() => void) | undefined,
    onRender: properties.get('onRender')?.value as (() => void) | undefined,
  }
}

/**
 * What binds to the state, and what a dialog calls, checked as the component
 * is defined. A bound control binds through the state: its path starts with
 * a state property -- not a getter, which only presents the state and has
 * nothing to write to -- and one in a row binds through the row's item, so
 * the row's list is a state property. A dialog does not bind: what is typed
 * in it is a draft, given to the method its form names, as it is submitted.
 */
function checkBindings(
  name: string,
  markup: ParentNode,
  rows: Map<string, Element>,
  keys: string[],
  properties: Map<string, PropertyDescriptor>,
): void {
  const own = within(markup, BOUND_SELECTOR).filter(
    (el) => !el.closest('[data-pat]'),
  )
  const scopes: [Element[], string | null][] = [[own, null]]
  for (const [slot, row] of rows)
    scopes.push([within(row, BOUND_SELECTOR), slot])
  for (const [bound, slot] of scopes) {
    for (const el of bound) {
      const what = el.getAttribute('name')!
      if (el.closest('dialog')) {
        throw new Error(
          `${name} binds ${what} in a dialog: a dialog's form is a draft, ` +
            'given to its method as it is submitted',
        )
      }
      const top = slot ?? boundPath(el)![0]
      if (!keys.includes(top)) {
        throw new Error(
          slot
            ? `${name}'s ${slot} rows bind ${what}, but ${slot} is not in its state: ` +
                'a getter only presents the state, and cannot be written to'
            : `${name} binds ${what}, but ${top} is not in its state: ` +
                'a getter only presents the state, and cannot be written to',
        )
      }
    }
  }
  const forms = [markup, ...rows.values()].flatMap((node) =>
    within(node, 'dialog form input[name="method"]'),
  )
  for (const input of forms) {
    const method = (input as HTMLInputElement).value
    if (typeof properties.get(method)?.value !== 'function') {
      throw new Error(
        `${name} has no method ${method}, which its dialog's form calls`,
      )
    }
  }
}

/**
 * A component drawn into a root: a component element's shadow root, or
 * markup already in a page. It holds what was last drawn there, so that a
 * render writes only what changed.
 */
class View {
  readonly shape: Shape
  readonly delegate: Mumu<object, object>
  readonly link: Link
  #root: Element | ShadowRoot | null = null
  // What each data-prop property was last set to, per element.
  #set = new WeakMap<Element, Map<string, unknown>>()
  // The value each slot was last filled with.
  #filled = new Map<string, unknown>()
  // The list each row slot was last filled from.
  #rowsShown = new Map<string, unknown>()
  // Each row holder's rows, by key, with the item each was filled from.
  #rows = new WeakMap<Element, Rows>()
  // What each bound control was last shown.
  #shown = new WeakMap<Element, unknown>()

  constructor(shape: Shape, delegate: Mumu<object, object>, link: Link) {
    this.shape = shape
    this.delegate = delegate
    this.link = link
  }

  get attached(): boolean {
    return this.#root !== null
  }

  /**
   * Start drawing into root, whose markup is the component's: find its
   * refs, listen for its events, render, and let the component know it has
   * appeared.
   */
  attach(root: Element | ShadowRoot): void {
    const { name, handlers, onMount } = this.shape
    this.#root = root
    for (const el of Array.from(root.querySelectorAll('[data-ref]'))) {
      if (!el.closest('[data-pat]'))
        this.link.refs[el.getAttribute('data-ref')!] = el
    }
    const delegate = this.delegate as unknown as Record<
      string,
      (event: Event) => void
    >
    // In the capture phase, so that events that do not bubble -- a dialog's
    // close, say -- are heard too.
    for (const [event, method] of handlers) {
      root.addEventListener(
        event,
        (e) => {
          if (event === 'click') perf()?.step(`${name}.${method}`)
          delegate[method].call(delegate, e)
        },
        true,
      )
    }
    // Bound controls, both ways: what the state says shows in them as it
    // renders, and what is typed goes to the state's owner. Listened for as
    // they bubble, so the innermost component hears its own first.
    root.addEventListener('input', (e) => this.#input(e))
    root.addEventListener(BIND, (e) => this.#bind(e as CustomEvent<Bind>))
    root.addEventListener('submit', (e) => this.#submit(e as SubmitEvent))
    // Markup in the page: its this.* controls are not the state module's.
    if (root instanceof Element) claimed.add(root)
    this.render()
    // What the component does with its own elements as it appears: opens its
    // dialog, say. Before autofocus, which cannot reach into a dialog still
    // closed.
    if (typeof onMount === 'function') onMount.call(this.delegate)
    // An element marked autofocus in the template takes the focus as the
    // component first appears -- through a child component, too, which
    // passes it on to its own.
    const autofocus = root.querySelector('[autofocus]')
    if (autofocus instanceof HTMLElement) autofocus.focus()
  }

  /**
   * Change the state, all of the change at once, and render once. Values
   * that are the very ones the state already has change nothing, and a
   * change of nothing renders nothing: an owner may set its whole state again
   * without asking what changed.
   */
  set(change: Record<string, unknown>): void {
    const state = this.link.state as Record<string, unknown>
    if (Object.keys(change).every((key) => state[key] === change[key])) return
    this.link.state = Object.freeze({ ...state, ...change })
    this.render()
  }

  render(): void {
    const root = this.#root
    if (!root) return
    const { name, slots, rows, props, onRender } = this.shape
    const state = this.link.state as Record<string, Pattern>
    const delegate = this.delegate as unknown as Record<string, Pattern>
    const values: Record<string, Pattern> = {}
    for (const slot of slots) {
      const value = slot in state ? state[slot] : delegate[slot]
      // A slot whose value is the very one it was last filled with is already
      // showing it: neither its text nor its attributes are written again, so
      // a render touches only what changed.
      if (this.#filled.has(slot) && this.#filled.get(slot) === value) continue
      this.#filled.set(slot, value)
      // A boolean fills an attribute by its presence -- `disabled`, say --
      // which patslot cannot do: it always writes a value, and any value of a
      // boolean attribute, "false" too, means true.
      if (typeof value === 'boolean') {
        this.#toggle(slot, value)
        continue
      }
      // A slot holding a row pattern takes a list: one copy of the row for
      // each item, filled with the item's own slot values.
      const pattern = rows.get(slot)
      if (pattern) {
        const items = Array.isArray(value)
          ? (value as unknown as Record<string, unknown>[])
          : NONE
        this.#fillRows(slot, pattern, items)
        continue
      }
      // A list of objects is rows, and this slot has none to fill: patslot
      // would show each as "[object Object]".
      if (
        Array.isArray(value) &&
        value.some((v) => typeof v === 'object' && v && !(v instanceof Node))
      ) {
        throw new Error(
          `${name}'s ${slot} is a list of objects, but its slot has no data-pat="foreach" row`,
        )
      }
      values[slot] = value
    }
    if (Object.keys(values).length) {
      for (const element of Array.from(root.children)) {
        if (
          element instanceof HTMLElement &&
          !(element instanceof HTMLStyleElement)
        ) {
          fillInOrder(element, values)
        }
      }
    }
    if (props.length) this.#setProps(root)
    this.#showBound(root)
    // What the component does with its own elements after each render:
    // redraw a canvas, say. Rows still being filled may not be in yet.
    if (typeof onRender === 'function') onRender.call(this.delegate)
  }

  /**
   * Set each data-prop property from its slot: an input's `value`, say, or a
   * child component's state. Only when the slot's value has changed since it
   * was last set here. A range input the user is dragging holds its own value
   * until its owner answers; setting the old one back on every render in
   * between would snap it back under the pointer.
   */
  #setProps(root: Element | ShadowRoot): void {
    const state = this.link.state as Record<string, unknown>
    const delegate = this.delegate as unknown as Record<string, unknown>
    for (const el of Array.from(root.querySelectorAll('[data-prop]'))) {
      if (el.closest('[data-pat]')) continue
      let set = this.#set.get(el)
      if (!set) this.#set.set(el, (set = new Map()))
      for (const [name, slot] of pairs(el, 'data-prop')) {
        const value = slot in state ? state[slot] : delegate[slot]
        if (set.has(name) && set.get(name) === value) continue
        ;(el as unknown as Record<string, unknown>)[name] = value
        set.set(name, value)
      }
    }
  }

  /**
   * Show the state in each bound control, when what it binds to has changed
   * since it was last shown. A control being typed in shows what was typed,
   * which is already what the state has; one the state changes under it --
   * a draft cleared as it is added -- shows the change.
   */
  #showBound(root: Element | ShadowRoot): void {
    const state = this.link.state
    for (const el of Array.from(root.querySelectorAll(BOUND_SELECTOR))) {
      if (el.closest('[data-pat]') || !isControl(el)) continue
      const value = getIn(state, boundPath(el)!)
      if (this.#shown.has(el) && this.#shown.get(el) === value) continue
      this.#shown.set(el, value)
      show(el, value)
    }
  }

  /** Where in the state what is in a row is: the row's list, and its place. */
  #scopeOf(el: Element): string[] {
    const row = el.closest('[data-pat="foreach"]')
    if (!row) return []
    const holder = row.parentElement!
    const slot = holder.getAttribute('data-slot')!
    if (!this.shape.keys.includes(slot)) {
      throw new Error(
        `${this.shape.name}'s ${slot} rows bind, but ${slot} is not in its state: ` +
          'a getter only presents the state, and cannot be written to',
      )
    }
    const items = this.#rowsShown.get(slot) as unknown[]
    for (const { row: shown, item } of this.#rows.get(holder)?.values() ?? []) {
      if (shown === row) return [slot, String(items.indexOf(item))]
    }
    throw new Error(`${this.shape.name}'s ${slot} has a row it did not draw`)
  }

  /** A bound control of this component's changed: the state's, there. */
  #input(e: Event): void {
    const el = e.target
    if (!isControl(el)) return
    const path = boundPath(el)
    if (!path || el.closest('dialog')) return
    this.#commit([...this.#scopeOf(el), ...path], read(el))
  }

  /**
   * A component inside this one changed its state, there: the state it was
   * given by data-prop, so this component's, where that came from.
   */
  #bind(e: CustomEvent<Bind>): void {
    e.stopPropagation()
    const host = e.target as Element
    const [key, ...rest] = e.detail.path
    const from = pairs(host, 'data-prop').find(([name]) => name === key)?.[1]
    if (!from) {
      throw new Error(
        `<${host.localName}> binds its ${key}, which ${this.shape.name} does not give it by data-prop`,
      )
    }
    const scope = this.#scopeOf(host)
    if (!scope.length && !this.shape.keys.includes(from)) {
      throw new Error(
        `<${host.localName}> binds its ${key}, which ${this.shape.name} gives it from ${from}: ` +
          'a getter only presents the state, and cannot be written to',
      )
    }
    this.#commit([...scope, from, ...rest], e.detail.value)
  }

  /** Change the state at a path: the app's own, or else its owner's. */
  #commit(path: string[], value: unknown): void {
    const state = this.link.state as Record<string, unknown>
    if (getIn(state, path) === value) return
    if (this.link.commit) {
      const [key, ...rest] = path
      this.link.commit({ [key]: setIn(state[key], rest, value) })
    } else {
      this.link.emit(BIND, { path, value } satisfies Bind)
    }
  }

  /**
   * A dialog's form submitted: its method, named by its `method` input, is
   * called with the form's values, and the dialog closes. A submit button
   * whose value is `cancel` closes it and calls nothing, as Escape does.
   */
  #submit(e: SubmitEvent): void {
    const form = e.target
    if (!(form instanceof HTMLFormElement)) return
    const dialog = form.closest('dialog')
    const named = form.querySelector<HTMLInputElement>('input[name="method"]')
    if (!dialog || !named) return
    e.preventDefault()
    const button = e.submitter
    const returnValue =
      button instanceof HTMLButtonElement || button instanceof HTMLInputElement
        ? button.value
        : ''
    if (returnValue !== 'cancel') {
      const args: FormArgs = form_args(form)
      delete args['method']
      const delegate = this.delegate as unknown as Record<
        string,
        (args: FormArgs) => void
      >
      delegate[named.value].call(delegate, args)
    }
    dialog.close(returnValue)
  }

  /**
   * Put one copy of the row in the slot for each item, and fill it from the
   * item: its slots and attributes by patslot, its data-prop properties here.
   * The copies go in as they are, not cloned again as patslot would, so the
   * properties stay -- and they are set once the copies are in the page,
   * where a component in a row has become itself.
   *
   * A row is kept from one list to the next. Each is matched to an item by
   * the item's `key`, if it has one, or else by its place in the list: so a
   * line added to the end of a list adds a row and touches none of the
   * others, and a list whose items come and go from anywhere -- the chat
   * floating over the town, its oldest message leaving -- gives each item a
   * key. A kept row is filled again only if its item's values are not the
   * same ones, compared one by one, as the row was last filled from.
   */
  #fillRows(
    slot: string,
    pattern: Element,
    items: Record<string, unknown>[],
  ): void {
    // The same list as last time is the same rows: a long one that does not
    // change -- a map's countries -- is not even looked through.
    if (this.#rowsShown.get(slot) === items) return
    this.#rowsShown.set(slot, items)
    for (const holder of Array.from(
      this.#root!.querySelectorAll('[data-slot]'),
    )) {
      if (
        holder.getAttribute('data-slot') !== slot ||
        holder.closest('[data-pat]')
      )
        continue
      const before = this.#rows.get(holder)
      const after: Rows = new Map()
      const fill: [Element, Record<string, unknown>][] = []
      const made: Element[] = []
      const wanted = items.map((item, i) => {
        let key: unknown = 'key' in item ? item.key : i
        // Two items with one key would be one row: the second gets its own.
        if (after.has(key)) key = Symbol('duplicate key')
        const kept = before?.get(key)
        const row = kept?.row ?? (pattern.cloneNode(true) as Element)
        if (!kept) made.push(row)
        after.set(key, { row, item })
        if (!kept || !sameValues(kept.item, item)) fill.push([row, item])
        return row
      })
      this.#rows.set(holder, after)
      if (!before) {
        // The first time, the slot holds the template's own row: replaced.
        holder.replaceChildren(...wanted)
      } else {
        // What has gone, first, so that what stays is moved only if it has
        // to be: a row moved is taken out of the page and put back.
        for (const [key, { row }] of before) {
          if (after.get(key)?.row !== row) row.remove()
        }
        wanted.forEach((row, i) => {
          const here = holder.children[i]
          if (here !== row) moveRow(holder, row, here ?? null)
        })
      }
      for (const [row, item] of fill) {
        fillInOrder(row, item as Record<string, Pattern>)
        for (const el of [
          row,
          ...Array.from(row.querySelectorAll('[data-prop]')),
        ]) {
          for (const [name, from] of pairs(el, 'data-prop')) {
            ;(el as unknown as Record<string, unknown>)[name] = item[from]
          }
        }
        for (const el of within(row, BOUND_SELECTOR)) {
          if (isControl(el)) show(el, getIn(item, boundPath(el)!))
        }
      }
      // A dialog that is a row -- one of none or one, there while the state
      // says so -- opens as it appears.
      for (const row of made) {
        if (row instanceof HTMLDialogElement && row.isConnected && !row.open) {
          row.showModal()
        }
      }
    }
  }

  /** Add or remove every attribute a `data-attr` fills from this slot. */
  #toggle(slot: string, on: boolean): void {
    for (const el of Array.from(this.#root!.querySelectorAll('[data-attr]'))) {
      for (const [name, from] of pairs(el, 'data-attr')) {
        if (from === slot) el.toggleAttribute(name, on)
      }
    }
  }
}

/** A delegate, and the link between it and what draws it. */
function delegateFor(
  shape: Shape,
  component: Delegate,
  emitFrom: () => EventTarget,
  label: () => string,
): { delegate: Mumu<object, object>; link: Link } {
  const delegate = new component()
  const link: Link = {
    state: Object.freeze({ ...shape.defaults }),
    refs: {},
    emit: (event, detail) => {
      perf()?.step(`emit ${event} from ${label()}`)
      // composed: out of every shadow root it is inside, so what a component
      // nested in another asks for reaches the state's owner.
      emitFrom().dispatchEvent(
        new CustomEvent(event, { bubbles: true, composed: true, detail }),
      )
      perf()?.handled(event)
    },
  }
  links.set(delegate, link)
  return { delegate, link }
}

/**
 * The element class for a component, to define. Anything that is not a Mumu
 * subclass -- an element class already -- comes back as it is.
 */
export function mumuElement(
  cls: Delegate | CustomElementConstructor,
): CustomElementConstructor {
  if (!(cls.prototype instanceof Mumu)) return cls as CustomElementConstructor
  const component = cls as Delegate
  const shape = shapeOf(component, component.template.content)
  const { name, keys } = shape
  for (const key of keys) {
    // The state is the element's interface, so its names must be free on an
    // element: `title` or `role` would hide the element's own.
    if (key in HTMLElement.prototype || key === 'delegate') {
      throw new Error(
        `${name}'s state property ${key} is already a property of every element`,
      )
    }
  }

  class MumuHost extends HTMLElement {
    readonly delegate: Mumu<object, object>
    #view: View

    constructor() {
      super()
      for (const key of keys) {
        // Set before the element was defined -- by markup parsed ahead of
        // customElements.define, say -- a value is an own property of the
        // element, which hides the state property. Define elements first.
        if (Object.prototype.hasOwnProperty.call(this, key)) {
          throw new Error(
            `<${this.localName}>.${key} was set before the element was defined; ` +
              'define custom elements before anything creates them',
          )
        }
      }
      const { delegate, link } = delegateFor(
        shape,
        component,
        () => this,
        () => `<${this.localName}>`,
      )
      this.delegate = delegate
      this.#view = new View(shape, delegate, link)
    }

    /** Called by each state property's setter. */
    [UPDATE](key: string, value: unknown): void {
      this.#view.set({ [key]: value })
    }

    connectedCallback(): void {
      // Once only: an element moved in the DOM is connected again, and a
      // shadow root cannot be attached twice.
      if (this.#view.attached) {
        this.#view.render()
        return
      }
      // delegatesFocus: focusing the element focuses the first thing in it
      // that takes focus, so an owner can focus a component's input.
      const root = this.attachShadow({ mode: 'open', delegatesFocus: true })
      root.appendChild(component.template.content.cloneNode(true))
      this.#view.attach(root)
    }
  }

  // The state properties, on the element's prototype, so `key in el` finds
  // them, as they would a built-in element's.
  for (const key of keys) {
    Object.defineProperty(MumuHost.prototype, key, {
      get(this: MumuHost) {
        return (links.get(this.delegate)!.state as Record<string, unknown>)[key]
      },
      set(this: MumuHost, value: unknown) {
        this[UPDATE](key, value)
      },
      enumerable: true,
      configurable: true,
    })
  }
  return MumuHost
}

/**
 * A component drawn into markup already in the page, rather than into an
 * element's shadow root: root's contents are its template, and it renders
 * there. What it emits is dispatched from root. `set` changes its state, all
 * of a change at once, rendering once.
 *
 * For an app, whose markup is the page itself. A component that goes in a
 * page is an element, and mumuElement makes it.
 */
export function mumuView<S extends object>(
  cls: Delegate,
  root: Element,
  commit?: (change: Partial<S>) => void,
): { delegate: Mumu<S, object>; set(change: Partial<S>): void } {
  const shape = shapeOf(cls, root)
  const { delegate, link } = delegateFor(
    shape,
    cls,
    () => root,
    () => shape.name,
  )
  link.commit = commit as Link['commit']
  const view = new View(shape, delegate, link)
  view.attach(root)
  return {
    delegate: delegate as Mumu<S, object>,
    set: (change) => view.set(change as Record<string, unknown>),
  }
}
