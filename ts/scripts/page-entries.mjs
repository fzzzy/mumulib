// The entries of the pages Python serves: every index.html under root, at
// any depth -- an entry is always a directory's index, its slash. Each is
// named by its directory, as rolldown names its chunks: notes, and
// notes/settings for notes/settings/index.html, and index for pages' own.
import * as fs from 'node:fs'
import * as path from 'node:path'

/**
 * @param {string} root
 * @returns {Record<string, string>}
 */
export function pageEntries(root) {
  return Object.fromEntries(
    fs
      .readdirSync(root, { recursive: true, encoding: 'utf8' })
      .filter((file) => path.basename(file) === 'index.html')
      .map((file) => [
        // The directory's own index, pages/index.html, is named index
        path.dirname(file) === '.'
          ? 'index'
          : path.dirname(file).split(path.sep).join('/'),
        path.join(root, file),
      ])
      .sort(([a], [b]) => (a < b ? -1 : 1))
  )
}
