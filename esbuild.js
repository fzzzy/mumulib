#!/usr/bin/env node

import * as esbuild from 'esbuild';
import * as chokidar from 'chokidar';
import * as fs from 'fs/promises';


const isServe = process.argv.includes('--serve');


const args = {
  format: 'esm',
  logLevel: 'info',
  entryPoints: ['./src/index.ts', './examples/use_state.ts', './examples/use_patslot.ts', './examples/use_dialog.ts', './examples/use_patslot/index.ts', './examples/use_patslot/patslot_example.ts'],
  bundle: true,
  sourcemap: true,
  outdir: 'dist',
  outbase: 'src',
};


if (isServe) {
  let ctx = await esbuild.context(args);

  let watcher = chokidar.watch('src', {
    ignored: /(^|[\/\\])\../, // ignore dotfiles
    persistent: true
  });

  watcher
    .on('add', async (path) => {
      console.log(`File ${path} has been added`);
      if (path.endsWith('.html') || path.endsWith('.png')) {
        const outputPath = path.replace('src', 'dist');
        await fs.copyFile(path, outputPath);
      }
    })
    .on('change', async (path) => {
      console.log(`File ${path} has been changed`)
      if (path.endsWith('.html') || path.endsWith('.png')) {
        const outputPath = path.replace('src', 'dist');
        await fs.copyFile(path, outputPath);
        let touch = await fs.open('src/index.ts', 'a');
        await touch.write('\n');
        await touch.close();
      }
      ctx.rebuild();
    })
    .on('unlink', async (path) => {
      console.log(`File ${path} has been removed`)
      const outputPath = path.replace('src', 'dist').replace('.ts', '.js');
      await fs.rm(outputPath);
    });

  await ctx.serve({
    servedir: 'dist',
    port: 8000,
  });
} else {
  await esbuild.build(args);
}
