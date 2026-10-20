import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';
import { loadApi } from './load-api.mjs';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const page = readFileSync(new URL('../src/app/components/AnalyticsPage.tsx', import.meta.url), 'utf8');
// Execute the click handler without mounting unrelated charts and dialogs.
const handlerSource = page.match(/const handleSelectStudent = useCallback\((async .*?), \[selectedExam, students[^\]]*\]\);/s)[1];
const handlerCode = transformSync(`(${handlerSource})`, { loader: 'ts' }).code;
const { fetchLecturerStudentDetail, fetchLecturerStudentDetailStream } = await loadApi('../src/app/api/lecturerApi.ts');

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
    studentRequest: { current: null },
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

test('student stream forwards queue phases and ignores heartbeat progress', async () => {
  const originalFetch = globalThis.fetch;
  const updates = [];
  const event = (type, data) => `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
  const text = event('progress', { phase: 'queued', message: 'Waiting', progress: 0 })
    + event('ping', { message: 'alive', progress: 0 })
    + event('progress', { phase: 'analyzing', message: 'Classifying', progress: 35 })
    + event('result', { student_id: 'A' });
  let sent = false;
  globalThis.fetch = async () => ({ ok: true, body: { getReader: () => ({ read: async () => {
    if (sent) return { done: true };
    sent = true;
    return { done: false, value: new TextEncoder().encode(text) };
  } }) } });
  try {
    const result = await fetchLecturerStudentDetailStream('IT2040', 'Final', 'A', 2026, 7, 1, (...args) => updates.push(args));
    assert.equal(result.student_id, 'A');
    assert.deepEqual(updates, [['Waiting', 0, 'queued'], ['Classifying', 35, 'analyzing']]);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('student performance replaces the exam page and Back to exam preserves the exam destination', () => {
  const params = new URLSearchParams('student=S1&course=IT2040&session=Final&year=2026&month=7&semester=1');
  let stateIndex = 0;
  const exam = { course_code: 'IT2040', session_name: 'Final', year: 2026, month: 7, semester: 1 };
  const hooks = {
    ...React,
    useState: (initial) => {
      const index = stateIndex++;
      return [index === 0 ? [exam] : index === 1 ? exam : initial, () => {}];
    },
    useEffect() {},
    useRef: (value) => ({ current: value }),
    useCallback: (callback) => callback,
  };
  const stub = ({ children }) => React.createElement('div', null, children);
  const module = { exports: {} };
  vm.runInNewContext(transformSync(page, { loader: 'tsx', format: 'cjs' }).code, {
    URLSearchParams,
    module,
    exports: module.exports,
    require: (name) => {
      if (name === 'react') return hooks;
      if (name === 'react-router') return { useSearchParams: () => [params, () => {}],
        Link: ({ to, children }) => React.createElement('a', { href: to }, children) };
      if (name === 'framer-motion') return { motion: { div: stub, p: stub } };
      return new Proxy({}, { get: () => stub });
    },
  });
  const html = renderToStaticMarkup(React.createElement(module.exports.default));
  assert.match(html, /S1.*Performance/);
  assert.match(html, /Loading performance/);
  assert.doesNotMatch(html, /Individual Students|role="dialog"/);
  assert.match(html, /href="\?course=IT2040&amp;session=Final&amp;year=2026&amp;month=7&amp;semester=1">.*?Back to exam/s);
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

test('diagram-only details retry full student analysis', async () => {
  const result = await openStudent('diagram_only');
  assert.deepEqual(result.requests, ['health', 'stream']);
  assert.deepEqual(result.loaded, { student_id: 'S1' });
  assert.ok(result.notifications.some((event) => event.active && event.progress === 0));
  assert.ok(result.notifications.some((event) => event.progress === 100));
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

function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

function racingStudents(status = 'generated') {
  const requests = [], notifications = [], timers = [], errors = [];
  let loaded, error, loading;
  const context = {
    Error, URLSearchParams,
    studentRequest: { current: null },
    searchParams: new URLSearchParams(), setSearchParams() {},
    selectedExam: { course_code: 'IT2040', session_name: 'Final', year: 2026, month: 7, semester: 1 },
    students: ['A', 'B'].map(student_id => ({ student_id, analysis_status: status })),
    fetchLlmHealth: async () => ({ online: true, model_available: true }),
    fetchLecturerStudentDetail: (...args) => {
      const request = { ...deferred(), studentId: args[2], year: args[3] };
      requests.push(request);
      return request.promise;
    },
    fetchLecturerStudentDetailStream: (...args) => {
      const request = { ...deferred(), studentId: args[2], progress: args[6] };
      requests.push(request);
      return request.promise;
    },
    window: { dispatchEvent: (event) => notifications.push(event.detail) },
    CustomEvent: class { constructor(_, options) { this.detail = options.detail; } },
    setSelectedStudentId() {},
    setLoadingStudentDetail: value => { loading = value; },
    setStudentDetail: value => { loaded = value; },
    setStudentDetailError: value => { error = value; },
    setStudents() {}, setTimeout: fn => timers.push(fn), toast: { error: value => errors.push(value) },
  };
  const select = vm.runInNewContext(handlerCode, context);
  return { select, requests, notifications, timers, errors, context,
    get loaded() { return loaded; }, get error() { return error; }, get loading() { return loading; } };
}

for (const status of ['generated', 'pending']) test(`late student A success cannot replace student B (${status})`, async () => {
  const view = racingStudents(status);
  const first = view.select('A');
  await new Promise(resolve => setImmediate(resolve));
  const second = view.select('B');
  await new Promise(resolve => setImmediate(resolve));
  view.requests[1].resolve({ student_id: 'B' });
  await second;
  view.requests[0].resolve({ student_id: 'A' });
  await first;
  assert.equal(view.loaded.student_id, 'B');
});

test('obsolete model-health failure does not become the current student error', async () => {
  const view = racingStudents('pending');
  const health = [];
  view.context.fetchLlmHealth = () => {
    const request = deferred(); health.push(request); return request.promise;
  };
  const old = view.select('A');
  const current = view.select('B');
  health[0].reject(new Error('Old health failure'));
  await old;
  assert.equal(view.error, null);
  assert.equal(view.errors.length, 0);
  assert.equal(view.loading, true);
  health[1].resolve({ online: true, model_available: true });
  await new Promise(resolve => setImmediate(resolve));
  view.requests[0].resolve({ student_id: 'B' });
  await current;
});

test('URL changes hide previous student or exam errors before effects start the new load', () => {
  for (const query of ['student=B&year=2026', 'student=A&year=2027']) {
    const params = new URLSearchParams(`${query}&course=IT2040&session=Final&month=7&semester=1`);
    let index = 0;
    const exam = { course_code: 'IT2040', session_name: 'Final', year: 2026, month: 7, semester: 1 };
    const states = { 0: [exam, { ...exam, year: 2027 }], 1: exam,
      19: 'A', 22: 'Error belonging to the previous selection' };
    const hooks = { ...React,
      useState: initial => [index in states ? states[index++] : (index++, initial), () => {}],
      useEffect() {}, useRef: value => ({ current: value }), useCallback: callback => callback,
    };
    const stub = ({ children }) => React.createElement('div', null, children);
    const module = { exports: {} };
    vm.runInNewContext(transformSync(page, { loader: 'tsx', format: 'cjs' }).code, {
      module, exports: module.exports, URLSearchParams,
      require(name) {
        if (name === 'react') return hooks;
        if (name === 'react-router') return { useSearchParams: () => [params, () => {}], Link: stub };
        if (name === 'framer-motion') return { motion: { div: stub, p: stub } };
        return new Proxy({}, { get: () => stub });
      },
    });
    const html = renderToStaticMarkup(React.createElement(module.exports.default));
    assert.match(html, /Loading performance/);
    assert.doesNotMatch(html, /Error belonging to the previous selection/);
  }
});

test('obsolete errors and completion cannot clear the current loading state', async () => {
  const view = racingStudents();
  const first = view.select('A');
  const second = view.select('B');
  view.requests[0].reject(new Error('Old failure'));
  await first;
  assert.equal(view.error, null);
  assert.equal(view.loading, true);
  view.requests[1].resolve({ student_id: 'B' });
  await second;
  assert.equal(view.loading, false);
});

test('background student keeps progress and fallback without overwriting the selected student', async () => {
  const view = racingStudents('pending');
  const first = view.select('A');
  await new Promise(resolve => setImmediate(resolve));
  const second = view.select('B');
  await new Promise(resolve => setImmediate(resolve));
  view.requests[0].progress('Student A progress', 75);
  view.requests[0].reject(new Error('Old stream failure'));
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(view.notifications.some(event => event.studentId === 'A' && event.progress === 75));
  assert.equal(view.requests.length, 3);
  view.requests[2].resolve({ student_id: 'A' });
  await first;
  assert.ok(view.notifications.some(event => event.studentId === 'A' && !event.active && event.progress === 100));
  assert.equal(view.loaded, null);
  view.requests[1].resolve({ student_id: 'B' });
  await second;
});

test('completion closes only its own notification without a delayed timer', async () => {
  const view = racingStudents('pending');
  const first = view.select('A');
  await new Promise(resolve => setImmediate(resolve));
  view.requests[0].resolve({ student_id: 'A' });
  await first;
  const second = view.select('B');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(view.timers.length, 0);
  assert.ok(view.notifications.some(event => event.studentId === 'A' && !event.active && event.status === 'complete'));
  assert.ok(view.notifications.some(event => event.studentId === 'B' && event.active));
  view.requests[1].resolve({ student_id: 'B' });
  await second;
});

test('switching students during the health check still submits both analyses', async () => {
  const view = racingStudents('pending');
  const health = [];
  view.context.fetchLlmHealth = () => {
    const request = deferred(); health.push(request); return request.promise;
  };
  const first = view.select('A');
  const second = view.select('B');
  health[0].resolve({ online: true, model_available: true });
  health[1].resolve({ online: true, model_available: true });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(view.requests.map(request => request.studentId), ['A', 'B']);
  view.requests[0].resolve({ student_id: 'A' });
  view.requests[1].resolve({ student_id: 'B' });
  await Promise.all([first, second]);
  assert.equal(view.loaded.student_id, 'B');
});

test('changing exam invalidates a pending student request with the same student ID', async () => {
  const view = racingStudents();
  const old = view.select('A');
  const examSource = page.match(/const handleSelectExam = useCallback\((async .*?), \[\]\);/s)[1];
  Object.assign(view.context, {
    setSelectedExam: exam => { view.context.selectedExam = exam; },
    fetchExamAnalyticsStream: async () => ({}), fetchTeachingActions: async () => [], fetchExamStudents: async () => [],
  });
  for (const setter of ['setLoadingAnalytics', 'setLoadingStudents', 'setAnalytics', 'setLiveModelMessage',
    'setStudentSearch', 'setLoadSteps', 'setCurrentLoadStep', 'setLoadingActions', 'setTeachingActions',
    'setSelectedTopic', 'setSelectedQuestion', 'setPaperOpen', 'setStudentListError']) view.context[setter] = () => {};
  view.context.handleSelectExam = vm.runInNewContext(transformSync(`(${examSource})`, { loader: 'ts' }).code, view.context);
  await view.context.handleSelectExam({ ...view.context.selectedExam, year: 2027 });
  const current = view.select('A');
  view.requests[1].resolve({ student_id: 'A', year: 2027 });
  await current;
  view.requests[0].resolve({ student_id: 'A', year: 2026 });
  await old;
  assert.equal(view.loaded.year, 2027);
});
