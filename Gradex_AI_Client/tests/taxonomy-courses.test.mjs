import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { loadApi } from './load-api.mjs';

const api = await loadApi('../src/app/api/taxonomyApi.ts');

test('taxonomy courses load from the analytics endpoint with authentication', async () => {
  assert.equal(typeof api.fetchTaxonomyCourses, 'function');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, options) => {
    assert.equal(new URL(url).pathname, '/api/courses');
    assert.equal(options.credentials, 'include');
    return { ok: true, json: async () => ({ items: [{ code: 'IT2040' }] }) };
  };
  try {
    assert.deepEqual(await api.fetchTaxonomyCourses(), [{ code: 'IT2040' }]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});
