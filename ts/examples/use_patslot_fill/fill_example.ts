import { patslot } from 'mumulib'

window.onload = async () => {
  await patslot.fill_body({
    name: 'Jane Smith',
    age: 12,
    color: 'color: blue',
  })
  await patslot.fill(document.getElementById('fill-many') as HTMLElement, {
    first: 'one',
    second: 'two',
  })
  setTimeout(() => {
    patslot.fill_slots(
      document.getElementById('fill-element') as HTMLElement,
      'fill_me',
      'now been filled.'
    )
  }, 500)
}
