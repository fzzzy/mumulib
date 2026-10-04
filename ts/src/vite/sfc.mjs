/**
 * Single-file components as HTML: a `.sfc.html` holds a `<template>` and a
 * `<script>`, and importing it gives the custom element class its script
 * exports -- or, with no script, one that renders the template into its
 * shadow root. The script is TypeScript, and sees `template` (the parsed
 * `<template>`) and `defineComponent(template)`.
 *
 *     // vite.config.ts
 *     import { sfcPlugin } from 'mumulib/vite-plugin-sfc'
 *     export default defineConfig({ plugins: [sfcPlugin()] })
 *
 *     // anywhere
 *     import Counter from './counter.sfc.html'
 *     customElements.define('my-counter', Counter)
 *
 * Each component is a module named `<path>.sfc.html?sfc&lang.ts`, as Vue names
 * a `<script lang="ts">`: Vite's own TypeScript transform compiles it, and
 * coverage tools instrument it. A `\0`-prefixed virtual module, which this
 * used to be, is skipped by istanbul on principle, so no component's script
 * was ever counted. The module is the script as it is in the file, with the
 * template code put in front, and its source map puts every token of the
 * script back where it is in the `.sfc.html`.
 *
 * Plain JavaScript, typed with JSDoc, so that it ships as it is: tsc checks it
 * and writes its declarations, and nothing has to build it.
 */
import fs from 'node:fs'

const SUFFIX = '.sfc.html'
const QUERY = '?sfc&lang.ts'

/** @param {string} template */
function templateCode(template) {
  return `const template = document.createElement('template');
template.innerHTML = ${JSON.stringify(template)};

function defineComponent(template: HTMLTemplateElement): CustomElementConstructor {
  return class extends HTMLElement {
    connectedCallback() {
      this.attachShadow({ mode: 'open' });
      this.shadowRoot!.appendChild(template.content.cloneNode(true));
    }
  };
}
`
}

const BASE64 =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'

/** One number as a source map's base64 VLQ. @param {number} n */
function vlq(n) {
  let rest = n < 0 ? (-n << 1) | 1 : n << 1
  let out = ''
  do {
    let digit = rest & 31
    rest >>>= 5
    if (rest) digit |= 32
    out += BASE64[digit]
  } while (rest)
  return out
}

/**
 * The mappings for text copied verbatim from `source` at `start`, after
 * `before` generated lines: a point at each word and punctuation mark, so a
 * position anywhere in the script maps back to its own line and column.
 *
 * @param {string} source
 * @param {number} start
 * @param {number} length
 * @param {number} before
 */
function mappings(source, start, length, before) {
  let line = source.slice(0, start).split('\n').length - 1
  let column = start - (source.lastIndexOf('\n', start - 1) + 1)
  // Each field is relative to the one before it: the generated column within
  // its line, the original line and column across the whole map
  let lastLine = 0
  let lastColumn = 0
  const lines = source.slice(start, start + length).split('\n')
  const out = lines.map((text) => {
    const segments = []
    let lastGenerated = 0
    for (const match of text.matchAll(/[\w$]+|[^\s\w$]/g)) {
      const generated = match.index
      const original = column + generated
      segments.push(
        vlq(generated - lastGenerated) +
          vlq(0) +
          vlq(line - lastLine) +
          vlq(original - lastColumn)
      )
      lastGenerated = generated
      lastLine = line
      lastColumn = original
    }
    line += 1
    column = 0
    return segments.join(',')
  })
  return ';'.repeat(before) + out.join(';')
}

// Elements whose content is text to their own end tag, however much it looks
// like markup: inside a template, a `</template>` in one does not end it
const RAW = new Set(['script', 'style', 'textarea', 'title'])

// A tag's name where one starts at `<`, and whether it is an end tag
const TAG = /<(\/?)([a-zA-Z][^\s/>]*)/y

/** Line and column, from 1, of an index. @param {string} source @param {number} at */
function where(source, at) {
  const before = source.slice(0, at).split('\n')
  return `${before.length}:${before[before.length - 1].length + 1}`
}

/** @param {string} source @param {number} at */
function tagAt(source, at) {
  TAG.lastIndex = at
  const match = TAG.exec(source)
  return match && { closing: match[1] === '/', name: match[2].toLowerCase() }
}

/**
 * The index after the `>` that ends the tag at `at`: a quoted attribute value
 * is read whole, so `title="a>b"` does not end it.
 *
 * @param {string} source
 * @param {number} at
 * @param {string} filename
 */
function tagEnd(source, at, filename) {
  let quote = ''
  for (let i = at + 1; i < source.length; i++) {
    const c = source[i]
    if (quote) {
      if (c === quote) quote = ''
    } else if (c === '"' || c === "'") {
      quote = c
    } else if (c === '>') {
      return i + 1
    }
  }
  throw new Error(`${filename}:${where(source, at)}: a tag is not closed`)
}

/** The index after the comment at `at`. @param {string} source @param {number} at @param {string} filename */
function commentEnd(source, at, filename) {
  const end = source.indexOf('-->', at + 4)
  if (end < 0) {
    throw new Error(`${filename}:${where(source, at)}: a comment is not closed`)
  }
  return end + 3
}

/**
 * Where the end tag of a raw text element starts, from `from`: its first
 * `</name`, as HTML has it, whatever comes between.
 *
 * @param {string} source
 * @param {number} from
 * @param {string} name
 * @param {string} filename
 */
