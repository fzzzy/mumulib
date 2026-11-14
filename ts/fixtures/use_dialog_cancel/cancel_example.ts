import { state, dialog } from 'mumulib'
import type { FormArgs } from 'mumulib'

class MyObject {
  my_method(args: FormArgs) {
    const node = document.createElement('div')
    node.className = 'output'
    node.textContent = 'saved ' + args.name
    document.body.appendChild(node)
  }
}

// Each state, for the test to see selected set and cleared
state.onstate(async (new_state) => {
  document.body.dataset.selected = new_state.selected ?? ''
})

state.set_state({ my_object: new MyObject() })

// Opened by hand, not on every change of state, so a cancel stays cancelled
document.getElementById('open')?.addEventListener('click', () => {
  dialog.do_dialog('my_dialog', 'this.my_object', (el) => el)
})
