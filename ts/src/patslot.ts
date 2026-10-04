/**
 * Patslot
 *
 * This module provides functions and types for working with HTML templates.
 *
 * Types:
 * - Pattern: A type representing a pattern that can be an HTMLElement, an array of patterns, a generator of patterns, a string, or a Promise for any of these.
 *
 * Functions:
 * - fill_body(slots: { [key: string]: Pattern }): void
 *   Fills the document body with the provided slots.
 *
 * - fill_slots(node: HTMLElement, slotname: string, pat: Pattern): void
 *   Fills the specified slots in the given node with the provided pattern.
 *
 * - append_to_slots(node: HTMLElement, slotname: string, pat: Pattern): void
 *   Appends the specified pattern to the given slots in the node.
 *
 * - clone_pat(patname: string, slots: { [key: string]: Pattern }): Promise<HTMLElement>
 *   Clones the specified pattern and fills its slots with the provided patterns, returning the cloned element.
 *
 * - template(url: string): Promise<Template>
 *   The template at url, another page whose patterns its clone_pat clones.
 */

import morphdom from 'morphdom'

const TEMPLATE = document.body.cloneNode(true) as HTMLElement

type SyncPattern =
  | HTMLElement
  // An array's elements may be promises too, as clone_pat's are: each is
  // awaited as the slot is filled
  | (
      | HTMLElement
      | Promise<HTMLElement | string>
      | Generator<Pattern>
      | AsyncGenerator<Pattern>
      | string
    )[]
  | Generator<Pattern>
  | AsyncGenerator<Pattern>
  | string
  | number

type Pattern = Promise<SyncPattern> | SyncPattern

function isAsyncIterable(value: unknown): value is AsyncIterable<Pattern> {
  return (
    typeof (value as { [Symbol.asyncIterator]?: unknown })?.[
      Symbol.asyncIterator
    ] === 'function'
  )
}

// The elements under node that have attribute as value, compared as text:
// no selector is built from a name, so any name is found as it is written
function having(node: Element, attribute: string, value: string): Element[] {
  return Array.from(node.querySelectorAll(`[${attribute}]`)).filter(
    (el) => el.getAttribute(attribute) === value
  )
}

// An element's attribute slots, from its data-attr: "id=row_id,title=hint" is
// [["id", "row_id"], ["title", "hint"]]. The one reading of data-attr, as
// tags.attr_slots is Python's: a pair without both a name and a slot is no
// slot, and only the first = divides one
function attr_slots(el: Element): [string, string][] {
  const slots: [string, string][] = []
  for (const pair of (el.getAttribute('data-attr') || '').split(',')) {
    const eq = pair.indexOf('=')
    const name = pair.slice(0, eq)
    const slot = pair.slice(eq + 1)
    if (eq !== -1 && name && slot) {
      slots.push([name, slot])
    }
  }
  return slots
}

// What a fill of node reaches, node first: the elements that match, but
// nothing inside a pattern -- its prototype in the page, or a clone of one
// already filled into a slot -- whose slots and attributes are its own; and,
// given stop, nothing inside a match, whose content is being replaced
function reach(
  node: Element,
  matches: (el: Element) => boolean,
  stop: boolean
): Element[] {
  const found: Element[] = []
  const visit = (el: Element) => {
    const matched = matches(el)
    if (matched) {
      found.push(el)
    }
    if (matched && stop) {
      return
    }
    if (el !== node && el.hasAttribute('data-pat')) {
      return
    }
    for (const child of Array.from(el.children)) {
      visit(child)
    }
  }
  visit(node)
  return found
}

class Template {
  url: string

  constructor(url: string) {
    this.url = url
  }

  async clone_pat(
    patname: string,
    slots: { [key: string]: Pattern }
  ): Promise<HTMLElement> {
    let template
    if (this.url === '') {
      template = TEMPLATE
    } else {
      const response = await fetch(this.url)
      const text = await response.text()
      const parser = new DOMParser()
      const doc = parser.parseFromString(text, 'text/html')
      template = doc.body
    }

    const [pat] = having(template, 'data-pat', patname)
    if (!pat) {
      throw new Error(`No pat named ${patname}`)
    }
    const clone = pat.cloneNode(true) as HTMLElement
    for (const [slotname, pat2] of Object.entries(slots)) {
      await fill_slots(clone, slotname, pat2)
    }
    return clone
  }
}

/**
 * The template at url, another page's patterns to clone: a promise, so that
 * how it is had can change -- fetched before it resolves, say -- without
 * changing a caller. For now it resolves at once, and each clone_pat fetches
 * the page.
 */
async function template(url: string): Promise<Template> {
  return new Template(url)
}

