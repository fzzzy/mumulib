#!/usr/bin/env node
/**
 * Type checking for .sfc.html components, which tsc cannot see and Vite only
 * strips of their types. Each component becomes, in memory, the module the
 * plugin makes of it; TypeScript checks those with the project's tsconfig,
 * their imports resolving as usual from disk; and every error is put back at
 * its line and column in the .sfc.html, the script being copied verbatim.
 *
 *     mumulib-sfc-check [--project tsconfig.json] [dir or file ...]
 *
 * With no paths it checks every .sfc.html under the working directory. It
 * exits 1 if anything is wrong, printing errors as tsc does.
 *
 * Plain JavaScript, typed with JSDoc, so that it ships as it is.
 */
import fs from 'node:fs'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { parseSfc } from './sfc.mjs'

const SKIP = new Set(['node_modules', 'dist', 'coverage-frontend', 'var'])

/**
 * Every .sfc.html in or under `paths`, absolute.
 *
 * @param {string[]} paths
 * @returns {string[]}
 */
export function findSfcFiles(paths) {
  /** @type {string[]} */
  const found = []
  /** @param {string} at */
  const walk = (at) => {
    const stat = fs.statSync(at)
    if (stat.isFile()) {
      if (at.endsWith('.sfc.html')) found.push(path.resolve(at))
      return
    }
    for (const entry of fs.readdirSync(at, { withFileTypes: true })) {
      if (entry.name.startsWith('.') || SKIP.has(entry.name)) continue
      walk(path.join(at, entry.name))
    }
  }
  for (const at of paths) walk(at)
  return found.sort()
}

/**
 * @typedef {object} SfcError
 * @property {string} file the .sfc.html
 * @property {number} line 1-based
 * @property {number} column 1-based
 * @property {number} code the TS error number
 * @property {string} message
 */

/**
 * The type errors in `files`, placed in the .sfc.html they belong to.
 *
 * @param {string[]} files absolute paths of .sfc.html files
 * @param {{ project?: string }} [options] the tsconfig; found from the
 *   working directory if not given
 * @returns {Promise<SfcError[]>}
 */
export async function checkSfc(files, options = {}) {
  const ts = (await import('typescript')).default
  const configPath =
    options.project ?? ts.findConfigFile(process.cwd(), ts.sys.fileExists)

  /** @type {import('typescript').CompilerOptions} */
  let compilerOptions = {
    strict: true,
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.ESNext,
    moduleResolution: ts.ModuleResolutionKind.Bundler,
    skipLibCheck: true,
  }
  // The project's declarations come too -- its vite/client, its
  // sfc-client -- but only errors in the components are reported
  /** @type {string[]} */
  let declarations = []
  if (configPath) {
    const read = ts.readConfigFile(configPath, ts.sys.readFile)
    const parsed = ts.parseJsonConfigFileContent(
      read.config,
      ts.sys,
      path.dirname(configPath)
    )
    compilerOptions = parsed.options
    declarations = parsed.fileNames.filter((name) => name.endsWith('.d.ts'))
  }
  compilerOptions = { ...compilerOptions, noEmit: true }

  /** @type {Map<string, { file: string, source: string, code: string, script: { start: number, length: number, lines: number } | null }>} */
  const modules = new Map()
  for (const file of files) {
    const source = fs.readFileSync(file, 'utf-8')
    const { code, script } = parseSfc(source, file)
    modules.set(`${file}.ts`, { file, source, code, script })
  }

  const host = ts.createCompilerHost(compilerOptions)
  const { getSourceFile, fileExists, readFile } = host
  host.fileExists = (name) => modules.has(name) || fileExists.call(host, name)
  host.readFile = (name) => modules.get(name)?.code ?? readFile.call(host, name)
  host.getSourceFile = (name, languageVersion, ...rest) => {
    const module = modules.get(name)
    return module
      ? ts.createSourceFile(name, module.code, languageVersion, true)
      : getSourceFile.call(host, name, languageVersion, ...rest)
  }

  const program = ts.createProgram(
    [...modules.keys(), ...declarations],
    compilerOptions,
    host
  )
  /** @type {SfcError[]} */
  const errors = []
  for (const diagnostic of ts.getPreEmitDiagnostics(program)) {
    const module = diagnostic.file && modules.get(diagnostic.file.fileName)
    if (!module) continue
    // Past the generated header, the module is the script verbatim, so an
    // offset in one is an offset in the other
    const headerLength = module.code.length - (module.script?.length ?? 0)
    const offset = diagnostic.start ?? 0
    const at =
      module.script && offset >= headerLength
        ? module.script.start + offset - headerLength
        : 0
    const before = module.source.slice(0, at).split('\n')
    errors.push({
      file: module.file,
      line: before.length,
      column: before[before.length - 1].length + 1,
      code: diagnostic.code,
      message: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
    })
  }
  return errors
}

/** @param {string[]} argv */
async function main(argv) {
  /** @type {string | undefined} */
  let project
  /** @type {string[]} */
  const paths = []
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--project' || argv[i] === '-p') project = argv[++i]
    else paths.push(argv[i])
  }
  const files = findSfcFiles(paths.length ? paths : ['.'])
  const errors = await checkSfc(files, { project })
  for (const e of errors) {
    const where = path.relative(process.cwd(), e.file)
    console.log(
      `${where}:${e.line}:${e.column} - error TS${e.code}: ${e.message}`
    )
  }
  const s = files.length === 1 ? '' : 's'
  console.log(
    errors.length
      ? `${errors.length} error${errors.length === 1 ? '' : 's'} in ${files.length} component${s}.`
      : `${files.length} component${s}, no type errors.`
  )
  process.exitCode = errors.length ? 1 : 0
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href
) {
  await main(process.argv.slice(2))
}
