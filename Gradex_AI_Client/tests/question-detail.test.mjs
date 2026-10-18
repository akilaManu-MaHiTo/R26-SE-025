import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { transformSync } from 'esbuild';
import { loadApi } from './load-api.mjs';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const api = await loadApi('../src/app/api/lecturerApi.ts');
const exam = { course_code: 'IT/2040', session_name: 'Final Examination', year: 2022, month: 7, semester: 1 };

test('topic approval saves a canonical choice or clears it for the exact exam question', async () => {
  assert.equal(typeof api.saveQuestionTopic, 'function');
  const originalFetch = globalThis.fetch;
  const choices = [];
  globalThis.fetch = async (url, options) => {
    const request = new URL(url);
    assert.equal(request.pathname, '/api/lecturers/exams/IT%2F2040/Final%20Examination/questions/01/topic');
    assert.equal(request.search, '?year=2022&month=7&semester=1');
    assert.equal(options.method, 'PUT');
    choices.push(JSON.parse(options.body).topic);
    return { ok: true, json: async () => ({ approved_topic: choices.at(-1) }) };
  };
  try {
    await api.saveQuestionTopic(exam, '01', 'Schema Refinement');
    await api.saveQuestionTopic(exam, '01', null);
    assert.deepEqual(choices, ['Schema Refinement', null]);
  } finally { globalThis.fetch = originalFetch; }
});

test('topic approval reports rejected writes instead of implying success', async () => {
  assert.equal(typeof api.saveQuestionTopic, 'function');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 409, json: async () => ({ detail: 'The rubric changed' }) });
  try { await assert.rejects(api.saveQuestionTopic(exam, '01', 'SQL'), /rubric changed/); }
  finally { globalThis.fetch = originalFetch; }
});

