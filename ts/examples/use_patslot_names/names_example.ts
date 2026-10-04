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
    // Only the first = divides a pair: this slot is a=b
    'a=b': 'divided once',
    plain: 'plain',
  })
  document.body.dataset.filled = 'yes'
}
