import { patslot } from 'mumulib'

window.onload = async () => {
  // Names no bare selector could hold, and an outer slot "name" filled after
  // people whose own "name" is already filled: theirs is left as it is
  await patslot.fill_body({
    people: [
      patslot.clone_pat('person.row', { name: 'Ada' }),
      patslot.clone_pat('person.row', { name: 'Grace' }),
    ],
    name: 'Town',
    'item.name': 'dotted',
    '2 col': 'spaced',
  })
  document.body.dataset.filled = 'yes'
}
