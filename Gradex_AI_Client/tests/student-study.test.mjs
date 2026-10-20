import assert from 'node:assert/strict';
import test from 'node:test';
import { loadApi } from './load-api.mjs';

const { fetchStudentMaterials, studentMaterialPdfUrl, fetchStudentPractice } = await loadApi('../src/app/api/studentApi.ts');
const exam = { subject_code: 'IT2040', session_name: 'Final / June', year: 2024, month: 6, semester: 1 };

test('student resources use authenticated student paths', async () => {
  const original = globalThis.fetch;
  let request;
  globalThis.fetch = async (url, init) => {
    request = { url, init };
    return { ok: true, json: async () => ({ status: 'ok', items: [] }) };
  };
  try {
    assert.deepEqual(await fetchStudentMaterials('S/1'), { status: 'ok', items: [] });
    assert.equal(request.url, 'http://testserver/api/students/S%2F1/materials');
    assert.equal(request.init.credentials, 'include');
    assert.equal(studentMaterialPdfUrl('S/1', 'a'.repeat(24)), 'http://testserver/api/students/S%2F1/materials/' + 'a'.repeat(24) + '/pdf');
  } finally { globalThis.fetch = original; }
});

test('practice sends every selected exam field and keeps model failures readable', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    const query = new URL(url).searchParams;
    assert.equal(query.get('course_code'), exam.subject_code);
    assert.equal(query.get('session_name'), exam.session_name);
    assert.equal(query.get('year'), '2024');
    assert.equal(query.get('month'), '6');
    assert.equal(query.get('semester'), '1');
    assert.equal(init.credentials, 'include');
    return { ok: false, status: 503, json: async () => ({ detail: { reason: 'model_unavailable' } }) };
  };
  try {
    await assert.rejects(fetchStudentPractice('S1', exam), /Practice generation is unavailable/);
  } finally { globalThis.fetch = original; }
});
