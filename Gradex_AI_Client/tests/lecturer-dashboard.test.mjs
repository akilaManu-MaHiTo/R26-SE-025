import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { transformSync } from 'esbuild';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';

const source = readFileSync(new URL('../src/app/components/LecturerDashboard.tsx', import.meta.url), 'utf8');

function dashboard(fetchExams) {
  const states = [], effects = [];
  let index = 0, mounted = false;
  const stub = ({ children }) => React.createElement('div', null, children);
  const hooks = { ...React,
    useState(initial) {
      const slot = index++;
      if (!(slot in states)) states[slot] = initial;
      return [states[slot], value => { states[slot] = value; }];
    },
    useEffect(effect) { if (!mounted) effects.push(effect); },
  };
  const module = { exports: {} };
  vm.runInNewContext(transformSync(source, { loader: 'tsx', format: 'cjs' }).code, {
    React, module, exports: module.exports,
    require(name) {
      if (name === 'react') return hooks;
      if (name === 'react-router') return { useNavigate: () => () => {} };
      if (name.includes('lecturerApi')) return { fetchExams };
      return new Proxy({}, { get: () => stub });
    },
  });
  return {
    render() {
      index = 0;
      const tree = module.exports.LecturerDashboard();
      const html = renderToStaticMarkup(tree);
      if (!mounted) { mounted = true; for (const effect of effects) effect(); }
      return html;
    },
  };
}

test('home shows API exam counts without invented grading, activity or risk claims', async () => {
  const view = dashboard(async () => [{ analyzed: true }, { analyzed: false }, { analyzed: true }]);
  const loading = view.render();
  assert.match(loading, /Loading/);
  await new Promise(resolve => setImmediate(resolve));
  const html = view.render();
  assert.match(html, />3<.*Exams listed/);
  assert.match(html, />2<.*Analytics available/);
  assert.match(html, /No data available/);
  assert.doesNotMatch(html, /1,284|342|74\.2|Dr\. Mendis|at-risk|CS-2024|pending|\+24%/);
});

test('home distinguishes a failed exam request from an empty exam list', async () => {
  const failed = dashboard(async () => { throw new Error('Offline'); });
  failed.render();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(failed.render(), /Could not load exam summaries/);
  assert.doesNotMatch(failed.render(), />0<.*Exams listed/);
  const empty = dashboard(async () => []);
  empty.render();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(empty.render(), />0<.*Exams listed/);
  assert.match(empty.render(), /No exams available/);
});
