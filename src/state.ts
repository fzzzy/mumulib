
import { set, get } from "object-path";

type State = { [key: string]: any };
type OnStateChange = (state: State) => void;

const initialValues = {};
const obs: OnStateChange[] = [];
let loaded = false;
let state: State = {};
let setting = 0;
let dirty = false;



function onstate(onstatechange: OnStateChange): void {
  if (loaded) {
    onstatechange(state);
  }
  obs.push(onstatechange);
}

function set_state(nstate: State): void {
  let changed = false;
  for (const [k, v] of Object.entries(nstate)) {
    if (state[k] !== v) {
      if (v === undefined) {
        delete state[k];
      } else {
        state[k] = v;
        changed = true;
      }
    }
  }
  if (!changed) {
    return;
  }
  setting++;
  if (setting == 1) {
    console.log("onstatechange");
    for (const onstatechange of obs) {
      onstatechange(state);
    }
  } else {
    dirty = true;
  }
  setting--;
  if (setting == 0 && dirty) {
    dirty = false;
    window.requestAnimationFrame(() => set_state(state));
  }
}


document.addEventListener('DOMContentLoaded', function () {
  loaded = true;
  set_state({ "loaded": true });
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
          //document.body.dataset.state = JSON.stringify(state);
          set_state(state);
      } else if (name.substring(0, 9) === 'selected.') {
          const selected = get(state, state['selected']);
          set(selected, name.substring(9), value);
          console.log(`${name} = ${JSON.stringify(value)}`);
          //document.body.dataset.state = JSON.stringify(state);
          set_state(state);
      }
  }
}, true);


export { onstate, set_state, state };


