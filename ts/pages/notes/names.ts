// A player's name, in the order heraldry describes a coat of arms -- the
// beast first, then what it is doing, then its colour, as in "a lion
// rampant gules" -- in today's words: "Otter Swimming Teal". The colour in
// the name is the colour the player is shown in, on the row it is at and in
// the key, so the name says which outline is whose.

// prettier-ignore
const BEASTS = [
  'Otter', 'Heron', 'Fox', 'Hare', 'Owl', 'Stag', 'Boar', 'Wren', 'Salmon',
  'Bear', 'Moth', 'Newt', 'Badger', 'Crane', 'Raven', 'Lynx', 'Wolf', 'Swan',
  'Toad', 'Eel', 'Falcon', 'Marten', 'Beaver', 'Mole', 'Lark', 'Goose',
  'Pike', 'Stoat', 'Weasel', 'Ox', 'Ram', 'Goat', 'Hound', 'Cat', 'Dove',
  'Kite', 'Curlew', 'Plover', 'Trout', 'Seal',
]

// prettier-ignore
const DOINGS = [
  'Rearing', 'Walking', 'Sitting', 'Resting', 'Standing', 'Leaping',
  'Sleeping', 'Flying', 'Swimming', 'Watching', 'Turning', 'Running',
  'Prowling', 'Dancing', 'Climbing', 'Diving', 'Wading', 'Hiding', 'Singing',
  'Gliding', 'Grazing', 'Basking', 'Burrowing', 'Drifting', 'Hunting',
  'Nesting', 'Pouncing', 'Stretching', 'Wandering', 'Yawning',
]

// Each a colour an outline can be told apart by on white: named as it looks
export const COLORS: Record<string, string> = {
  Red: '#d32f2f',
  Vermilion: '#e8501c',
  Orange: '#f57c00',
  Amber: '#e0a000',
  Olive: '#808000',
  Lime: '#7cb342',
  Green: '#2e7d32',
  Jade: '#00a86b',
  Teal: '#00897b',
  Cyan: '#00acc1',
  Azure: '#1e88e5',
  Cobalt: '#1d4ed8',
  Navy: '#1a237e',
  Indigo: '#4f46e5',
  Violet: '#7c3aed',
  Purple: '#8e24aa',
  Plum: '#7b2d5b',
  Magenta: '#d81b60',
  Rose: '#e11d74',
  Coral: '#f06650',
  Brown: '#795548',
  Rust: '#a0410d',
  Slate: '#546e7a',
  Charcoal: '#37474f',
}

function pick<T>(from: readonly T[]): T {
  const [n] = crypto.getRandomValues(new Uint32Array(1))
  return from[n! % from.length]!
}

/** A name, and the colour it ends with. */
export function heraldic(): { name: string; color: string } {
  const colour = pick(Object.keys(COLORS))
  return {
    name: `${pick(BEASTS)} ${pick(DOINGS)} ${colour}`,
    color: COLORS[colour]!,
  }
}

/** An id or a key: random, and as long as asked, in letters and digits. */
export function randomId(length = 10): string {
  const letters = '0123456789abcdefghijklmnopqrstuvwxyz'
  return Array.from(
    crypto.getRandomValues(new Uint8Array(length)),
    (n) => letters[n % letters.length]
  ).join('')
}
