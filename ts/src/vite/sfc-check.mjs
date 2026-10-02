#!/usr/bin/env node
/**
 * Type checking for .sfc.html components, which tsc cannot see and Vite only
 * strips of their types. Each component becomes, in memory, the module the
 * plugin makes of it; TypeScript checks those with the project's tsconfig,
 * their imports resolving as usual from disk; and every error is put back at
 * its line and column in the .sfc.html, the script being copied verbatim.
 *
 * The files the tsconfig names are checked too, in the same program, and an
 * import of a .sfc.html in any of them resolves to that module: so importing
 * a component gives its own class, with its own properties, where tsc alone
 * knows only the `declare module '*.sfc.html'` of sfc-client, some custom
 * element. Run it in place of tsc, not beside it.
 *
 *     mumulib-sfc-check [--project tsconfig.json] [--declarations] [dir or file ...]
 *
 * With --declarations it also writes each component's declarations beside it,
 * <name>.sfc.html.d.ts, so tsc and editors know its class too.
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
 * @param {{ project?: string, sources?: boolean }} [options] the tsconfig,
 *   found from the working directory if not given; and whether to check the
 *   files it names too, not only the components

 * @returns {Promise<SfcError[]>}
 */
export async function checkSfc(files, options = {}) {
  const { ts, program, modules, sources } = await buildProgram(files, options, {
    noEmit: true,
  })
  const reported = new Set(sources)
  /** @type {SfcError[]} */
  const errors = []
  for (const diagnostic of ts.getPreEmitDiagnostics(program)) {
    // A project file's error is where it says, as tsc would put it
    if (diagnostic.file && reported.has(diagnostic.file.fileName)) {
      const where = diagnostic.file.getLineAndCharacterOfPosition(
        diagnostic.start ?? 0
      )
      errors.push({
        file: diagnostic.file.fileName,
        line: where.line + 1,
        column: where.character + 1,
        code: diagnostic.code,
        message: ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'),
      })
      continue
    }
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

/**
 * Declarations for each component in `files`, written beside it as
 * `<name>.sfc.html.d.ts`: what TypeScript reads for `import ... from
 * './<name>.sfc.html'`, with no setting needed, ahead of sfc-client's
 * wildcard. So tsc and an editor know a component's own class too. They are
 * generated from the component, and are not for editing or committing.
 *
 * @param {string[]} files absolute paths of .sfc.html files
 * @param {{ project?: string }} [options] the tsconfig, as for checkSfc
 * @returns {Promise<string[]>} the declaration files written
 */
export async function writeDeclarations(files, options = {}) {
  const { program, modules } = await buildProgram(files, options, {
    noEmit: false,
    declaration: true,
    emitDeclarationOnly: true,
    noEmitOnError: false,
  })
  /** @type {string[]} */
  const written = []
  for (const [name, module] of modules) {
    if (!files.includes(module.file)) continue
    const source = program.getSourceFile(name)
    if (!source) continue
    program.emit(source, (_out, text) => {
      const target = `${module.file}.d.ts`
      const header = `// Generated by mumulib-sfc-check from ${path.basename(module.file)}; do not edit.\n`
      fs.writeFileSync(target, header + text)
      written.push(target)
    })
  }
  return written
}

/**
 * The program checkSfc and writeDeclarations share: the components as the
 * plugin makes them, the tsconfig's own files if asked for, and imports of a
 * .sfc.html resolving to its component.
 *
 * @param {string[]} files
 * @param {{ project?: string, sources?: boolean }} options
 * @param {import('typescript').CompilerOptions} overrides
 */
async function buildProgram(files, options, overrides) {
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
  // The project's own files, checked and reported alongside the components
  /** @type {string[]} */
  let sources = []
  if (configPath) {
    const read = ts.readConfigFile(configPath, ts.sys.readFile)
    const parsed = ts.parseJsonConfigFileContent(
      read.config,
      ts.sys,
      path.dirname(configPath)
    )
    compilerOptions = parsed.options
    declarations = parsed.fileNames.filter((name) => name.endsWith('.d.ts'))
    sources = options.sources
      ? parsed.fileNames.filter((name) => !name.endsWith('.d.ts'))
      : []
  }
  compilerOptions = { ...compilerOptions, ...overrides }

  /** @type {Map<string, { file: string, source: string, code: string, script: { start: number, length: number, lines: number } | null }>} */
  const modules = new Map()
  /** The module a .sfc.html becomes, made the first time it is asked for. @param {string} file */
  const moduleFor = (file) => {
    const name = `${file}.ts`
    if (!modules.has(name)) {
      const source = fs.readFileSync(file, 'utf-8')
      const { code, script } = parseSfc(source, file)
      modules.set(name, { file, source, code, script })
    }
    return name
  }
  for (const file of files) moduleFor(file)

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
  // An import of a .sfc.html is its component's module, as the plugin makes
  // it -- not the wildcard declaration -- and the rest resolve as usual
  host.resolveModuleNameLiterals = (literals, containing, redirected, opts) =>
    literals.map((literal) => {
      const specifier = literal.text
      if (specifier.endsWith('.sfc.html') && specifier.startsWith('.')) {
        const file = path.resolve(path.dirname(containing), specifier)
        if (fs.existsSync(file)) {
          return {
            resolvedModule: {
              resolvedFileName: moduleFor(file),
              extension: ts.Extension.Ts,
              isExternalLibraryImport: false,
            },
          }
        }
      }
      return ts.resolveModuleName(
        specifier,
        containing,
        opts,
        host,
        undefined,
        redirected
      )
    })

  const program = ts.createProgram(
    [...modules.keys(), ...sources, ...declarations],
    compilerOptions,
    host
  )
  return { ts, program, modules, sources }
}

/** @param {string[]} argv */
async function main(argv) {
  /** @type {string | undefined} */
  let project
  let declarations = false
  /** @type {string[]} */
  const paths = []
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--project' || argv[i] === '-p') project = argv[++i]
    else if (argv[i] === '--declarations') declarations = true
    else paths.push(argv[i])
  }
  const files = findSfcFiles(paths.length ? paths : ['.'])
  // Given a tsconfig, its own files are checked too; searching from the
  // working directory, as before, only the components are
  const errors = await checkSfc(files, {
    project,
    sources: project !== undefined,
  })
  for (const e of errors) {
    const where = path.relative(process.cwd(), e.file)
    console.log(
      `${where}:${e.line}:${e.column} - error TS${e.code}: ${e.message}`
    )
  }
  const s = files.length === 1 ? '' : 's'
  const where = project ? ` and ${path.basename(project)}'s files` : ''
  console.log(
    errors.length
      ? `${errors.length} error${errors.length === 1 ? '' : 's'} in ${files.length} component${s}${where}.`
      : `${files.length} component${s}${where}, no type errs.`
  )
  if (declarations) {
    const written = await writeDeclarations(files, { project })
    const n = written.length
    console.log(
      `Wrote ${n} declaration${n === 1 ? '' : 's'}, <name>.sfc.html.d.ts.`
    )
  }
  process.exitCode = errors.length ? 1 : 0
}

if (
  process.argv[1] &&
  import.meta.url === pathToFileURL(fs.realpathSync(process.argv[1])).href
) {
  await main(process.argv.slice(2))
}