test('question detail request keeps the complete exam identity and encodes path values', async () => {
  assert.equal(typeof api.fetchQuestionDetail, 'function');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    const request = new URL(url);
    assert.equal(request.pathname, '/api/lecturers/exams/IT%2F2040/Final%20Examination/questions/01');
    assert.equal(request.search, '?year=2022&month=7&semester=1');
    return { ok: true, json: async () => ({ question_no: '01', responses: [] }) };
  };
  try {
    assert.deepEqual(await api.fetchQuestionDetail(exam, '01'), { question_no: '01', responses: [] });
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('question detail surfaces API errors to the popup', async () => {
  assert.equal(typeof api.fetchQuestionDetail, 'function');
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, status: 404, json: async () => ({ detail: 'Question not found' }) });
  try {
    await assert.rejects(api.fetchQuestionDetail(exam, '99'), /Question not found/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

const modalSource = readFileSync(new URL('../src/app/components/analytics/QuestionDetailModal.tsx', import.meta.url), 'utf8');
const modalCode = transformSync(modalSource, { loader: 'tsx', format: 'cjs' }).code;
const detail = {
  question_no: '01', question_text: 'Explain normalization.', max_marks: 10,
  mark_distribution: [{ marks: 5, count: 1 }], excluded_count: 0,
  responses: [
    { student_id: 'S1', score: 5, answer_excerpt: 'A saved <answer>', slice_source: 'split', feedback: 'Add an example.' },
    { student_id: 'S2', score: 0, answer_excerpt: null, slice_source: null, feedback: null },
    { student_id: 'S3', score: 10, answer_excerpt: 'Whole paper', slice_source: 'full', feedback: null },
    { student_id: 'S4', score: 5, answer_excerpt: 'Recovered answer', slice_source: 'ocr', feedback: null },
  ],
};

function popup(fetchDetail, saveTopic = async () => ({}), onTopicSaved = () => {}) {
  const states = [];
  let index = 0;
  let effectDeps;
  let cleanup;
  let pendingEffect;
  const clicks = new Map();
  let chooseTopic;
  const hooks = {
    ...React,
    useState(initial) {
      const slot = index++;
      if (!(slot in states)) states[slot] = initial;
      return [states[slot], (value) => { states[slot] = typeof value === 'function' ? value(states[slot]) : value; }];
    },
    useRef(initial) {
      const slot = index++;
      if (!(slot in states)) states[slot] = { current: initial };
      return states[slot];
    },
    useEffect(effect, deps) {
      if (JSON.stringify(deps) !== effectDeps) {
        cleanup?.();
        effectDeps = JSON.stringify(deps);
        pendingEffect = effect;
      }
    },
  };
  const childrenOnly = ({ children }) => React.createElement('div', null, children);
  const button = ({ children, onClick, disabled }) => {
    clicks.set(React.Children.toArray(children).filter(c => typeof c === 'string').join(''), onClick);
    return React.createElement('button', { disabled, onClick }, children);
  };
  const module = { exports: {} };
  vm.runInNewContext(modalCode, {
    module, exports: module.exports, Error,
    require(name) {
      if (name === 'react') return hooks;
      if (name.includes('lecturerApi')) return { fetchQuestionDetail: fetchDetail, saveQuestionTopic: saveTopic };
      if (name.includes('/select')) return new Proxy({}, { get: (_, name) => name === 'Select' ? ({ children, onValueChange }) => {
        chooseTopic = onValueChange;
        return React.createElement('div', null, children);
      } : childrenOnly });
      if (name.includes('/button')) return { Button: button };
      return new Proxy({}, { get: () => childrenOnly });
    },
  });
  return {
    render(number = '01') {
      index = 0;
      clicks.clear();
      const tree = module.exports.QuestionDetailModal({
        question: { question_id: `Q${number}`, question_no: number, topic: 'DBMS', bloom_level: 'Understand', average_percentage: 50 },
        exam, open: true, onClose() {}, onTopicSaved,
      });
      const html = renderToStaticMarkup(tree);
      if (pendingEffect) { const effect = pendingEffect; pendingEffect = null; cleanup = effect(); }
      return html;
    },
    click(label) { assert.equal(typeof clicks.get(label), 'function'); return clicks.get(label)(); },
    chooseTopic(value) { assert.equal(typeof chooseTopic, 'function'); chooseTopic(value); },
  };
}

test('lecturer can save a question topic and request refreshed analytics', async () => {
  const writes = [];
  let refreshes = 0;
  const view = popup(async () => ({ ...detail, approved_topic: null, topic_options: ['Schema Refinement'] }),
    async (...args) => writes.push(args), () => refreshes++);
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  view.render();
  view.chooseTopic('Schema Refinement');
  view.render();
  await view.click('Save & Reanalyse');
  assert.equal(writes.length, 1);
  assert.equal(writes[0][1], '01');
  assert.equal(writes[0][2], 'Schema Refinement');
  assert.equal(refreshes, 1);
});

test('failed topic save keeps the popup open and does not request reanalysis', async () => {
  let refreshes = 0;
  const view = popup(async () => ({ ...detail, approved_topic: null, topic_options: ['Schema Refinement'] }),
    async () => { throw new Error('The rubric changed'); }, () => refreshes++);
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  view.render();
  view.chooseTopic('Schema Refinement');
  view.render();
  await view.click('Save & Reanalyse');
  assert.match(view.render(), /The rubric changed/);
  assert.equal(refreshes, 0);
});

test('late topic save cannot refresh a different question or exam', async () => {
  let resolveSave;
  let refreshes = 0;
  const view = popup(async () => ({ ...detail, topic_options: ['Schema Refinement'] }),
    () => new Promise(resolve => { resolveSave = resolve; }), () => refreshes++);
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  view.render();
  view.chooseTopic('Schema Refinement');
  view.render();
  const saving = view.click('Save & Reanalyse');
  view.render('02');
  resolveSave({});
  await saving;
  assert.equal(refreshes, 0);
});

test('popup opens each evidence view and labels missing and full-paper excerpts', async () => {
  const view = popup(async () => detail);
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  assert.doesNotMatch(view.render(), /<button disabled="">(?:<div><\/div>)?View /);
  view.click('View Question Text');
  assert.match(view.render(), /Explain normalization\./);
  view.click('View Student Responses');
  const responses = view.render();
  assert.match(responses, /A saved &lt;answer&gt;/);
  assert.match(responses, /No saved answer excerpt/);
  assert.match(responses, /Full-paper excerpt/);
  assert.match(responses, /Extracted from the saved OCR transcript/);
  assert.match(responses, /Recovered answer/);
  view.click('View Mark Distribution');
  assert.match(view.render(), /Mark Distribution/);
});

test('late response from a previous question cannot replace the current question', async () => {
  const pending = [];
  const view = popup(() => new Promise(resolve => pending.push(resolve)));
  view.render('01');
  view.render('02');
  pending[1]({ ...detail, question_no: '02', question_text: 'Current question' });
  await new Promise(resolve => setImmediate(resolve));
  view.render('02');
  view.click('View Question Text');
  pending[0](detail);
  await new Promise(resolve => setImmediate(resolve));
  const html = view.render('02');
  assert.match(html, /Current question/);
  assert.doesNotMatch(html, /Explain normalization/);
});

test('failed evidence load can be retried and enables the views after success', async () => {
  let attempts = 0;
  const view = popup(async () => {
    if (++attempts === 1) throw new Error('Question service unavailable');
    return detail;
  });
  assert.match(view.render(), /Loading question evidence/);
  await new Promise(resolve => setImmediate(resolve));
  assert.match(view.render(), /Question service unavailable/);
  view.click('Retry');
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  assert.doesNotMatch(view.render(), /<button disabled="">(?:<div><\/div>)?View |Question service unavailable/);
  view.click('View Question Text');
  assert.match(view.render(), /Explain normalization/);
});

test('empty question evidence displays useful empty states for all three views', async () => {
  const view = popup(async () => ({ ...detail, question_text: null, responses: [], mark_distribution: [] }));
  view.render();
  await new Promise(resolve => setImmediate(resolve));
  view.render();
  for (const [label, message] of [
    ['View Question Text', /No saved question text/],
    ['View Mark Distribution', /No graded marks/],
    ['View Student Responses', /No graded responses/],
  ]) {
    view.click(label);
    assert.match(view.render(), message);
  }
});
