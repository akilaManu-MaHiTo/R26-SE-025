import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { transformSync } from 'esbuild';

const source = readFileSync(new URL('../src/app/api/taxonomyApi.ts', import.meta.url), 'utf8');
const code = transformSync(source.replace('import.meta', '({ env: { VITE_GRADEX_API_KEY: "test-key" } })'), { loader: 'ts', format: 'esm' }).code;
const api = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);

test('taxonomy courses load from the analytics endpoint with authentication', async () => {
  assert.equal(typeof api.fetchTaxonomyCourses, 'function');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(new URL(url).pathname, '/api/courses');
    assert.equal(options.headers['X-API-Key'], 'test-key');
    return { ok: true, json: async () => ({ items: [{ code: 'IT2040' }] }) };
  };
  try {
    assert.deepEqual(await api.fetchTaxonomyCourses(), [{ code: 'IT2040' }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
