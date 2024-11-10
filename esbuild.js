#!/usr/bin/env node

import * as esbuild from 'esbuild';
import * as chokidar from 'chokidar';
import * as fs from 'fs/promises';


const isServe = process.argv.includes('--serve');


const args = {
  format: 'esm',
  logLevel: 'info',
  entryPoints: [
    './src/index.ts',
    './examples/use_state/state_example.ts',
    './examples/use_state_input/input_example.ts',
    './examples/use_state_selected/selected_example.ts',
    './examples/use_patslot/patslot_example.ts',
    './examples/use_patslot_fill/fill_example.ts',
    './examples/use_patslot_nested/nested_example.ts',
    './examples/use_dialog/dialog_example.ts'
  ],
  bundle: true,
  sourcemap: true,
  outdir: 'dist',
  external: ['http', 'fs', 'path'],
};


if (isServe) {
  let ctx = await esbuild.context(args);

  let watcher = chokidar.watch(['src', 'examples'], {
    ignored: /(^|[\/\\])\../, // ignore dotfiles
    persistent: true
  });

  watcher
    .on('add', async (path) => {
      console.log(`File ${path} has been added`);
      if (path.endsWith('.html') || path.endsWith('.png')) {
        const outputPath = path.replace('src', 'dist/src').replace('examples', 'dist/examples');
        await fs.mkdir(outputPath.split('/').slice(0, -1).join('/'), { recursive: true });
        await fs.copyFile(path, outputPath);
        await fs.copyFile('index.html', 'dist/index.html');
      }
    })
    .on('change', async (path) => {
      console.log(`File ${path} has been changed`)
      if (path.endsWith('.html') || path.endsWith('.png')) {
        const outputPath = path.replace('src', 'dist/src').replace('examples', 'dist/examples');
        await fs.mkdir(outputPath.split('/').slice(0, -1).join('/'), { recursive: true });
        await fs.copyFile(path, outputPath);
        await fs.copyFile('index.html', 'dist/index.html');
        let touch = await fs.open('src/index.ts', 'a');
        await touch.write('\n');
        await touch.close();
      }
      ctx.rebuild();
    })
    .on('unlink', async (path) => {
      console.log(`File ${path} has been removed`)
      const outputPath = path.replace('src', 'dist').replace('examples', 'dist/examples').replace('.ts', '.js');
      await fs.rm(outputPath);
      await fs.copyFile('index.html', 'dist/index.html');
    });

  await ctx.serve({
    servedir: 'dist',
    port: 8000,
  });
} else {
  await esbuild.build(args);
}