function rawClose(source, from, name, filename) {
  const close = new RegExp(`</${name}[\\s/>]`, 'ig')
  close.lastIndex = from
  const match = close.exec(source)
  if (!match) {
    throw new Error(
      `${filename}:${where(source, from)}: <${name}> is not closed`
    )
  }
  return match.index
}

/**
 * Where the `</template>` that closes a template starts, from its content's
 * start: one inside it opens another that must close first, and a comment, or
 * a raw text element's content, is passed over whole, whatever it mentions.
 *
 * @param {string} source
 * @param {number} from
 * @param {string} filename
 */
function templateClose(source, from, filename) {
  let depth = 1
  let i = from
  for (;;) {
    const lt = source.indexOf('<', i)
    if (lt < 0) {
      throw new Error(
        `${filename}:${where(source, from)}: <template> is not closed`
      )
    }
    if (source.startsWith('<!--', lt)) {
      i = commentEnd(source, lt, filename)
      continue
    }
    const tag = tagAt(source, lt)
    if (!tag) {
      i = lt + 1
      continue
    }
    if (tag.name === 'template') {
      depth += tag.closing ? -1 : 1
      if (depth === 0) return lt
    }
    i = tagEnd(source, lt, filename)
    if (!tag.closing && RAW.has(tag.name)) {
      i = rawClose(source, i, tag.name, filename)
    }
  }
}

/**
 * A `.sfc.html`'s two parts, as HTML reads them: at the top level, a
 * `<template>` and a `<script>`, each at most once, and comments; anything
 * else there is an error, rather than passed over. Each part is where its
 * content starts and ends.
 *
 * @param {string} source
 * @param {string} filename
 */
function parts(source, filename) {
  /** @type {Record<string, { start: number, end: number }>} */
  const found = {}
  let i = 0
  for (;;) {
    const lt = source.indexOf('<', i)
    const text = source.slice(i, lt < 0 ? source.length : lt)
    if (text.trim()) {
      const at = i + text.search(/\S/)
      throw new Error(
        `${filename}:${where(source, at)}: text outside <template> and <script>`
      )
    }
    if (lt < 0) return found
    if (source.startsWith('<!--', lt)) {
      i = commentEnd(source, lt, filename)
      continue
    }
    const tag = tagAt(source, lt)
    const name = tag && !tag.closing ? tag.name : ''
    if (name !== 'template' && name !== 'script') {
      throw new Error(
        `${filename}:${where(source, lt)}: only a <template> and a <script> may be at the top level`
      )
    }
    if (found[name]) {
      throw new Error(`${filename}:${where(source, lt)}: a second <${name}>`)
    }
    const start = tagEnd(source, lt, filename)
    const end =
      name === 'template'
        ? templateClose(source, start, filename)
        : rawClose(source, start, name, filename)
    found[name] = { start, end }
    i = tagEnd(source, end, filename)
  }
}

/**
 * A `.sfc.html` as the TypeScript module it stands for, and where its script
 * came from: `start` and `length` in the source, and the `lines` of generated
 * header before it. The plugin makes its source map from these, and the type
 * checker puts errors back in place with them.
 *
 * @param {string} source
 * @param {string} filename
 * @returns {{ code: string, script: { start: number, length: number, lines: number } | null }}
 */
export function parseSfc(source, filename) {
  const { template, script } = parts(source, filename)
  if (!template && !script) {
    throw new Error(`${filename}: a .sfc.html needs a <template> or a <script>`)
  }
  const header = template
    ? templateCode(source.slice(template.start, template.end).trim())
    : ''
  if (!script) {
    return {
      code: `${header}\nexport default defineComponent(template);\n`,
      script: null,
    }
  }
  return {
    code: header + source.slice(script.start, script.end),
    script: {
      start: script.start,
      length: script.end - script.start,
      lines: header.split('\n').length - 1,
    },
  }
}

/**
 * A `.sfc.html` as the TypeScript module it stands for, with its source map.
 *
 * @param {string} source
 * @param {string} filename
 * @returns {{ code: string, map: import('vite').Rollup.SourceMapInput }}
 */
export function compileSfc(source, filename) {
  const { code, script } = parseSfc(source, filename)
  return {
    code,
    // With no script, nothing maps; the map still says whose module it is
    map: {
      version: 3,
      sources: [filename],
      sourcesContent: [source],
      names: [],
      mappings: script
        ? mappings(source, script.start, script.length, script.lines)
        : '',
    },
  }
}

/** @returns {import('vite').Plugin} */
export function sfcPlugin() {
  return {
    name: 'mumulib:sfc',
    enforce: 'pre',

    handleHotUpdate({ file, server }) {
      if (file.endsWith(SUFFIX)) {
        server.ws.send({ type: 'full-reload' })
        return []
      }
    },

    async resolveId(source, importer, options) {
      if (!source.endsWith(SUFFIX)) return null
      // Vite's dependency scan reads what it resolves from disk itself,
      // plugins' load aside, so it is left the file as it is on disk
      if (/** @type {{ scan?: boolean }} */ (options).scan) return null
      const resolved = await this.resolve(source, importer, { skipSelf: true })
      return resolved ? resolved.id + QUERY : null
    },

    load(id) {
      if (!id.endsWith(SUFFIX + QUERY)) return null
      const filename = id.slice(0, -QUERY.length)
      this.addWatchFile(filename)
      return compileSfc(fs.readFileSync(filename, 'utf-8'), filename)
    },
  }
}
