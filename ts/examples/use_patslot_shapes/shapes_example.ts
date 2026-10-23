import { patslot } from 'mumulib'
import type { Pattern } from 'mumulib'

const byId = (id: string) => document.getElementById(id) as HTMLElement

// How many times each generator has been run through: a generator filled
// into two slots of one name runs once, the second slot taking what the
// first was given
const generated = { sync: 0, async: 0 }

function* rows(): Generator<Pattern> {
  generated.sync++
  yield patslot.clone_pat('row', { label: 'one' })
  yield 'two'
}

async function* streamed_rows(): AsyncGenerator<Pattern> {
  generated.async++
  yield await patslot.clone_pat('row', { label: 'three' })
  yield 'four'
}

// What each fill that is refused says, in order
async function refused(fill: () => Promise<void>) {
  try {
    await fill()
  } catch (error) {
    const item = document.createElement('li')
    item.textContent = (error as Error).message
    byId('errors').appendChild(item)
  }
}

window.onload = async () => {
  // One element: each slot of the name takes a clone of it, named as the slot
  const badge = document.createElement('span')
  badge.textContent = 'new'
  await patslot.fill_slots(byId('element'), 'badge', badge)

  await patslot.fill_slots(byId('promised'), 'later', Promise.resolve('kept'))

  await patslot.fill_slots(byId('sync'), 'rows', rows())
  await patslot.fill_slots(byId('async'), 'rows', streamed_rows())

  // Appended after what is there, rather than in its place
  const second = document.createElement('li')
  second.textContent = 'second'
  await patslot.append_to_slots(byId('appended'), 'items', second)
  await patslot.append_to_slots(byId('appended'), 'note', ', world')
  await patslot.append_to_slots(byId('appended'), 'more', ['second', 'third'])

  // An attribute takes an iterable's parts as one string, however deep
  await patslot.fill(byId('attrs'), {
    words: ['a', 'b', 'c'],
    generated: (function* () {
      yield 'x'
      yield 'y'
    })(),
    streamed: (async function* () {
      yield 'p'
      yield 'q'
    })(),
    nested: [
      'x',
      Promise.resolve('y'),
      (function* (): Generator<Pattern> {
        yield ['z', '1']
      })(),
    ],
  })

  // Patterns inside patterns, however deep, each part in its place
  await patslot.fill_slots(byId('nested'), 'mixed', [
    'a',
    (function* (): Generator<Pattern> {
      yield 'b'
      yield ['c', Promise.resolve('d')]
    })(),
    (async function* (): AsyncGenerator<Pattern> {
      yield patslot.clone_pat('row', { label: 'e' })
      yield 5
    })(),
  ])

  // A generator into a slot and attributes of its name, and into attributes
  // alone: each takes all it gives
  const tags = function* () {
    yield 'red'
    yield 'green'
  }
  await patslot.fill_slots(byId('shared'), 'tags', tags())
  await patslot.fill_slots(byId('attributes'), 'tags', tags())

  // An element is no attribute's value, however it comes
  const element = () => document.createElement('i')
  await refused(() => patslot.clone_pat('nowhere', {}).then(() => {}))
  await refused(() => patslot.fill_slots(byId('attrs'), 'words', element()))
  await refused(() =>
    patslot.fill_slots(
      byId('attrs'),
      'generated',
      (function* () {
        yield element()
      })()
    )
  )
  await refused(() =>
    patslot.fill_slots(
      byId('attrs'),
      'streamed',
      (async function* () {
        yield element()
      })()
    )
  )

  document.body.dataset.generated = `${generated.sync} ${generated.async}`
  document.body.dataset.filled = 'yes'
}
