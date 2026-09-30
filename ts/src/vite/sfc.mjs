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
  const template = /<template>([\s\S]*?)<\/template>/.exec(source)
  const script = /<script[^>]*>([\s\S]*?)<\/script>/.exec(source)
  if (!template && !script) {
    throw new Error(`${filename}: a .sfc.html needs a <template> or a <script>`)
  }
  const header = template ? templateCode(template[1].trim()) : ''
  if (!script) {
    return {
      code: `${header}\nexport default defineComponent(template);\n`,
      script: null,
    }
  }
  return {
    code: header + script[1],
    script: {
      start: script.index + script[0].indexOf('>') + 1,
      length: script[1].length,
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
