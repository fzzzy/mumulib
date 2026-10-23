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

export { show, drafted }
export type { Control }
