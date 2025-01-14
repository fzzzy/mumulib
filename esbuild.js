#!/usr/bin/env node

const esbuild = require('esbuild');
const chokidar = require('chokidar');
const fs = require('fs/promises');
const { exec } = require('child_process');

(async function main() {

  const isServe = process.argv.includes('--serve');

  const commonArgs = {
    logLevel: 'info',
    alias: {
      'mumulib': './src/index.ts',
    },
    define: {
      document: 'document',
    },
    entryPoints: [
      './src/index.ts',
      './examples/use_state/state_example.ts',
      './examples/use_state_input/input_example.ts',
      './examples/use_state_select_textarea/select_textarea_example.ts',
      './examples/use_state_selected/selected_example.ts',
      './examples/use_state_update/update_example.ts',
      './examples/use_state_selected_update/selected_update_example.ts',
      './examples/use_patslot/patslot_example.ts',
      './examples/use_patslot_fill/fill_example.ts',
      './examples/use_patslot_nested/nested_example.ts',
      './examples/use_patslot_template/template_example.ts',
      './examples/use_dialog/dialog_example.ts'
    ],
    bundle: true,
    sourcemap: true,
    outdir: 'dist',
    external: ['http', 'fs', 'path', 'domino'],
  };

  const builds = [
    {
      ...commonArgs,
      format: 'cjs',
      target: 'node20',
      outdir: 'dist/cjs',
    },
    {
      ...commonArgs,
      format: 'esm',
      target: 'es2020',
      outdir: 'dist/esm',
    }
  ];

  const testArgs = {
    logLevel: 'info',
    alias: {
      'mumulib': './src/index.ts',
    },
    define: {
      document: 'document',
    },
    entryPoints: [
      './src/test.ts',
    ],
    bundle: true,
    sourcemap: true,
    outdir: 'dist',
    external: ['domino', 'chromium-bidi', './loader', "playwright"],
    platform: 'node',
    format: 'cjs',
    target: 'node20',
    outdir: 'dist/test',
};

  await esbuild.build(builds[0]);
  await esbuild.build(builds[1]);
  await esbuild.build(testArgs);

  exec('node_modules/typescript/bin/tsc', (error, stdout, stderr) => {
    console.log('Generating type declarations...');
    console.log(stdout);
    if (error) {
      console.error(`Error generating type declarations: ${error}\n${stderr}`);
      process.exit(1);
    }
    console.log(`Type declarations generated.\n${stdout}`);
    if (stderr) {
      console.error(`TypeScript warnings/errors:\n${stderr}`);
    }
  });

  if (isServe) {
    let ctx = await esbuild.context(builds[0]);

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

    let ctx2 = await esbuild.context(testArgs);

    let watcher2 = chokidar.watch(['src/test.ts'], {
      ignored: /(^|[\/\\])\../, // ignore dotfiles
      persistent: true
    });
    watcher2.on('change', async (path) => {
      console.log(`Test ${path} has been changed`)
      ctx2.rebuild();
    })

  
    await ctx.serve({
      servedir: 'dist',
      port: 8000,
    });
  }
})().catch((e) => {
  console.error(e);
  process.exit(1);
});

