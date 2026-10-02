import { state } from 'mumulib'
import type { State } from 'mumulib'

// The state as onstate last gave it: read from there, as it changes, never
// by reaching into the state module
let seen: State = {}

// Each second, the selected person's number, one more than it was seen
function update() {
  const selected = seen['selected']
  state.set_path(`${selected}.number`, seen[selected].number + 1)
  setTimeout(update, 1000)
}

state.onstate(async (new_state) => {
  seen = new_state
  if (Object.keys(new_state).length === 0) {
    await state.set_state({
      selected: 'person1',
      person1: { number: 0 },
      person2: { number: 0 },
    })
    setTimeout(update, 1000)
  }
  const node = document.createElement('div')
  node.className = 'output'
  node.textContent = 'Got state ' + JSON.stringify(new_state)
  document.body.appendChild(node)
})
