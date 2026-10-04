/**
 * State
 *
 * This module provides functions and types for managing application state.
 *
 * Types:
 * - State: The application state as an object with string keys and any values.
 * - OnStateChange: A callback function that is called when the state changes. The callback takes the new state.
 *
 * Functions:
 * - onstate(onstatechange: OnStateChange)
 *   Registers a callback function to be called when the state changes.
 *
 * - set_state(newstate: State)
 *   Updates the application state with the provided new state and notifies registered callbacks. The new top level keys are merged with the old top level keys.
 *
 * The state itself is not exported: it is read as onstate gives it.
 *
 * - debug(mode: boolean)
 *   Whether or not to log the current application state on changes.
 *
 */

import { set, get } from 'object-path'
import { tree as state } from './tree.js'

// The caller's own data, whatever its shape: the published type says so, and
// narrowing it here would break code that reads its state as it likes.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type State = { [key: string]: any } | any
type OnStateChange = (state: State) => Promise<void>

const initialValues: { [key: string]: string } = {}
const obs: OnStateChange[] = []
let loaded = false
let setting = 0
let dirty = false
let debug_mode: boolean = false

function debug(mode: boolean) {
  debug_mode = mode
}

async function onstate(onstatechange: OnStateChange) {
  if (loaded) {
    await onstatechange(state)
  }
  obs.push(onstatechange)
}

async function _set_state(
  root: State,
  path: string,
  nstate: State
): Promise<void> {
  let changed = false
  if (nstate === null) {
    changed = true
  } else {
    if (!path) {
      for (const [k, v] of Object.entries(nstate)) {
        if (root[k] !== v) {
          if (v === undefined) {
            delete root[k]
          } else {
            root[k] = v
          }
          changed = true
        }
      }
    } else {
      const old = get(root, path)
      if (old !== nstate) {
        set(root, path, nstate)
        changed = true
      }
    }
  }
  if (!changed) {
    return
  }
  setting++
  try {
    if (setting === 1) {
      update_dom_state(state)
      if (debug_mode) {
        document.body.setAttribute('data-state', JSON.stringify(state))
        console.log('onstatechange', state)
      }
      for (const onstatechange of obs) {
        await onstatechange(state)
      }
    } else {
      dirty = true
    }
  } finally {
    // Even when a callback throws: else every later change would count as
    // nested in this one, and nothing would be rendered again
    setting--
    if (setting === 0 && dirty) {
      dirty = false
      // The next frame in a browser; in Node, which has none, the next turn
      const later =
        globalThis.requestAnimationFrame ??
        ((then: () => void) => setTimeout(then, 0))
      later(() => set_state(null))
    }
  }
}

async function set_state(nstate: State): Promise<void> {
  await _set_state(state, '', nstate)
}

async function _set_path(
  root: State,
  path: string,
  nstate: State
): Promise<void> {
  await _set_state(root, path, nstate)
}

async function set_path(path: string, nstate: State): Promise<void> {
  await _set_path(state, path, nstate)
}

document.addEventListener('DOMContentLoaded', async function () {
  loaded = true
  await set_state(null)
})

// A checkbox or a radio button: what it says is whether it is checked, not
// its value, and it says so by a change event, which only a change fires
function checkable(el: Element): el is HTMLInputElement {
  return (
    el instanceof HTMLInputElement &&
    (el.type === 'checkbox' || el.type === 'radio')
  )
}

// What a control says, as the state holds it: a checkbox whether it is
// checked; a radio button, which only says so as it is checked, its value
function read(
  el: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement
): string | boolean {
  if (el instanceof HTMLInputElement && el.type === 'checkbox') {
    return el.checked
  }
  return el.value
}

// The state, shown by a control: a checkbox checked if it is truthy, a radio
// button checked if its own value is the state's -- its value left as it is,
// as it is what the button stands for -- and anything else given the value
function show(
  el: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement,
  value: unknown
) {
  if (el instanceof HTMLInputElement && el.type === 'checkbox') {
    el.checked = Boolean(value)
  } else if (el instanceof HTMLInputElement && el.type === 'radio') {
    el.checked = el.value === value
  } else if (el.value !== value) {
    el.value = value as string
  }
}

document.addEventListener(
  'focus',
  function (e) {
    if (
      (e.target instanceof HTMLInputElement && !checkable(e.target)) ||
      e.target instanceof HTMLTextAreaElement
    ) {
      initialValues[e.target.name] = e.target.value
    }
  },
  true
)

function possibly_changed(e: Event) {
  let target
  if (e.target) {
    if (e.target instanceof HTMLInputElement) {
      target = e.target as HTMLInputElement
    } else if (e.target instanceof HTMLSelectElement) {
      target = e.target as HTMLSelectElement
    } else if (e.target instanceof HTMLTextAreaElement) {
      target = e.target as HTMLTextAreaElement
    }
    // An empty value is a field cleared, and goes through like any other
    if (target && !target.name) {
      return
    }
  }
  if (!target) {
    return
  }
  const name = target.name
  const value = read(target)
  // A text field is compared with what it held when focused; a change event,
  // a checkable's or a select's, is only fired by a change
  if (
    name !== 'selected' &&
    !checkable(target) &&
    initialValues[name] === value
  ) {
    return
  }
  //console.log('Input event fired:', e.target.name, e.target.value);
  if (name.substring(0, 5) === 'this.') {
    set(state, name.substring(5), value)
    console.log(`${name} = ${JSON.stringify(value)}`)
    set_state(null)
  } else if (name.substring(0, 9) === 'selected.') {
    // should state['selected'] be prefixed with "this." for consistency
    const selected = get(state, state['selected'])
    console.log('selected', selected)
    set(selected, name.substring(9), value)
    if (debug_mode) {
      console.log(`${name} = ${JSON.stringify(value)}`)
    }
    set_state(null)
  } else if (name === 'selected') {
    set(state, 'selected', value)
    set_state(null)
  }
}

document.addEventListener(
  'focusout',
  function (e: Event) {
    //console.log('blur event fired:', e);
    if (
      e.target &&
      ((e.target instanceof HTMLInputElement && !checkable(e.target)) ||
        e.target instanceof HTMLTextAreaElement)
    ) {
      possibly_changed(e)
    }
  },
  true
)

document.addEventListener(
  'change',
  function (e: Event) {
    //console.log('blur event fired:', e);
    if (
      e.target &&
      ((e.target instanceof Element && checkable(e.target)) ||
        e.target instanceof HTMLSelectElement)
    ) {
      possibly_changed(e)
    }
  },
  true
)

async function update_dom_state(state: State) {
  const elements = document.querySelectorAll('input, select, textarea')
  elements.forEach((element) => {
    let el
    if (element instanceof HTMLInputElement) {
      el = element as HTMLInputElement
    } else if (element instanceof HTMLSelectElement) {
      el = element as HTMLSelectElement
    } else if (element instanceof HTMLTextAreaElement) {
      el = element as HTMLTextAreaElement
    }
    if (!el) {
      return
    }
    const name = el.name
    if (name.startsWith('this.')) {
      show(el, get(state, name.slice(5)))
    } else if (name.startsWith('selected.')) {
      const selectedState = get(state, state['selected'])
      show(el, get(selectedState, name.slice(9)))
    } else if (name === 'selected') {
      show(el, state['selected'])
    }
  })
}

export { onstate, set_state, set_path, debug }
export type { State, OnStateChange }
