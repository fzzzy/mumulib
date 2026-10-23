import { state, dialog } from 'mumulib'
import type { FormArgs } from 'mumulib'

// Each call of a method, its arguments as JSON, for the test to read
function output(text: string) {
  const node = document.createElement('div')
  node.className = 'output'
  node.textContent = text
  document.body.appendChild(node)
}

class Recorder {
  record(args: FormArgs) {
    output(`record ${JSON.stringify(args)}`)
  }

  // A method may be async: the dialog waits for it before it clears selected
  async record_later(args: FormArgs) {
    await new Promise((resolve) => setTimeout(resolve, 10))
    output(`record_later ${JSON.stringify(args)} while ${selected} is selected`)
  }
}

class Person {
  name = 'Ada'
  age = '36'
  size = 'small'
  agreed = true
  bio = ''
  city = 'Paris'
  tags = ['red']
}

let selected = ''

// What a dialog without a method wrote into the state, and what is selected
state.onstate(async (new_state) => {
  selected = new_state.selected ?? ''
  const person = new_state.person as Person | undefined
  document.body.dataset.person = JSON.stringify(person)
  document.body.dataset.selected = selected
})

state.set_state({ recorder: new Recorder(), person: new Person() })

const open = (button: string, dialog_name: string, path: string) =>
  document.getElementById(button)?.addEventListener('click', () => {
    dialog.do_dialog(dialog_name, path, (el) => el)
  })

open('open-lists', 'lists', 'this.recorder')
open('open-named', 'named', 'this.recorder')
open('open-implicit', 'implicit', 'this.recorder')
open('open-selected', 'selected', 'this.person')
// No dialog of the name, and an element of the name that is no dialog
open('open-missing', 'missing', 'this.recorder')
open('open-missing', 'not_a_dialog', 'this.recorder')
