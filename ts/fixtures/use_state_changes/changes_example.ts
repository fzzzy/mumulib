import { state } from 'mumulib'

function log(text: string) {
  const node = document.createElement('div')
  node.className = 'output'
  node.textContent = text
  document.body.appendChild(node)
}

// Each state as it is rendered; one with boom in it makes the callback throw
state.onstate(async (new_state) => {
  if (new_state.boom) {
    throw new Error('boom')
  }
  log('Got state ' + JSON.stringify(new_state))
})

// A deletion is a change, and a callback that throws does not stop the next
document.getElementById('run')?.addEventListener('click', async () => {
  await state.set_state({ a: 1 })
  await state.set_state({ a: undefined })
  try {
    await state.set_state({ boom: true })
  } catch (error) {
    log('threw ' + (error as Error).message)
  }
  await state.set_state({ boom: undefined, b: 2 })
})
