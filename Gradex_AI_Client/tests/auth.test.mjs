import assert from 'node:assert/strict';
import test from 'node:test';
import { loadApi } from './load-api.mjs';

const api = await loadApi('../src/app/api/authApi.ts');

test('login sends credentials and accepts only server-provided identity', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(new URL(url).pathname, '/api/auth/login');
    assert.equal(init.credentials, 'include');
    assert.deepEqual(JSON.parse(init.body), { email: 'teacher@example.edu', password: 'secret' });
    return { ok: true, status: 200, json: async () => ({ role: 'lecturer', email: 'teacher@example.edu', student_id: null }) };
  };
  try { assert.equal((await api.login('teacher@example.edu', 'secret')).role, 'lecturer'); }
  finally { globalThis.fetch = original; }
});

test('rejected credentials clear the UI session and surface the error', async () => {
  const original = globalThis.fetch;
  globalThis.window = new EventTarget();
  let expired = 0;
  window.addEventListener('gradex:unauthorized', () => expired++);
  globalThis.fetch = async () => ({ ok: false, status: 401, json: async () => ({ detail: 'Invalid email or password' }) });
  try {
    await assert.rejects(api.login('student@example.edu', 'wrong'), /Invalid email or password/);
    assert.equal(expired, 1);
    assert.equal(await api.currentUser(), null);
  } finally { globalThis.fetch = original; delete globalThis.window; }
});

test('logout reports failed revocation instead of pretending to sign out', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    assert.equal(new URL(url).pathname, '/api/auth/logout');
    assert.equal(init.method, 'POST');
    assert.equal(init.credentials, 'include');
    return { ok: false, status: 503 };
  };
  try { await assert.rejects(api.logout(), /Could not sign out/); }
  finally { globalThis.fetch = original; }
});
