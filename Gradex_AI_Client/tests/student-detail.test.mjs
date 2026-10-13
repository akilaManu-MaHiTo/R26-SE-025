import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const page = readFileSync(new URL('../src/app/components/AnalyticsPage.tsx', import.meta.url), 'utf8');
// Execute the click handler without mounting unrelated charts and dialogs.
const handlerSource = page.match(/const handleSelectStudent = useCallback\((async .*?), \[selectedExam, students[^\]]*\]\);/s)[1];
const handlerCode = transformSync(`(${handlerSource})`, { loader: 'ts' }).code;
const apiSource = readFileSync(new URL('../src/app/api/lecturerApi.ts', import.meta.url), 'utf8');
const apiCode = transformSync(apiSource, { loader: 'ts', format: 'esm' }).code;
const { fetchLecturerStudentDetail } = await import(`data:text/javascript;base64,${Buffer.from(apiCode).toString('base64')}`);

async function openStudent(status, { missing = false, streamFails = false, modelOnline = true } = {}) {
  const requests = [];
  const notifications = [];
  let loaded;
  let error;
  let destination;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    requests.push(new URL(url));
    return { ok: !missing, status: missing ? 423 : 200, json: async () => missing ? { detail: 'analytics not yet generated' } : { student_id: 'S1' } };
  };
  const context = {
    Error,
    URLSearchParams,
    searchParams: new URLSearchParams(),
    setSearchParams: (value) => { destination = new URLSearchParams(value); },
    selectedExam: { course_code: 'IT2040', session_name: 'Final', year: 2026, month: 7, semester: 1 },
    students: [{ student_id: 'S1', analysis_status: status }],
    fetchLecturerStudentDetail,
    fetchLlmHealth: async () => { requests.push('health'); return { online: modelOnline, model_available: modelOnline }; },
    fetchLecturerStudentDetailStream: async () => {
      requests.push('stream');
      if (streamFails) throw new Error('stream unavailable');
      return { student_id: 'S1' };
    },
    window: { dispatchEvent: (event) => notifications.push(event.detail) },
    CustomEvent: class { constructor(_, options) { this.detail = options.detail; } },
    setSelectedStudentId() {}, setLoadingStudentDetail() {},
    setStudentDetail: (value) => { loaded = value; },
    setStudentDetailError: (value) => { error = value; },
    setStudents() {}, setTimeout() {}, toast: { error() {} },
  };
  try {
    await vm.runInNewContext(handlerCode, context)('S1');
    return { requests, notifications, loaded, error, destination };
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('opening a student navigates to a performance page with the full exam identity', async () => {
  const { destination } = await openStudent('generated');
  assert.ok(destination, 'click should navigate to a separate page');
  assert.equal(destination.get('student'), 'S1');
  assert.equal(destination.get('course'), 'IT2040');
  assert.equal(destination.get('session'), 'Final');
  assert.equal(destination.get('year'), '2026');
  assert.equal(destination.get('month'), '7');
  assert.equal(destination.get('semester'), '1');
});

test('student performance replaces the exam page and Back to exam clears the student destination', () => {
  const params = new URLSearchParams('student=S1&course=IT2040&session=Final&year=2026&month=7&semester=1');
  let destination;
  let stateIndex = 0;
  let goBack;
  const hooks = {
    ...React,
    useState: (initial) => [stateIndex++ === 1 ? { course_code: 'IT2040', session_name: 'Final', year: 2026 } : initial, () => {}],
    useEffect() {},
    useCallback: (callback) => callback,
  };
  const stub = ({ children, onClick }) => {
    if (onClick) goBack = onClick;
    return React.createElement('div', null, children);
  };
  const module = { exports: {} };
  vm.runInNewContext(transformSync(page, { loader: 'tsx', format: 'cjs' }).code, {
    URLSearchParams,
    module,
    exports: module.exports,
    require: (name) => {
      if (name === 'react') return hooks;
      if (name === 'react-router') return { useSearchParams: () => [params, (value) => { destination = value; }] };
      if (name === 'framer-motion') return { motion: { div: stub, p: stub } };
      return new Proxy({}, { get: () => stub });
    },
  });
  const html = renderToStaticMarkup(React.createElement(module.exports.default));
  assert.match(html, /S1.*Performance/);
  assert.match(html, /Loading performance/);
  assert.doesNotMatch(html, /Individual Students|role="dialog"/);
  goBack();
  assert.equal(destination.has('student'), false);
  assert.equal(destination.get('course'), 'IT2040');
});

test('pending student opens the page with an error when the model is offline', async () => {
  const result = await openStudent('pending', { modelOnline: false });
  assert.equal(result.destination.get('student'), 'S1');
  assert.deepEqual(result.requests, ['health']);
  assert.match(result.error, /Model unavailable/);
});

test('Ready student loads saved details without analysis or model notifications', async () => {
  const result = await openStudent('generated');
  assert.equal(result.requests.length, 1);
  assert.ok(result.requests[0] instanceof URL);
  assert.equal(result.requests[0].searchParams.get('auto_analyze'), 'false');
  assert.deepEqual(result.loaded, { student_id: 'S1' });
  assert.equal(result.notifications.length, 0);
});

test('missing saved details for a Ready student shows an error without starting analysis', async () => {
  const result = await openStudent('generated', { missing: true });
  assert.equal(result.requests.length, 1);
  assert.ok(result.requests[0] instanceof URL);
  assert.equal(result.requests[0].searchParams.get('auto_analyze'), 'false');
  assert.equal(result.error, 'analytics not yet generated');
  assert.equal(result.notifications.length, 0);
});

test('diagram-only details reopen without model requests or analysis notifications', async () => {
  const result = await openStudent('diagram_only');
  assert.equal(result.requests.length, 1);
  assert.ok(result.requests[0] instanceof URL);
  assert.equal(result.requests[0].searchParams.get('auto_analyze'), 'false');
  assert.deepEqual(result.loaded, { student_id: 'S1' });
  assert.equal(result.notifications.length, 0);
});

test('pending student still checks the model and streams analysis progress', async () => {
  const result = await openStudent('pending');
  assert.deepEqual(result.requests, ['health', 'stream']);
  assert.deepEqual(result.loaded, { student_id: 'S1' });
  assert.ok(result.notifications.some((event) => event.active && event.progress === 0));
  assert.ok(result.notifications.some((event) => event.progress === 100));
});

test('pending student retains automatic analysis when the stream fails', async () => {
  const result = await openStudent('pending', { streamFails: true });
  assert.deepEqual(result.requests.slice(0, 2), ['health', 'stream']);
  assert.notEqual(result.requests[2].searchParams.get('auto_analyze'), 'false');
  assert.deepEqual(result.loaded, { student_id: 'S1' });
});
