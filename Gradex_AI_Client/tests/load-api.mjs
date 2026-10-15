import { buildSync } from 'esbuild';
import { fileURLToPath } from 'node:url';

export async function loadApi(path) {
  const result = buildSync({
    entryPoints: [fileURLToPath(new URL(path, import.meta.url))],
    bundle: true, write: false, format: 'esm',
    define: { 'import.meta.env': '{"VITE_API_BASE_URL":"http://testserver"}' },
  });
  return import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].text).toString('base64')}`);
}
