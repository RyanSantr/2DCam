import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
await build({
  absWorkingDir: root,
  entryPoints: ['avatarcam/web3d/viewer-source.js'],
  outfile: 'avatarcam/web3d/viewer.js',
  nodePaths: [fileURLToPath(new URL('node_modules', import.meta.url))],
  bundle: true,
  format: 'esm',
  target: 'es2022',
  minify: true,
});
if (process.env.AVATARCAM_ENABLE_CUBISM_BUILD === '1') await build({
  absWorkingDir: root,
  entryPoints: ['avatarcam/web3d/live2d-source.js'],
  outfile: 'avatarcam/web3d/live2d.js',
  nodePaths: [fileURLToPath(new URL('node_modules', import.meta.url))],
  bundle: true, format: 'esm', target: 'es2022', minify: true,
});
