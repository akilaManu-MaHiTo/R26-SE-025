import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { transformSync } from 'esbuild';
import { loadApi } from './load-api.mjs';

const api = await loadApi('../src/app/api/lecturerApi.ts');
const exam = { course_code: 'IT/2040', session_name: 'Final Exam', year: 2026, month: 7, semester: 1 };

test('answer evidence uses encoded student and question paths with the full exam identity', async () => {
  assert.equal(typeof api.fetchStudentAnswerEvidence, 'function');
  const original = globalThis.fetch;
  globalThis.fetch = async url => {
    const request = new URL(url);
    assert.equal(request.pathname, '/api/lecturers/exams/IT%2F2040/Final%20Exam/student/S%2F1/questions/01');
    assert.equal(request.search, '?year=2026&month=7&semester=1');
    return { ok: true, json: async () => ({ answer_excerpt: 'Student answer' }) };
  };
  try { assert.equal((await api.fetchStudentAnswerEvidence(exam, 'S/1', '01')).answer_excerpt, 'Student answer'); }
  finally { globalThis.fetch = original; }
});

test('answer evidence reports lookup failures instead of claiming an empty answer', async () => {
  assert.equal(typeof api.fetchStudentAnswerEvidence, 'function');
  const original = globalThis.fetch;
  globalThis.fetch = async () => ({ ok: false, json: async () => ({ detail: 'No saved evidence for this exam' }) });
  try { await assert.rejects(api.fetchStudentAnswerEvidence(exam, 'S1', '01'), /No saved evidence/); }
  finally { globalThis.fetch = original; }
});

const question = {
  question_id: 'Q1', question_no: '01', question_text: 'Explain normalisation.', topic: 'Normalisation', subtopic: '3NF',
  bloom_analysis: { level: 'Understand' }, performance: { score: 4, max_score: 10, percentage: 40 },
  criteria_performance: [{ criterion: 'Explain dependency', awarded_marks: 4, max_marks: 10, achieved: false }],
};

function renderRow(evidence, { open = true, error = null } = {}) {
  const source = readFileSync(new URL('../src/app/components/analytics/StudentQuestionRow.tsx', import.meta.url), 'utf8');
  const module = { exports: {} };
  let index = 0;
  const states = [open, evidence, error, 0];
  const stub = ({ children }) => React.createElement('div', null, children);
  vm.runInNewContext(transformSync(source, { loader: 'tsx', format: 'cjs' }).code, {
    module, exports: module.exports,
    require(name) {
      if (name === 'react') return { ...React, useState: () => [states[index++], () => {}], useEffect() {} };
      return new Proxy({}, { get: (_, key) => key === 'Button'
        ? ({ children, ...props }) => React.createElement('button', props, children) : stub });
    },
  });
  return renderToStaticMarkup(React.createElement(module.exports.StudentQuestionRow, { question, exam, studentId: 'S1' }));
}

test('expanded question shows answer evidence beside rubric marks and grading reasons', () => {
  const html = renderRow({ answer_excerpt: '<script>student text</script>', slice_source: 'regex', feedback: 'Missing example',
    justification: 'Partial credit', criteria_breakdown: [{ point: 'Explain dependency', awarded_marks: 4, reason: 'Incomplete explanation' }] });
  assert.match(html, /Explain normalisation/);
  assert.match(html, /&lt;script&gt;student text&lt;\/script&gt;/);
  assert.match(html, /Missing example/);
  assert.match(html, /Partial credit/);
  assert.match(html, /Incomplete explanation/);
  assert.match(html, /4 \/ 10/);
  assert.match(html, /excerpt/i);
  assert.match(html, /aria-expanded="true"/);
});

test('missing extracted text never claims that the student submitted no answer', () => {
  const html = renderRow({ answer_excerpt: null, slice_source: 'empty', criteria_breakdown: [] });
  assert.match(html, /No answer text was extracted/);
  assert.doesNotMatch(html, /No answer submitted|Unanswered/);
  assert.match(html, /No saved grading feedback/);
});

test('whole-paper fallback is not presented as a separated question answer', () => {
  const html = renderRow({ answer_excerpt: 'Whole paper text', slice_source: 'full', criteria_breakdown: [] });
  assert.match(html, /Full-paper excerpt/);
  assert.match(html, /did not separate/);
});

test('collapsed questions keep evidence hidden and failures offer retry', () => {
  assert.doesNotMatch(renderRow({ answer_excerpt: 'Hidden answer' }, { open: false }), /Hidden answer|Explain normalisation/);
  const html = renderRow(null, { error: 'Evidence unavailable' });
  assert.match(html, /Evidence unavailable/);
  assert.match(html, /Retry/);
});
