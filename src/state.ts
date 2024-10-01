
type State = { [key: string]: any };
type OnStateChange = (state: State) => void;

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



export { onstate, set_state };


