import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { loadApi } from './load-api.mjs';

const api = await loadApi('../src/app/api/taxonomyApi.ts');

test('new course is posted to the same courses collection endpoint with authentication', async () => {
  const originalFetch = globalThis.fetch;
  const course = { code: 'IT2050', name: 'New Course', description: '' };
  globalThis.fetch = async (url, options) => {
    assert.equal(new URL(url).pathname, '/api/courses');
    assert.equal(options.credentials, 'include');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), course);
    return { ok: true, json: async () => ({ _id: 'saved-course-id', ...course }) };
  };
  try { assert.deepEqual(await api.createCourse(course), { _id: 'saved-course-id', ...course }); }
  finally { globalThis.fetch = originalFetch; }
});

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
