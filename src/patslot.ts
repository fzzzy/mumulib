/**
 * Patslot Module API Documentation
 *
 * This module provides functions and types for working with HTML templates and slots.
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
 *
 * Classes:
 * - Template: A class that takes a URL parameter and provides a clone_pat method.
 */

import morphdom from "morphdom";

const TEMPLATE = document.body.cloneNode(true) as HTMLElement;

type SyncPattern = HTMLElement |
    (HTMLElement | Generator<Pattern> | AsyncGenerator<Pattern> | string)[] |
    Generator<Pattern> | AsyncGenerator<Pattern> |
    string |
    number;

type Pattern = Promise<SyncPattern> | SyncPattern;

class Template {
    url: string;

    constructor(url: string) {
        this.url = url;
    }

    async clone_pat(patname: string, slots: { [key: string]: Pattern }): Promise<HTMLElement> {
        let template;
        if (this.url === "") {
            template = TEMPLATE;
        } else {
            const response = await fetch(this.url);
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, "text/html");
            template = doc.body;
        }

        const pat = template.querySelector(`[data-pat=${patname}]`);
        if (!pat) {
            throw new Error(`No pat named ${patname}`);
        }
        const clone = pat.cloneNode(true) as HTMLElement;
        for (const [slotname, pat2] of Object.entries(slots)) {
            await fill_slots(clone, slotname, pat2);
        }
        return clone;
    }
}

async function fill_body(slots: { [key: string]: Pattern }) {
    const clone = document.body.cloneNode(true) as HTMLElement;
    for (const [slotname, pat2] of Object.entries(slots)) {
        await fill_slots(clone, slotname, pat2);
    }
    morphdom(document.body, clone);
}

async function fill(
    node: HTMLElement,
    slots: { [key: string]: Pattern }
) {
    for (const [slotname, pat2] of Object.entries(slots)) {
        await fill_slots(node, slotname, pat2);
    }
}


async function fill_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern
) {
    await _fill_or_append_slots(node, slotname, pat, false);
}


async function append_to_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern
) {
    await _fill_or_append_slots(node, slotname, pat, true);
}


async function _fill_or_append_slots(
    node: HTMLElement,
    slotname: string,
    pat: Pattern,
    append: boolean
) {
    let slots: HTMLElement[] | Element[] | NodeListOf<Element> = [];
    if (node.dataset.slot == slotname) {
        slots = [node];
    } else {
        slots = Array.from(node.querySelectorAll(`[data-slot=${slotname}]`));
    }
    let calculated_slot: (Element | string)[] = [];
    if (pat instanceof Promise) {
        pat = await pat;
    }
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
                    0
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
                if (typeof (pat as any)[Symbol.asyncIterator] === 'function') {
                    for await (const p of pat) {
                        if (p instanceof Element) {
                            calculated_slot.push(p);
                            slot.appendChild(p.cloneNode(true) as Element);
                        } else {
                            calculated_slot.push(p.toString());
                            slot.appendChild(document.createTextNode(p.toString()));
                        }
                    }
                } else {
                    for (let p of pat as Generator<Pattern>) {
                        if (p instanceof Promise) {
                            p = await p;
                        }
                        if (p instanceof Element) {
                            calculated_slot.push(p);
                            slot.appendChild(p.cloneNode(true) as Element);
                        } else {
                            calculated_slot.push(p.toString());
                            slot.appendChild(document.createTextNode(p.toString()));
                        }
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
    attrslots = [
        ...attrslots,
        ...Array.from(node.querySelectorAll(`[data-attr]`))
    ];

    for (const attrslot of attrslots) {
        const attrs = (attrslot as HTMLElement).dataset.attr || '';
        //console.log("attrs", attrs);
        const mappings = attrs.split(',');
        const results: Promise<void>[] = mappings.map(async (mapping) => {
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
                if (typeof (pat as any)[Symbol.asyncIterator] === 'function') {
                for await (const p of pat) {
                    if (p instanceof Element) {
                        throw new Error("Can't set attr to Element");
                    } else {
                        patstr += p.toString();
                    }
                }
            } else {
                for (const p of pat as Generator<Pattern>) {
                    if (p instanceof Element) {
                        throw new Error("Can't set attr to Element");
                    } else {
                        patstr += p.toString();
                    }
                }

            }
                attrslot.setAttribute(attribute_name, patstr);
            } else {
                attrslot.setAttribute(attribute_name, pat.toString());
            }
        });
        await Promise.all(results);
    }
}

async function clone_pat(
    patname: string,
    slots: { [key: string]: Pattern }
): Promise<HTMLElement> {
    const template = new Template("");
    return await template.clone_pat(patname, slots);
}

export { clone_pat, fill_slots, fill_body, append_to_slots, Template };
export type { Pattern };
