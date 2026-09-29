// The declarations tsc writes to dist/types serve `require`; `import` resolves
// types beside a package.json that says they are ESM, so they are copied
// there and marked.
import * as fs from 'node:fs/promises'

// sfc-client.d.ts is a declaration already, which tsc checks but does not
// copy into its output
await fs.copyFile('src/vite/sfc-client.d.ts', 'dist/types/vite/sfc-client.d.ts')

await fs.rm('dist/esm/types', { recursive: true, force: true })
await fs.cp('dist/types', 'dist/esm/types', { recursive: true })
await fs.writeFile('dist/esm/types/package.json', '{"type":"module"}\n')
