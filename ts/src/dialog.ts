/**
 * Dialog
 *
 * This module provides functions for handling dialog interactions.
 *
 * Functions:
 * - do_dialog(dialog_name: string, path: string, render: (el: HTMLElement, state: object) => HTMLElement): void
 *   Opens a dialog, renders its content, and handles form submissions.
 *   Submitting a form saves it: the form the dialog's returnValue names, or
 *   else the one submitted. Closing it any other way -- Escape, or a submit
 *   button whose value is "cancel" -- saves nothing.
 *
 *   Parameters:
 *   - dialog_name: The ID of the dialog element to be opened.
 *   - path: The path to the state object to be used for rendering the dialog.
 *   - render: A function that takes an HTMLElement and a state object, and returns an HTMLElement representing the rendered dialog content.
 *
 *   Return value:
 *   - void
 */

import { set, get } from 'object-path'
import morphdom from 'morphdom'
import { set_state } from './state.js'
import { tree as state } from './tree.js'

// May fill the dialog in place and return it, and may be async: it is awaited
type RenderFunc = (
  el: HTMLElement,
  state: object
) => HTMLElement | Promise<HTMLElement>

// What a form's method is called with: each control's value by its name. A
// name ending in [] is always a list, without the brackets -- a multiple
// select with one choice is still a list -- and a name given twice is too.
type FormArgs = { [key: string]: string | string[] }

function form_args(form: HTMLFormElement): FormArgs {
  const args: FormArgs = {}
  // FormData, not the form's <input>s: a <textarea>, a <select> and a
  // form-associated custom element are values too
  for (const [key, value] of new FormData(form)) {
    if (typeof value !== 'string') {
      continue
    }
    const listed = key.endsWith('[]')
    const name = listed ? key.slice(0, -2) : key
    const before = args[name]
    if (Array.isArray(before)) {
      before.push(value)
    } else if (before !== undefined) {
      args[name] = [before, value]
    } else {
      args[name] = listed ? [value] : value
    }
  }
  return args
}

async function do_dialog(
  dialog_name: string,
  path: string,
  render: RenderFunc
) {
  set_state({ selected: path })
  const substate = get(state, path.substring(5))
  console.log('SUBSTATE', state, path, substate)

  const dialog = document.getElementById(dialog_name)
  if (dialog && dialog instanceof HTMLDialogElement) {
    const clone = await render(dialog, substate)
    console.log('cloned', dialog, clone)
    morphdom(dialog, clone)
    // The form submitted this showing; none, and the dialog was cancelled
    let submitted: HTMLFormElement | null = null
    for (const d of Array.from(dialog.querySelectorAll('form'))) {
      d.onsubmit = (event) => {
        event.preventDefault()
        if (event.target) {
          let target = event.target as HTMLElement
          while (!(target instanceof HTMLDialogElement)) {
            if (target.parentNode) {
              target = target.parentNode as HTMLElement
            } else {
              console.error('Dialog target not found')
              return
            }
          }
          submitted = d
          // What method="dialog" would have done: the button's value is the
          // dialog's returnValue, so a Cancel button cancels
          const button = event.submitter
          target.close(
            button instanceof HTMLButtonElement ||
              button instanceof HTMLInputElement
              ? button.value
              : ''
          )
        }
      }
    }
    // A dialog keeps its returnValue from one showing to the next: a Cancel
    // last time would make this one's Save a cancel too
    dialog.returnValue = ''
    dialog.showModal()
    dialog.onclose = async (ev) => {
      console.log('closing', ev.target)
      if (!ev.target) {
        return
      }
      const returnValue = (ev.target as HTMLDialogElement).returnValue
      // Escape closes the dialog without a submit, as does close() from code
      if (submitted === null || returnValue === 'cancel') {
        set_state({ selected: undefined })
        return
      }
      // The name compared as text, not built into a selector, so any
      // returnValue is a name; and the attribute, which a control named
      // "name" does not hide as it does form.name
      const named = Array.from(
        (ev.target as HTMLElement).querySelectorAll('form')
      ).find((f) => f.getAttribute('name') === returnValue)
      const form = (returnValue && named) || submitted
      const method = form.querySelector(
        'input[name="method"]'
      ) as HTMLInputElement
      if (method) {
        const args = form_args(form)
        console.log('calling method', method.value, args)
        const got = get(state, String(args['path']).substring(5))
        console.log('got', got)
        delete args['method']
        delete args['path']
        const result = got[method.value].call(got, args)
        if (result instanceof Promise) {
          await result
        }
      } else {
        for (const inp of Array.from(form.querySelectorAll('input'))) {
          if (inp.name.substring(0, 9) === 'selected.') {
            const fullname = `${state['selected']}.${inp.name.substring(9)}`
            console.log('setting', fullname, inp.value)
            set(state, fullname.substring(5), inp.value)
          }
        }
      }
      set_state({ selected: undefined })
    }
  } else {
    console.error(`Dialog ${dialog_name} not found.`)
  }
}

export { do_dialog }
export type { RenderFunc, FormArgs }
