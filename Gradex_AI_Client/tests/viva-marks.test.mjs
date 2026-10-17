import assert from 'node:assert/strict';
import test, { afterEach } from 'node:test';
import { loadApi } from './load-api.mjs';

const api = await loadApi('./viva-marks-entry.ts');

// Every test starts and ends on the default scale, so a scale a test sets never leaks.
afterEach(() => api.setMarkingScale(api.DEFAULT_MARKING_SCALE));

const useScale = (markMax, technicalMax = markMax, decimals = 2) =>
  api.setMarkingScale(api.buildMarkingScale(markMax, technicalMax, decimals));

// ----------------------------------------------------------------- default scale (out of 20)

test('the default scale is out of 20', () => {
  const scale = api.getMarkingScale();
  assert.equal(scale.markMax, 20);
  assert.equal(scale.technicalMax, 20);
  assert.equal(scale.decimals, 2);
});

test('percentToMark scales a 0-100 percentage to the mark (2 decimals)', () => {
  assert.equal(api.percentToMark(100), 20);
  assert.equal(api.percentToMark(0), 0);
  // The same values the engine tests pin (marking_scale.percent_to_mark).
  assert.equal(api.percentToMark(69.44), 13.89);
  assert.equal(api.percentToMark(79.06), 15.81);
  assert.equal(api.percentToMark(150), 20);
  assert.equal(api.percentToMark(null), null);
});

test('formatOfficialMark shows the mark the same way everywhere', () => {
  assert.equal(api.formatOfficialMark(15.81), '15.81 / 20');
  assert.equal(api.formatOfficialMark(14), '14.00 / 20');
  assert.equal(api.formatOfficialMark(null), '—');
  assert.equal(api.formatMarkValue(15.8), '15.80');
});

test('grade bands match the engine', () => {
  const cases = {
    20: 'A+', 18: 'A+', 17.99: 'A', 16: 'A', 15.99: 'B+', 14: 'B+',
    13.99: 'B', 12: 'B', 11.99: 'C+', 10: 'C+', 9.99: 'C', 8: 'C', 7.99: 'F', 0: 'F',
  };
  for (const [mark, grade] of Object.entries(cases)) {
    assert.equal(api.resolveGradeFromMark(Number(mark)), grade, `mark ${mark}`);
  }
  assert.equal(api.resolveGradeFromMark(null), null);
});

test('the grade follows the rounded, displayed mark', () => {
  const mark = api.percentToMark(69.98); // 13.996 -> 14.00
  assert.equal(mark, 14);
  assert.equal(api.resolveGradeFromMark(mark), 'B+');
});

test('the technical preview matches the server arithmetic', () => {
  const weights = { weightAi: 0.5, weightTechnical: 0.5 };
  // AI 68.11% with technical 18/20 (90%): 0.5*68.11 + 0.5*90 = 79.055% -> 15.81 / 20.
  assert.equal(api.fusePreviewMark(68.11, 18, weights), 15.81);
  assert.equal(api.fusePreviewMark(60, 16, weights), 14); // 70% -> 14.00
  assert.equal(api.fusePreviewMark(60, 0, weights), 6);
  assert.equal(api.fusePreviewMark(60, 20, weights), 16);
});

// ----------------------------------------------------------------- the scale is configuration

test('every helper follows the configured mark scale', () => {
  for (const markMax of [25, 30, 100]) {
    useScale(markMax);
    assert.equal(api.percentToMark(75), (75 / 100) * markMax, `scale ${markMax}`);
    assert.equal(api.formatOfficialMark(api.percentToMark(75)), `${((75 / 100) * markMax).toFixed(2)} / ${markMax}`);
  }
});

test('the same percentage gets the same grade on any scale', () => {
  const percents = [0, 39.9, 40, 49.9, 50, 59.9, 60, 69.9, 70, 79.9, 80, 89.9, 90, 100];
  for (const percent of percents) {
    const letters = new Set();
    for (const markMax of [20, 25, 30, 100]) {
      useScale(markMax);
      letters.add(api.resolveGradeFromMark(api.percentToMark(percent)));
    }
    assert.equal(letters.size, 1, `percent ${percent} graded differently: ${[...letters]}`);
  }
});

test('grade band minimums are derived from the percentages', () => {
  useScale(30);
  const bands = api.getMarkingScale().gradeBands;
  assert.deepEqual(bands[0], { grade: 'A+', minPercent: 90, minMark: 27 });
  assert.equal(bands.find((b) => b.grade === 'B').minMark, 18);
  assert.equal(bands.at(-1).minMark, 0);
});

test('the technical preview uses the technical maximum', () => {
  useScale(30, 10);
  const weights = { weightAi: 0.5, weightTechnical: 0.5 };
  // Technical 8/10 is 80%; AI 60% -> 0.5*60 + 0.5*80 = 70% -> 21 / 30.
  assert.equal(api.fusePreviewMark(60, 8, weights), 21);
});

