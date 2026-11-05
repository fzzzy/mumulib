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
 * row inside it, an element marked `data-pat="foreach"`, takes a list: each
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
function sameValues(
  a: Record<string, unknown>,
  b: Record<string, unknown>
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
  template: HTMLTemplateElement,
  name: string
): {
  slots: string[]
  rows: Map<string, Element>
  props: string[]
} {
  const names = new Set<string>()
  const props = new Set<string>()
  const rows = new Map<string, Element>()
  const own = (el: Element) => !el.closest('[data-pat]')
  for (const el of Array.from(
    template.content.querySelectorAll('[data-slot]')
  ).filter(own)) {
    const slot = el.getAttribute('data-slot')!
    names.add(slot)
    // The slot's own row: not one inside another pattern in it.
    const found = Array.from(
      el.querySelectorAll('[data-pat="foreach"]')
    ).filter((row) => !row.parentElement!.closest('[data-pat]'))
    if (found.length > 1) {
      throw new Error(
        `${name}'s slot ${slot} has ${found.length} data-pat="foreach" rows; a list has one`
      )
    }
    if (found.length) rows.set(slot, found[0])
  }
  for (const el of Array.from(
    template.content.querySelectorAll('[data-attr]')
  ).filter(own)) {
    for (const [, slot] of pairs(el, 'data-attr')) names.add(slot)
  }
  for (const el of Array.from(
    template.content.querySelectorAll('[data-prop]')
  ).filter(own)) {
    for (const [, slot] of pairs(el, 'data-prop')) props.add(slot)
  }
  return { slots: [...names], rows, props: [...props] }
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
      Object.getOwnPropertyDescriptors(proto)
    )) {
      if (key !== 'constructor' && !found.has(key)) found.set(key, d)
    }
    proto = Object.getPrototypeOf(proto) as object | null
  }
  return found
}

/**
 * The element class for a component, to define. Anything that is not a Mumu
 * subclass -- an element class already -- comes back as it is.
 */
