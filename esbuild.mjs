#!/usr/bin/env node
import * as esbuild from 'esbuild';
import chokidar from 'chokidar';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFile } from 'node:child_process';
import { promisify } from 'node:util';

const root = path.dirname(fileURLToPath(import.meta.url));
process.chdir(root);
const execFileAsync = promisify(execFile);
const serving = process.argv.includes('--serve');
const port = Number(process.env.PORT || 8000);

async function files(dir) {
    const entries = await fs.readdir(dir, { withFileTypes: true });
    const nested = await Promise.all(entries.map(entry => {
        const filename = path.join(dir, entry.name);
        return entry.isDirectory() ? files(filename) : [filename];
    }));
    return nested.flat();
}

async function declarations() {
    await fs.rm('dist/types', { recursive: true, force: true });
    await execFileAsync(process.execPath, ['node_modules/typescript/bin/tsc']);
    await fs.cp('dist/types', 'dist/esm/types', { recursive: true });
    await fs.writeFile('dist/esm/types/package.json', '{"type":"module"}\n');
}

async function copyAsset(filename) {
    const target = path.join('dist', filename);
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.copyFile(filename, target);
}

const common = { bundle: true, sourcemap: true, logLevel: 'info' };
const library = { ...common, entryPoints: ['src/index.ts'], platform: 'node', target: 'node20', external: ['domino'] };
const nodeBuilds = [
    { ...library, format: 'cjs', outfile: 'dist/cjs/index.cjs',
      banner: { js: "if (typeof document === 'undefined') globalThis.document = require('domino').createWindow('').document;" } },
    { ...library, format: 'esm', outfile: 'dist/esm/index.mjs',
      banner: { js: "import domino from 'domino';\nif (typeof document === 'undefined') globalThis.document = domino.createWindow('').document;" } },
];

async function browserOptions() {
    return { ...common, format: 'esm', platform: 'browser', target: 'es2020',
        entryPoints: ['src/index.ts', ...(await files('examples')).filter(file => file.endsWith('.ts'))],
        outbase: '.', outdir: 'dist/browser', outExtension: { '.js': '.mjs' },
        alias: { mumulib: './src/index.ts' },
    };
}

let context;
let watcher;
let queue = Promise.resolve();
let closing = false;
async function shutdown() {
    closing = true;
    await watcher?.close();
    await queue;
    await context?.dispose();
}

try {
    await fs.rm('dist', { recursive: true, force: true });
    await Promise.all(nodeBuilds.map(options => esbuild.build(options)));
    context = await esbuild.context(await browserOptions());
    await context.rebuild();
    for (const file of ['index.html', ...(await files('examples')).filter(file => !file.endsWith('.ts'))]) {
        await copyAsset(file);
    }
    await declarations();
    if (!serving) {
        await context.dispose();
    } else {
        watcher = chokidar.watch(['src', 'examples', 'index.html'], { ignoreInitial: true });
        watcher.on('all', (event, filename) => {
            if (closing || !['add', 'change', 'unlink'].includes(event)) return;
            queue = queue.then(async () => {
                if (filename.endsWith('.ts')) {
                    // Recreate the context so newly added/deleted examples change entry points.
                    if (event !== 'change') {
                        await context.dispose();
                        await fs.rm('dist/browser', { recursive: true, force: true });
                        context = await esbuild.context(await browserOptions());
                        await context.serve({ servedir: 'dist', host: '127.0.0.1', port });
                    }
                    await context.rebuild();
                    await Promise.all(nodeBuilds.map(options => esbuild.build(options)));
                    await fs.rm('dist/esm/types', { recursive: true, force: true });
                    await declarations();
                } else if (event === 'unlink') {
                    await fs.rm(path.join('dist', filename), { force: true });
                } else {
                    await copyAsset(filename);
                }
            }).catch(error => console.error('Rebuild failed:', error));
        });
        watcher.on('error', error => console.error('Watcher failed:', error));
        await context.serve({ servedir: 'dist', host: '127.0.0.1', port });
        for (const signal of ['SIGINT', 'SIGTERM']) {
            process.once(signal, () => { shutdown().catch(console.error); });
        }
    }
} catch (error) {
    console.error(error);
    await shutdown();
    process.exitCode = 1;
}
