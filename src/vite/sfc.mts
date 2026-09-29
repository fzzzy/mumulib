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
 * was ever counted. And the module is the file with everything but the script
 * cut away, the template code put in front, so its source map puts every line
 * of the script back where it is in the `.sfc.html`.
 */
import fs from 'node:fs'
import MagicString, { type SourceMap } from 'magic-string'
import type { Plugin } from 'vite'

const SUFFIX = '.sfc.html'
const QUERY = '?sfc&lang.ts'

function templateCode(template: string): string {
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

/** A `.sfc.html` as the TypeScript module it stands for, with its source map. */
export function compileSfc(
  source: string,
  filename: string
): { code: string; map: SourceMap } {
  const template = /<template>([\s\S]*?)<\/template>/.exec(source)
  const script = /<script[^>]*>([\s\S]*?)<\/script>/.exec(source)
  if (!template && !script) {
    throw new Error(`${filename}: a .sfc.html needs a <template> or a <script>`)
  }

  const code = new MagicString(source)
  const header = template ? templateCode(template[1].trim()) : ''
  if (script) {
    const start = script.index + script[0].indexOf('>') + 1
    const end = start + script[1].length
    code.remove(0, start)
    code.remove(end, source.length)
    code.prepend(header)
  } else {
    code.remove(0, source.length)
    code.prepend(`${header}\nexport default defineComponent(template);\n`)
  }
  return {
    code: code.toString(),
    map: code.generateMap({
      source: filename,
      includeContent: true,
      hires: true,
    }),
  }
}

export function sfcPlugin(): Plugin {
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
      if ((options as { scan?: boolean }).scan) return null
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
