/**
 * Patslot Module API Documentation
 *
 * This module provides functions and types for working with HTML templates and slots.
 *
 * Constants:
 * - TEMPLATE: A constant representing the initial cloned state of the document body.
 *
 * Types:
 * - Pattern: A type representing a pattern that can be an HTMLElement, an array of patterns, a generator of patterns, or a string.
 *
 * Functions:
 * - fill_body(slots: { [key: string]: Pattern }): void
 *   Fills the document body with the provided slots and updates the DOM.
 *
 * - fill_slots(node: HTMLElement, slotname: string, pat: Pattern): void
 *   Fills the specified slots in the given node with the provided pattern.
 *
 * - append_to_slots(node: HTMLElement, slotname: string, pat: Pattern): void
 *   Appends the specified pattern to the given slots in the node.
 *
 * - clone_pat(patname: string, slots: { [key: string]: Pattern }): HTMLElement
 *   Clones the specified pattern and fills its slots with the provided patterns.
 */

import morphdom from "morphdom";

const TEMPLATE = document.body.cloneNode(true) as HTMLElement;

type Pattern = HTMLElement |
    (HTMLElement | Generator<Pattern> | string)[] |
    Generator<Pattern> |
    string;

function fill_body(slots: { [key: string]: Pattern }) {
    const clone = document.body.cloneNode(true) as HTMLElement;
    for (const [slotname, pat2] of Object.entries(slots)) {
        fill_slots(clone, slotname, pat2);
    }
    morphdom(document.body, clone);
}

function fill_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern
) {
    _fill_or_append_slots(node, slotname, pat, false);
}


function append_to_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern
) {
    _fill_or_append_slots(node, slotname, pat, true);
}


function _fill_or_append_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern,
    append: boolean
) {
    let slots: HTMLElement[] | Element[] | NodeListOf<Element> = [];
    if (node.dataset.slot == slotname) {
        slots = [node];
    } else {
        slots = node.querySelectorAll(`[data-slot=${slotname}]`);
    }
    let calculated_slot: (Element | string)[] = [];
    for (const slot of slots) {
        // console.log("got a slots", slot, pat);
        if (pat instanceof Element) {
            if (append) {
                slot.appendChild(pat.cloneNode(true) as Element);
            } else {
                pat.dataset.slot = slotname;
                slot.replaceWith(pat.cloneNode(true) as Element);                
            }
        } else if (
            pat instanceof Array ||
            (typeof pat === 'object' &&
                'next' in pat &&
                'throw' in pat)) {
            if (!append) {
                while (slot.firstChild) {
                    slot.removeChild(slot.firstChild);
                }    
            }
            if (calculated_slot.length !== 0) {
                for (const p of calculated_slot) {
                    if (p instanceof Element) {
                        slot.appendChild(p.cloneNode(true) as Element);
                    } else {
                        slot.appendChild(document.createTextNode(p));
                    }
                }
            } else {
                for (const p of pat) {
                    if (p instanceof Element) {
                        calculated_slot.push(p);
                        slot.appendChild(p.cloneNode(true) as Element);
                    } else {
                        calculated_slot.push(p.toString());
                        slot.appendChild(document.createTextNode(p.toString()));
                    }
                }
            }
        } else {
            if (append) {
                slot.textContent += (pat === undefined) ? "undefined" : pat.toString();
            } else {
                slot.textContent = (pat === undefined) ? "undefined" : pat.toString();
            }
        }
    }
    let attrslots: HTMLElement[] | Element[] | NodeListOf<Element> = [];
    if (node.dataset.attr) {
        attrslots = [node];
    }
    attrslots = [...attrslots, ...node.querySelectorAll(`[data-attr]`)];

    for (const attrslot of attrslots) {
        const attrs = (attrslot as HTMLElement).dataset.attr || '';
        //console.log("attrs", attrs);
        const mappings = attrs.split(',');
        mappings.forEach(mapping => {
            const [attribute_name, attribute_slot] = mapping.split('=');
            //console.log("attribute_slot", attribute_slot, slotname);
            if (attribute_slot != slotname) {
                return;
            }
            if (pat instanceof Element) {
                throw new Error("Can't set attr to Element");
            } else if (
                pat instanceof Array ||
                (typeof pat === 'object' &&
                    'next' in pat &&
                    'throw' in pat)) {
                let patstr = "";
                for (const p of pat) {
                    if (p instanceof Element) {
                        throw new Error("Can't set attr to Element");
                    } else {
                        patstr += p.toString();
                    }
                }
                attrslot.setAttribute(attribute_name, patstr);
            } else {
                attrslot.setAttribute(attribute_name, pat);
            }
        });
    }
}

function clone_pat(
    patname: string,
    slots: { [key: string]: Pattern }
): HTMLElement {
    //console.log(TEMPLATE);
    const pat = TEMPLATE.querySelector(`[data-pat=${patname}]`);
    if (!pat) {
        throw new Error(`No pat named ${patname}`);
    }
    //console.log(pat);
    const clone = pat.cloneNode(true) as HTMLElement;
    for (const [slotname, pat2] of Object.entries(slots)) {
        fill_slots(clone, slotname, pat2);
    }
    return clone;
}



export { clone_pat, fill_slots, fill_body, append_to_slots, Pattern, TEMPLATE };