async function fill_body(slots: { [key: string]: Pattern }) {
  const clone = document.body.cloneNode(true) as HTMLElement
  for (const [slotname, pat2] of Object.entries(slots)) {
    await fill_slots(clone, slotname, pat2)
  }
  morphdom(document.body, clone)
}

async function fill(node: HTMLElement, slots: { [key: string]: Pattern }) {
  for (const [slotname, pat2] of Object.entries(slots)) {
    await fill_slots(node, slotname, pat2)
  }
}

async function fill_slots(node: HTMLElement, slotname: string, pat: Pattern) {
  await _fill_or_append_slots(node, slotname, pat, false)
}

async function append_to_slots(
  node: HTMLElement,
  slotname: string,
  pat: Pattern
) {
  await _fill_or_append_slots(node, slotname, pat, true)
}

async function _fill_or_append_slots(
  node: HTMLElement,
  slotname: string,
  pat: Pattern,
  append: boolean
) {
  // Attributes, not dataset, which domino -- the DOM in Node -- lacks. A
  // pattern's own data-slot is found, as a slot filled with an element takes
  // the slot's name, but nothing inside it is
  const slots = reach(
    node,
    (el) => el.getAttribute('data-slot') === slotname,
    true
  )
  const calculated_slot: (Element | string)[] = []
  if (pat instanceof Promise) {
    pat = await pat
  }
  for (const slot of slots) {
    // console.log("got a slots", slot, pat);
    if (pat instanceof Element) {
      if (append) {
        slot.appendChild(pat.cloneNode(true) as Element)
      } else {
        pat.setAttribute('data-slot', slotname)
        slot.replaceWith(pat.cloneNode(true) as Element)
      }
    } else if (
      pat instanceof Array ||
      (typeof pat === 'object' && 'next' in pat && 'throw' in pat)
    ) {
      if (!append) {
        while (slot.firstChild) {
          slot.removeChild(slot.firstChild)
        }
      }
      if (calculated_slot.length !== 0) {
        for (const p of calculated_slot) {
          if (p instanceof Element) {
            slot.appendChild(p.cloneNode(true) as Element)
          } else {
            slot.appendChild(document.createTextNode(p))
          }
        }
      } else {
        if (isAsyncIterable(pat)) {
          for await (const p of pat) {
            if (p instanceof Element) {
              calculated_slot.push(p)
              slot.appendChild(p.cloneNode(true) as Element)
            } else {
              calculated_slot.push(p.toString())
              slot.appendChild(document.createTextNode(p.toString()))
            }
          }
        } else {
          for (let p of pat as Generator<Pattern>) {
            if (p instanceof Promise) {
              p = await p
            }
            if (p instanceof Element) {
              calculated_slot.push(p)
              slot.appendChild(p.cloneNode(true) as Element)
            } else {
              calculated_slot.push(p.toString())
              slot.appendChild(document.createTextNode(p.toString()))
            }
          }
        }
      }
    } else {
      if (append) {
        slot.textContent += pat === undefined ? 'undefined' : pat.toString()
      } else {
        slot.textContent = pat === undefined ? 'undefined' : pat.toString()
      }
    }
  }
  // A pattern's data-attr is its own, filled as it is cloned, not by a fill
  // of what it was put in
  const attrslots = reach(
    node,
    (el) =>
      Boolean(el.getAttribute('data-attr')) &&
      (el === node || !el.hasAttribute('data-pat')),
    false
  )

  for (const attrslot of attrslots) {
    const mappings = attr_slots(attrslot)
    const results: Promise<void>[] = mappings.map(async (mapping) => {
      const [attribute_name, attribute_slot] = mapping
      if (attribute_slot !== slotname) {
        return
      }
      if (pat instanceof Element) {
        throw new Error("Can't set attr to Element")
      } else if (
        pat instanceof Array ||
        (typeof pat === 'object' && 'next' in pat && 'throw' in pat)
      ) {
        let patstr = ''
        if (isAsyncIterable(pat)) {
          for await (const p of pat) {
            if (p instanceof Element) {
              throw new Error("Can't set attr to Element")
            } else {
              patstr += p.toString()
            }
          }
        } else {
          for (const p of pat as Generator<Pattern>) {
            if (p instanceof Element) {
              throw new Error("Can't set attr to Element")
            } else {
              patstr += p.toString()
            }
          }
        }
        attrslot.setAttribute(attribute_name, patstr)
      } else {
        attrslot.setAttribute(attribute_name, pat.toString())
      }
    })
    await Promise.all(results)
  }
}

async function clone_pat(
  patname: string,
  slots: { [key: string]: Pattern }
): Promise<HTMLElement> {
  const template = new Template('')
  return await template.clone_pat(patname, slots)
}

export { clone_pat, fill, fill_slots, fill_body, append_to_slots, template }
// The class is not exported, only its type: a template is had from template()
export type { Pattern, Template }
