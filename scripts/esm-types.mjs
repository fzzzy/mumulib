// The declarations tsc writes to dist/types serve `require`; `import` resolves
// types beside a package.json that says they are ESM, so they are copied
// there and marked.
import * as fs from 'node:fs/promises'

await fs.rm('dist/esm/types', { recursive: true, force: true })
await fs.cp('dist/types', 'dist/esm/types', { recursive: true })
await fs.writeFile('dist/esm/types/package.json', '{"type":"module"}\n')
