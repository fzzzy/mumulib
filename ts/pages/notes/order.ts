// Where a note is, as a string: the notes are shown sorted by it. There is
// always another between two -- between "a" and "b" is "aV", and between
// that and "aW", "aVV" -- so a note moved writes its own order alone, and no
// other note is ever renumbered. Squeezing into one gap again and again
// costs a character each time, not a collision, as numbers halving would.
//
// The digits are 0-9, A-Z, a-z, in the order a string comparison puts
// them, and no order ends in 0, the smallest: so there is always room
// before one, too.

const DIGITS = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

function digit(order: string, at: number): number {
  return at < order.length ? DIGITS.indexOf(order[at]!) : 0
}

/**
 * An order between before and after, either of which may be missing: the
 * start and the end. before must sort before after.
 */
export function between(before: string | null, after: string | null): string {
  const low = before ?? ''
  if (after !== null && !(low < after)) {
    throw new Error(
      `${JSON.stringify(low)} is not before ${JSON.stringify(after)}`
    )
  }
  let key = ''
  for (let at = 0; ; at++) {
    const lo = digit(low, at)
    // Past after's end, nothing is above: after never ends before it
    // differs from low, being after it
    const hi =
      after === null || at >= after.length ? DIGITS.length : digit(after, at)
    // The same digit in both: it is the key's, and the difference further on
    if (lo === hi) {
      key += DIGITS[lo]
      continue
    }
    if (hi - lo > 1) return key + DIGITS[Math.floor((lo + hi) / 2)]
    // Adjacent digits: low's, and anything after it above low's rest
    key += DIGITS[lo]
    return key + between(low.slice(at + 1) || null, null)
  }
}

/**
 * An order between before and after, as between gives, with two random
 * digits more: two pages putting a note in one gap at the same moment --
 * two people adding at once, after the same last note -- would otherwise
 * give both the same order, and nothing could go between them. Safe, as
 * what between gives is never the start of after: it is below after at
 * some digit, so anything after it is too.
 */
export function placed(before: string | null, after: string | null): string {
  const [a, b] = crypto.getRandomValues(new Uint8Array(2))
  // The last not 0, so that there is room before it
  return between(before, after) + DIGITS[a! % 62] + DIGITS[1 + (b! % 61)]
}

/** The notes' ids, sorted as they are shown: by order, then by id. */
export function sorted<T extends { order: string }>(
  notes: Record<string, T>
): string[] {
  return Object.keys(notes).sort((a, b) => {
    const x = notes[a]!.order
    const y = notes[b]!.order
    return x < y ? -1 : x > y ? 1 : a < b ? -1 : a > b ? 1 : 0
  })
}
