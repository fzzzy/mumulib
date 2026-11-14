import { state } from 'mumulib'

state.onstate(async (new_state) => {
  const node = document.createElement('div')
  node.className = 'output'
  node.textContent = 'Got state ' + JSON.stringify(new_state)
  document.body.appendChild(node)
})

// A change of state from elsewhere -- as sync makes one when the server
// announces it -- which a test sends without moving the focus
window.addEventListener('remote', (event) => {
  state.set_state((event as CustomEvent).detail)
})
