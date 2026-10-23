import { state } from 'mumulib'

// In debug, each change of state is written on the body as data-state, and
// logged; Quiet stops it
state.debug(true)
state.set_state({ title: 'first', selected: 'person', person: { name: 'Ada' } })

document.getElementById('quiet')?.addEventListener('click', () => {
  state.debug(false)
})

// A callback given once the page has loaded is called at once, with the
// state as it is, and with each change after
document.getElementById('late')?.addEventListener('click', () => {
  state.onstate(async (new_state) => {
    const node = document.createElement('div')
    node.className = 'output'
    node.textContent = 'Late state ' + JSON.stringify(new_state)
    document.body.appendChild(node)
  })
})
