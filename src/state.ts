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

type State = { [key: string]: any };
type OnStateChange = (state: State) => Promise<void>;

const initialValues = {};
const obs: OnStateChange[] = [];
let loaded = false;
let state: State = {};
let setting = 0;
let dirty = false;
let debug_mode = false;

function debug(mode) {
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
  await set_state({});
});

document.addEventListener('focus', function (e) {
  if (
    e.target &&
    e.target instanceof HTMLInputElement
  ) {
    initialValues[e.target.name] = e.target.value;
  }
}, true);

document.addEventListener('focusout', function (e: Event) {
  //console.log('blur event fired:', e);
  if (
    e.target &&
    e.target instanceof HTMLInputElement
  ) {
    let name = e.target.name;
    let value = e.target.value;
    if (initialValues[e.target.name] === value) {
      return;
    }
    //console.log('Input event fired:', e.target.name, e.target.value);
    if (name.substring(0, 5) === 'this.') {
      set(state, name.substring(5), value);
      console.log(`${name} = ${JSON.stringify(value)}`);
      set_state(state);
    } else if (name.substring(0, 9) === 'selected.') {
      // should state['selected'] be prefixed with "this." for consistency
      const selected = get(state, state['selected']);
      set(selected, name.substring(9), value);
      console.log(`${name} = ${JSON.stringify(value)}`);
      set_state(state);
    }
  }
}, true);

export { onstate, set_state, set_path, state, debug };

