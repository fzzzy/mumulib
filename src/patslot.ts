type State = { [key: string]: any };
type OnStateChange = (state: State) => void;

const obs: OnStateChange[] = [];
let loaded = false;
let state: State = {};
let setting = 0;
let dirty = false;

function fill_slot(
  node: ParentNode,
  slotname: string,
  pat: string | HTMLElement
): void {
  const slot = node.querySelector(`[data-slot=${slotname}]`);
  console.log(slot);
  if (slot) {
    if (pat instanceof HTMLElement) {
      if (slot instanceof HTMLElement) {
        slot.dataset.slot = slotname;
      }
      slot.replaceWith(pat);
    } else {
      slot.textContent = pat;
    }
  }
}

function clone_pat(
  node: ParentNode,
  patname: string,
  slots: { [key: string]: string | HTMLElement }
): Element {
  const pat = node.querySelector(`[data-pat=${patname}]`);
  console.log(pat);
  if (!pat) {
    throw new Error(`Pattern with data-pat=${patname} not found`);
  }
  const clone = pat.cloneNode(true) as Element;
  for (const [slotname, pat2] of Object.entries(slots)) {
    fill_slot(clone, slotname, pat2);
  }
  return clone;
}

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
       changed = true;
       state[k] = v;
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

export { clone_pat, fill_slot, onstate, set_state };