test('decimals are configurable', () => {
  useScale(20, 20, 0);
  assert.equal(api.percentToMark(69.44), 14);
  assert.equal(api.formatOfficialMark(14), '14 / 20');
  useScale(20, 20, 1);
  assert.equal(api.percentToMark(69.44), 13.9);
});

test('resolveOfficialMark follows the configured scale', () => {
  useScale(30);
  const r = api.resolveOfficialMark({
    assessment: {
      status: 'VALID',
      ai_performance: { score: 80 },
      fusion: { with_technical: { weight_ai: 0.5, weight_technical: 0.5 } },
    },
    analysisResult: { final_score: 80, final_mark: 24, final_grade: 'A' },
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: true,
  });
  assert.equal(r.finalMark, 24);
  assert.equal(r.grade, 'A');
});

test('the AI technical suggestion is scaled to the technical maximum, including older 0-10 results', () => {
  assert.equal(api.suggestedTechnicalMark({ overall_mark: 17.5, overall_score: 8.75 }), 17.5);
  assert.equal(api.suggestedTechnicalMark({ overall_score: 8.75 }), 17.5); // default scale, analysed before
  useScale(30);
  assert.equal(api.suggestedTechnicalMark({ overall_score: 8 }), 24); // 8/10 of 30
  assert.equal(api.suggestedTechnicalMark({ overall_score: null }), null);
  assert.equal(api.suggestedTechnicalMark(undefined), null);
});

// ----------------------------------------------------------------- the server payload

test('parseMarkingScale accepts the server payload', () => {
  const scale = api.parseMarkingScale({
    mark_max: 30,
    technical_max: 30,
    decimals: 2,
    grade_bands: [
      { grade: 'A+', min_percent: 90, min_mark: 27 },
      { grade: 'F', min_percent: 0, min_mark: 0 },
    ],
  });
  assert.equal(scale.markMax, 30);
  assert.deepEqual(scale.gradeBands[0], { grade: 'A+', minPercent: 90, minMark: 27 });
});

test('parseMarkingScale rejects an unusable payload', () => {
  const good = { mark_max: 20, technical_max: 20, decimals: 2, grade_bands: [{ grade: 'F', min_percent: 0, min_mark: 0 }] };
  assert.ok(api.parseMarkingScale(good));
  for (const bad of [
    null,
    'x',
    { ...good, mark_max: 0 },
    { ...good, technical_max: -1 },
    { ...good, decimals: 1.5 },
    { ...good, grade_bands: [] },
    { ...good, grade_bands: [{ grade: 'A', min_percent: 'x', min_mark: 1 }] },
  ]) {
    assert.equal(api.parseMarkingScale(bad), null, JSON.stringify(bad));
  }
});

test('subscribers hear about a new scale', () => {
  let heard = 0;
  const unsubscribe = api.subscribeMarkingScale(() => heard++);
  useScale(30);
  assert.equal(heard, 1);
  unsubscribe();
  useScale(25);
  assert.equal(heard, 1);
});

// ----------------------------------------------------------------- resolveOfficialMark (default scale)

const assessment = (overrides = {}) => ({
  status: 'VALID',
  ai_performance: { score: 68.11, mark: 13.62 },
  fusion: { weight_ai: 1, weight_technical: 0, with_technical: { weight_ai: 0.5, weight_technical: 0.5 } },
  ...overrides,
});

test('resolveOfficialMark: incomplete analyses have no mark', () => {
  const r = api.resolveOfficialMark({
    assessment: assessment({ status: 'INCOMPLETE' }),
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: false,
  });
  assert.deepEqual(r, { finalMark: null, markMax: 20, grade: null, isPreview: false });
});

test('resolveOfficialMark: a non-technical viva uses the server mark and grade', () => {
  const r = api.resolveOfficialMark({
    assessment: assessment(),
    analysisResult: { final_score: 68.11, final_mark: 13.62, final_grade: 'B' },
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: true,
  });
  assert.equal(r.finalMark, 13.62);
  assert.equal(r.grade, 'B');
  assert.equal(r.isPreview, false);
});

test('resolveOfficialMark: falls back to scaling the percentage when the server sent no mark', () => {
  const r = api.resolveOfficialMark({
    assessment: assessment(),
    analysisResult: { final_score: 79.06, final_mark: null, final_grade: null },
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: true,
  });
  assert.equal(r.finalMark, 15.81);
  assert.equal(r.grade, 'B+');
});

test('resolveOfficialMark: a technical draft previews live and is not final', () => {
  const none = api.resolveOfficialMark({
    assessment: assessment(),
    assessmentMode: 'WITH_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: false,
  });
  assert.equal(none.finalMark, null);

  const r = api.resolveOfficialMark({
    assessment: assessment(),
    // The auto-saved percentage must not be mistaken for a published technical mark.
    analysisResult: { final_score: 68.11, final_mark: 13.62, final_grade: 'B' },
    assessmentMode: 'WITH_TECHNICAL_ACCURACY',
    technicalAccuracy: 18,
    published: false,
  });
  assert.equal(r.finalMark, 15.81);
  assert.equal(r.grade, 'B+');
  assert.equal(r.isPreview, true);
});

