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

// mumulib/node: domino's DOM, then the library, which reads document as it
// loads. Two imports, written here rather than bundled, so that nothing can
// move the library ahead of the DOM; src/node.ts is the same, for its types.
await fs.writeFile(
  'dist/esm/node.mjs',
  "import './dom.mjs'\nexport * from './index.mjs'\n"
)
await fs.writeFile(
  'dist/cjs/node.cjs',
  "'use strict'\nrequire('./dom.cjs')\nmodule.exports = require('./index.cjs')\n"
)

await fs.rm('dist/esm/types', { recursive: true, force: true })
await fs.cp('dist/types', 'dist/esm/types', { recursive: true })
await fs.writeFile('dist/esm/types/package.json', '{"type":"module"}\n')
