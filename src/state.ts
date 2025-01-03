/**
 * State Module API Documentation
 *
 * This module provides functions and types for managing application state.
 *
 * Types:
 * - State: A type representing the application state as an object with string keys and any values.
 * - OnStateChange: A type representing a callback function that is called when the state changes. The callback takes the new state.
 *
 * Functions:
 * - onstate(onstatechange: OnStateChange)
 *   Registers a callback function to be called when the state changes.
 *
 * - set_state(nstate: State)
 *   Updates the application state with the provided new state and notifies registered callbacks. The new top level keys are merged with the old top level keys.
 *
 * - state: State
 *   The current application state.
 * 
 * - debug(mode: boolean)
 *   Whether or not to log the current application state on changes.
 * 
 */

import { set, get } from "object-path";

type State = { [key: string]: any } | any;
type OnStateChange = (state: State) => Promise<void>;

const initialValues: { [key: string]: string } = {};
const obs: OnStateChange[] = [];
let loaded = false;
let state: State = {};
let setting = 0;
let dirty = false;
let debug_mode: boolean = false;


function debug(mode: boolean) {
  debug_mode = mode;
}


async function onstate(onstatechange: OnStateChange) {
  if (loaded) {
    await onstatechange(state);
  }
  obs.push(onstatechange);
}


async function _set_state(root: any, path: string, nstate: State): Promise<void> {
  let changed = false;
  if (nstate === null) {
    changed = true;
  } else {
    if (!path) {
      for (const [k, v] of Object.entries(nstate)) {
        if (root[k] !== v) {
          if (v === undefined) {
            delete root[k];
          } else {
            root[k] = v;
            changed = true;
          }
        }
      }
    } else {
      const old = get(root, path);
      if (old !== nstate) {
        set(root, path, nstate);
        changed = true;
      }
    }  
  }
  if (!changed) {
    return;
  }
  setting++;
  if (setting === 1) {
    update_dom_state(state);
    if (debug_mode) {
      document.body.dataset.state = JSON.stringify(state);
      console.log("onstatechange", state);
    }
    for (const onstatechange of obs) {
      await onstatechange(state);
    }
  } else {
    dirty = true;
  }
  setting--;
  if (setting === 0 && dirty) {
    dirty = false;
    window.requestAnimationFrame(() => set_state(null));
  }
}


async function set_state(nstate: State): Promise<void> {
  await _set_state(state, "", nstate);
}


async function _set_path(root: any, path: string, nstate: State): Promise<void> {
  await _set_state(root, path, nstate);
}


async function set_path(path: string, nstate: State): Promise<void> {
  await _set_path(state, path, nstate);
}


document.addEventListener('DOMContentLoaded', async function () {
  loaded = true;
  await set_state(null);
});


document.addEventListener('focus', function (e) {
  if (
    e.target &&
    e.target instanceof HTMLInputElement
  ) {
    initialValues[e.target.name] = e.target.value;
  }
}, true);


function possibly_changed(e: Event) {
  let target;
  if (e.target) {
    if (e.target instanceof HTMLInputElement) {
      target = e.target as HTMLInputElement;  
    } else if (e.target instanceof HTMLSelectElement) {
      target = e.target as HTMLSelectElement;
    } else if (e.target instanceof HTMLTextAreaElement) {
      target = e.target as HTMLTextAreaElement;
    }
    if (target && (!target.name || !target.value)) {
      return;
    }
  }
  if (!target) {
    return;
  }
  let name = target.name;
  let value = target.value;
  if (initialValues[name] === value) {
    return;
  }
  //console.log('Input event fired:', e.target.name, e.target.value);
  if (name.substring(0, 5) === 'this.') {
    set(state, name.substring(5), value);
    console.log(`${name} = ${JSON.stringify(value)}`);
    set_state(null);
  } else if (name.substring(0, 9) === 'selected.') {
    // should state['selected'] be prefixed with "this." for consistency
    const selected = get(state, state['selected']);
    console.log("selected", selected);
    set(selected, name.substring(9), value);
    if (debug_mode) {
      console.log(`${name} = ${JSON.stringify(value)}`);
    }
    set_state(null);
  } else if (name === "selected") {
    set(state, "selected", value);
    set_state(null);
  }
}


document.addEventListener('focusout', function (e: Event) {
  //console.log('blur event fired:', e);
  if (
    e.target &&
    (e.target instanceof HTMLInputElement ||
      e.target instanceof HTMLTextAreaElement)
  ) {
    possibly_changed(e);
  }
}, true);


document.addEventListener('change', function (e: Event) {
  //console.log('blur event fired:', e);
  if (
    e.target &&
    ((e.target instanceof HTMLInputElement &&
    e.target.type === "radio") ||
    e.target instanceof HTMLSelectElement)
  ) {
    possibly_changed(e);
  }
}, true);


async function update_dom_state(state: State) {
  const elements = document.querySelectorAll('input, select, textarea');
  elements.forEach((element) => {
    let el;
    if (element instanceof HTMLInputElement) {
      el = element as HTMLInputElement;
    } else if (element instanceof HTMLSelectElement) {
      el = element as HTMLSelectElement;
    } else if (element instanceof HTMLTextAreaElement) {
      el = element as HTMLTextAreaElement;
    }
    if (!el) {
      return;
    }
    const name = el.name;
    if (name.startsWith('this.')) {
      const value = get(state, name.slice(5));
      if (el.value !== value) {
        el.value = value;
      }
    } else if (name.startsWith('selected.')) {
      const selectedState = get(state, state["selected"]);
      const value = get(selectedState, name.slice(9));
      if (el.value !== value) {
        el.value = value;
      }
    } else if (name === "selected") {
      const sel = state["selected"];
      if (el instanceof HTMLInputElement && el.type === "radio") {
        if (el.value === sel) {
          el.checked = true;
        } else {
          el.checked = false
        }  
      } else {
        el.value = sel;
      }
    }
  });
}


export { onstate, set_state, set_path, state, debug };
