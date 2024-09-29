
function fill_slot(node, slotname, pat) {
    const slot = node.querySelector(`[data-slot=${slotname}]`);
    console.log(slot);
    if (slot) {
        if (pat instanceof HTMLElement) {
            slot.dataset.slot = slotname;
            slot.replaceWith(pat);
        } else {

            slot.textContent = pat;
        }
    }
}

function clone_pat(node, patname, slots) {
    const pat = node.querySelector(`[data-pat=${patname}]`);
    console.log(pat);
    const clone = pat.cloneNode(true);
    for (const [slotname, pat2] of Object.entries(slots)) {
        fill_slot(clone, slotname, pat2);
    }
    return clone;
}

const obs = [];
let loaded = false;
let state = {};
let setting = 0;
let dirty = false;

function onstate(onstatechange) {
    if (loaded) {
        onstatechange(state);
    }
    obs.push(onstatechange);
}

function set_state(nstate) {
    for (const [k, v] of Object.entries(nstate)) {
        state[k] = v;
    }
    setting++;
    console.log("setting", setting);
    if (setting == 1) {
        for (const onstatechange of obs) {
            onstatechange(state);
        }
    } else {
        dirty = true;
        console.log("setting");
    }
    setting--;
    if (setting == 0 && dirty) {
        dirty = false;
        window.requestAnimationFrame(() =>
            set_state(state));
    }
}

document.addEventListener('DOMContentLoaded', function () {
    loaded = true;
    set_state(state);
});

export { clone_pat, fill_slot, onstate, set_state };