export function mumuElement(
  cls: Delegate | CustomElementConstructor
): CustomElementConstructor {
  if (!(cls.prototype instanceof Mumu)) return cls as CustomElementConstructor
  const component = cls as Delegate
  const name = component.name
  const defaults = component.state
  const keys = Object.keys(defaults)
  const properties = propertiesOf(component)
  const { slots, rows, props } = slotsOf(component.template, name)

  for (const [key, d] of properties) {
    if (d.set) {
      throw new Error(
        `${name} defines a setter for ${key}: a component only reads its state, ` +
          'and asks for changes with emit()'
      )
    }
  }
  for (const key of keys) {
    if (properties.has(key))
      throw new Error(`${name} defines ${key}, which is a state property`)
    // The state is the element's interface, so its names must be free on an
    // element: `title` or `role` would hide the element's own.
    if (key in HTMLElement.prototype || key === 'delegate') {
      throw new Error(
        `${name}'s state property ${key} is already a property of every element`
      )
    }
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
        `${name}.${method} is named for no event: "${event}" is not one an element has`
      )
    }
    handlers.push([event, method])
  }
  const onMount = properties.get('onMount')?.value as (() => void) | undefined
  const onRender = properties.get('onRender')?.value as (() => void) | undefined

  class MumuHost extends HTMLElement {
    readonly delegate: Mumu<object, object>
    #link: Link
    #root: ShadowRoot | null = null
    // What each data-prop property was last set to, per element.
    #set = new WeakMap<Element, Map<string, unknown>>()
    // The value each slot was last filled with.
    #filled = new Map<string, unknown>()
    // The list each row slot was last filled from.
    #rowsShown = new Map<string, unknown>()
    // Each row holder's rows, by key, with the item each was filled from.
    #rows = new WeakMap<Element, Rows>()

    constructor() {
      super()
      for (const key of keys) {
        // Set before the element was defined -- by markup parsed ahead of
        // customElements.define, say -- a value is an own property of the
        // element, which hides the state property. Define elements first.
        if (Object.prototype.hasOwnProperty.call(this, key)) {
          throw new Error(
            `<${this.localName}>.${key} was set before the element was defined; ` +
              'define custom elements before anything creates them'
          )
        }
      }
      this.delegate = new component()
      this.#link = {
        state: Object.freeze({ ...defaults }),
        refs: {},
        emit: (event, detail) => {
          perf()?.step(`emit ${event} from <${this.localName}>`)
          // composed: out of every shadow root it is inside, so what a
          // component nested in another asks for reaches the state's owner.
          this.dispatchEvent(
            new CustomEvent(event, { bubbles: true, composed: true, detail })
          )
          perf()?.handled(event)
        },
      }
      links.set(this.delegate, this.#link)
    }

    /**
     * Called by each state property's setter. The very value it already has
     * changes nothing, and renders nothing: an owner may set its whole state
     * again without asking what changed.
     */
    [UPDATE](key: string, value: unknown): void {
      if ((this.#link.state as Record<string, unknown>)[key] === value) return
      this.#link.state = Object.freeze({ ...this.#link.state, [key]: value })
      this.#render()
    }

    connectedCallback(): void {
      // Once only: an element moved in the DOM is connected again, and a
      // shadow root cannot be attached twice.
      if (!this.#root) {
        // delegatesFocus: focusing the element focuses the first thing in it
        // that takes focus, so an owner can focus a component's input.
        this.#root = this.attachShadow({ mode: 'open', delegatesFocus: true })
        this.#root.appendChild(component.template.content.cloneNode(true))
        for (const el of Array.from(
          this.#root.querySelectorAll('[data-ref]')
        )) {
          if (!el.closest('[data-pat]'))
            this.#link.refs[el.getAttribute('data-ref')!] = el
        }
        const delegate = this.delegate as unknown as Record<
          string,
          (event: Event) => void
        >
        // In the capture phase, so that events that do not bubble -- a
        // dialog's close, say -- are heard too.
        for (const [event, method] of handlers) {
          this.#root.addEventListener(
            event,
            (e) => {
              if (event === 'click') perf()?.step(`${name}.${method}`)
              delegate[method].call(delegate, e)
            },
            true
          )
        }
        this.#render()
        // What the component does with its own elements as it appears: opens
        // its dialog, say. Before autofocus, which cannot reach into a dialog
        // still closed.
        if (typeof onMount === 'function') onMount.call(this.delegate)
        // An element marked autofocus in the template takes the focus as the
        // component first appears -- through a child component, too, which
        // passes it on to its own.
        const autofocus = this.#root.querySelector('[autofocus]')
        if (autofocus instanceof HTMLElement) autofocus.focus()
        return
      }
      this.#render()
    }

    #render(): void {
      if (!this.#root) return
      const state = this.#link.state as Record<string, Pattern>
      const delegate = this.delegate as unknown as Record<string, Pattern>
      const values: Record<string, Pattern> = {}
      for (const slot of slots) {
        const value = slot in state ? state[slot] : delegate[slot]
        // A slot whose value is the very one it was last filled with is
        // already showing it: neither its text nor its attributes are written
        // again, so a render touches only what changed.
        if (this.#filled.has(slot) && this.#filled.get(slot) === value) continue
        this.#filled.set(slot, value)
        // A boolean fills an attribute by its presence -- `disabled`, say --
        // which patslot cannot do: it always writes a value, and any value
        // of a boolean attribute, "false" too, means true.
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
            `${name}'s ${slot} is a list of objects, but its slot has no data-pat="foreach" row`
          )
        }
        values[slot] = value
      }
      if (Object.keys(values).length) {
        for (const element of Array.from(this.#root.children)) {
          if (
            element instanceof HTMLElement &&
            !(element instanceof HTMLStyleElement)
          ) {
            fillInOrder(element, values)
          }
        }
      }
      if (props.length) this.#setProps()
      // What the component does with its own elements after each render:
      // redraw a canvas, say. Rows still being filled may not be in yet.
      if (typeof onRender === 'function') onRender.call(this.delegate)
    }

    /**
     * Set each data-prop property from its slot: an input's `value`, say, or
     * a child component's state. Only when the slot's value has changed since
     * it was last set here. A range input the user is dragging holds its own
     * value until its owner answers; setting the old one back on every render
     * in between would snap it back under the pointer.
     */
    #setProps(): void {
      const state = this.#link.state as Record<string, unknown>
      const delegate = this.delegate as unknown as Record<string, unknown>
      for (const el of Array.from(
        this.#root!.querySelectorAll('[data-prop]')
      )) {
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
     * Put one copy of the row in the slot for each item, and fill it from the
     * item: its slots and attributes by patslot, its data-prop properties
     * here. The copies go in as they are, not cloned again as patslot would,
     * so the properties stay -- and they are set once the copies are in the
     * page, where a component in a row has become itself.
     *
     * A row is kept from one list to the next. Each is matched to an item by
     * the item's `key`, if it has one, or else by its place in the list: so a
     * line added to the end of a list adds a row and touches none of the
     * others, and a list whose items come and go from anywhere -- the chat
     * floating over the town, its oldest message leaving -- gives each item
     * a key. A kept row is filled again only if its item's values are not the
     * same ones, compared one by one, as the row was last filled from.
     */
    #fillRows(
      slot: string,
      pattern: Element,
      items: Record<string, unknown>[]
    ): void {
      // The same list as last time is the same rows: a long one that does not
      // change -- a map's countries -- is not even looked through.
      if (this.#rowsShown.get(slot) === items) return
      this.#rowsShown.set(slot, items)
      for (const holder of Array.from(
        this.#root!.querySelectorAll('[data-slot]')
      )) {
        if (
          holder.getAttribute('data-slot') !== slot ||
          holder.closest('[data-pat]')
        )
          continue
        const before = this.#rows.get(holder)
        const after: Rows = new Map()
        const fill: [Element, Record<string, unknown>][] = []
        const wanted = items.map((item, i) => {
          let key: unknown = 'key' in item ? item.key : i
          // Two items with one key would be one row: the second gets its own.
          if (after.has(key)) key = Symbol('duplicate key')
          const kept = before?.get(key)
          const row = kept?.row ?? (pattern.cloneNode(true) as Element)
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
            if (here !== row) holder.insertBefore(row, here ?? null)
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
        }
      }
    }

    /** Add or remove every attribute a `data-attr` fills from this slot. */
    #toggle(slot: string, on: boolean): void {
      for (const el of Array.from(
        this.#root!.querySelectorAll('[data-attr]')
      )) {
        for (const [name, from] of pairs(el, 'data-attr')) {
          if (from === slot) el.toggleAttribute(name, on)
        }
      }
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
