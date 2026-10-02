// The declarations tsc writes to dist/types serve `require`; `import` resolves
// types beside a package.json that says they are ESM, so they are copied
// there and marked.
import * as fs from 'node:fs/promises'

// sfc-client.d.ts is a declaration already, which tsc checks but does not
// copy into its output; and the Vite plugins and the checker ship as they are
await fs.copyFile('src/vite/sfc-client.d.ts', 'dist/types/vite/sfc-client.d.ts')
await fs.mkdir('dist/vite', { recursive: true })
await fs.copyFile('src/vite/sfc.mjs', 'dist/vite/sfc.mjs')
await fs.copyFile('src/vite/origin.mjs', 'dist/vite/origin.mjs')
await fs.copyFile('src/vite/sfc-check.mjs', 'dist/vite/sfc-check.mjs')

await fs.rm('dist/esm/types', { recursive: true, force: true })
await fs.cp('dist/types', 'dist/esm/types', { recursive: true })
await fs.writeFile('dist/esm/types/package.json', '{"type":"module"}\n')
