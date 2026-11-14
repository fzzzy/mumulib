// What the state and dialog modules both do to a form's controls. Neither
// index.ts nor anything else exports it.

type Control = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement

// A value, shown by a control: a checkbox checked if it is truthy, or, given
// a list, if its own value is in it; a radio button checked if its own value
// is the one given -- its value left as it is, as it is what the button
// stands for; a multiple select's options chosen if theirs are in the list;
// and anything else given its text
function show(el: Control, value: unknown) {
  if (el instanceof HTMLInputElement && el.type === 'checkbox') {
    el.checked = Array.isArray(value)
      ? value.includes(el.value)
      : Boolean(value)
  } else if (el instanceof HTMLInputElement && el.type === 'radio') {
    el.checked = el.value === value
  } else if (el instanceof HTMLSelectElement && el.multiple) {
    for (const option of Array.from(el.options)) {
      option.selected = Array.isArray(value) && value.includes(option.value)
    }
  } else {
    // Nothing there is an empty field, not the text "undefined"
    const text = value === undefined || value === null ? '' : String(value)
    if (el.value !== text) {
      el.value = text
    }
  }
}

// A dialog's draft: a selected.* control in a <dialog>, which the dialog
// fills as it opens and saves as it is submitted, and the state neither
// shows nor writes to while it is open
function drafted(el: Control): boolean {
  return el.name.startsWith('selected.') && el.closest('dialog') !== null
}

// A checkbox or a radio button: what it says is whether it is checked
function checkable(el: Element): el is HTMLInputElement {
  return (
    el instanceof HTMLInputElement &&
    (el.type === 'checkbox' || el.type === 'radio')
  )
}

// What a control says, as the state holds it: a checkbox whether it is
// checked; a radio button, which only says so as it is checked, its value;
// a multiple select the values of its chosen options
function read(el: Control): string | boolean | string[] {
  if (el instanceof HTMLInputElement && el.type === 'checkbox') {
    return el.checked
  }
  if (el instanceof HTMLSelectElement && el.multiple) {
    return Array.from(el.selectedOptions, (option) => option.value)
  }
  return el.value
}

function isControl(el: unknown): el is Control {
  return (
    el instanceof HTMLInputElement ||
    el instanceof HTMLSelectElement ||
    el instanceof HTMLTextAreaElement
  )
}

// What a form's method is called with: each control's value by its name. A
// name ending in [] is always a list, without the brackets -- a multiple
// select with one choice is still a list, and one with none an empty list --
// and a name given twice is a list too.
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
  // A list nothing was sent for -- no box checked, no option chosen -- is
  // empty, as the server's form.texts has it; but not one whose controls are
  // all disabled, which the form does not send at all
  for (const control of Array.from(form.elements)) {
    const key = control.getAttribute('name')
    if (key?.endsWith('[]') && !control.matches(':disabled')) {
      args[key.slice(0, -2)] ??= []
    }
  }
  return args
}

// The page's markup an app draws: its this.* controls are the app's,
// bound by Mumu, and the state module's own this.* binding leaves them be
const claimed = new WeakSet<Node>()

function inClaimed(el: Node): boolean {
  for (let node: Node | null = el; node; node = node.parentNode) {
    if (claimed.has(node)) return true
  }
  return false
}

export {
  show,
  drafted,
  checkable,
  read,
  isControl,
  form_args,
  claimed,
  inClaimed,
}
export type { Control, FormArgs }