test('resolveOfficialMark: once a technical mark is published the server mark wins', () => {
  const r = api.resolveOfficialMark({
    assessment: assessment(),
    analysisResult: { final_score: 79.06, final_mark: 15.81, final_grade: 'B+' },
    assessmentMode: 'WITH_TECHNICAL_ACCURACY',
    technicalAccuracy: 18,
    published: true,
  });
  assert.equal(r.finalMark, 15.81);
  assert.equal(r.isPreview, false);
});

// ----------------------------------------------------------------- explainer text

test('the explainers describe the official mark on the configured scale', () => {
  const grade = api.buildScoreExplain('grade', {});
  const gradeText = [grade.summary, ...(grade.lines ?? [])].join(' | ');
  assert.match(gradeText, /out of 20/);
  assert.match(gradeText, /A\+ ≥ 18/);
  assert.match(gradeText, /F < 8/);
  assert.doesNotMatch(gradeText, /≥ 90\b/);

  useScale(30);
  const gradeAt30 = api.buildScoreExplain('grade', {});
  const textAt30 = [gradeAt30.summary, ...(gradeAt30.lines ?? [])].join(' | ');
  assert.match(textAt30, /out of 30/);
  assert.match(textAt30, /A\+ ≥ 27/);
  assert.doesNotMatch(textAt30, /out of 20/);
});

test('the worked example for a technical mark follows the scale', () => {
  const build = () =>
    api.buildScoreExplain('official_mark', {
      assessment: assessment({
        assessment_mode: 'WITH_TECHNICAL_ACCURACY',
        technical_accuracy: 18,
        scoring_version: 'v1.3',
        ai_performance: {
          score: 68.11,
          mark: 13.62,
          family_scores: { engagement: 0.6811, audio_acoustics: 0.6811, transcript: 0.6811 },
          family_weights_applied: { engagement: 0.3333, audio_acoustics: 0.3333, transcript: 0.3334 },
        },
      }),
      assessmentMode: 'WITH_TECHNICAL_ACCURACY',
    });
  const text = (content) =>
    [content.summary, content.formula, ...(content.lines ?? []), ...(content.workedExample ?? [])].join(' | ');

  const at20 = text(build());
  assert.match(at20, /out of 20/);
  assert.match(at20, /15\.81 \/ 20/); // 0.5 * 13.62 + 0.5 * 18
  assert.doesNotMatch(at20, /\/ 100/);

  useScale(30);
  const at30 = text(build());
  assert.match(at30, /out of 30/);
  assert.doesNotMatch(at30, /\/ 20/);
});

// ----------------------------------------------------------------- marks keep the scale they were given on

test('a saved mark keeps its own scale after the scale is changed', () => {
  useScale(30); // the scale was changed after this mark was given out of 20
  assert.equal(api.formatOfficialMark(13.89, 20), '13.89 / 20');
  assert.equal(api.formatOfficialMark(13.89), '13.89 / 30'); // an unsaved value uses the current scale

  const saved = api.resolveOfficialMark({
    assessment: { status: 'VALID', ai_performance: { score: 69.44 } },
    analysisResult: { final_score: 69.44, final_mark: 13.89, final_mark_max: 20, final_grade: 'B' },
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: true,
  });
  assert.equal(saved.finalMark, 13.89);
  assert.equal(saved.markMax, 20);
  assert.equal(saved.grade, 'B');
});

test('a mark with only a percentage is shown on the current scale', () => {
  useScale(30);
  const legacy = api.resolveOfficialMark({
    assessment: { status: 'VALID', ai_performance: { score: 80 } },
    analysisResult: { final_score: 80, final_mark: null, final_grade: null },
    assessmentMode: 'WITHOUT_TECHNICAL_ACCURACY',
    technicalAccuracy: null,
    published: true,
  });
  assert.equal(legacy.finalMark, 24); // 80% of 30
  assert.equal(legacy.markMax, 30);
});

test('a technical preview is estimated on the current scale', () => {
  useScale(25);
  const preview = api.resolveOfficialMark({
    assessment: {
      status: 'VALID',
      ai_performance: { score: 60 },
      fusion: { with_technical: { weight_ai: 0.5, weight_technical: 0.5 } },
    },
    assessmentMode: 'WITH_TECHNICAL_ACCURACY',
    technicalAccuracy: 20, // 80% of 25
    published: false,
  });
  assert.equal(preview.finalMark, 17.5); // 70% of 25
  assert.equal(preview.markMax, 25);
  assert.equal(preview.isPreview, true);
});
