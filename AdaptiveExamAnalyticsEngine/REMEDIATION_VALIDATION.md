# Diagram denominators and assessment coverage fixes

2026-10-15. Implements the user's follow-up to audit findings EQ-01, EQ-02, EQ-03 and EQ-09. The original audit reports/results remain baseline evidence; this document records the subsequent changes. Models, labels, training data and unrelated audit defects are unchanged.

## Changes

- `app/analytics/diagram_analysis.py`: student pass decisions use that student's maximum. Scores6/10 and60/100 now produce100% passing. Zero maximum uses the existing zero-performance convention without division by zero; this convention does not establish observed knowledge.
- Criterion percentages use the saved criterion's authoritative `max_marks`, summing earned/available marks across responses. Two students at2/5 yield40%. If any participating response lacks a finite positive criterion maximum, `max_marks` and percentage are null instead of inferred from the highest award. For varying maxima, the displayed Max is mean available marks, matching Avg awarded, while percentage uses total earned/available marks.
- `app/analytics/exam_analytics.py`: topic `attempt_count` counts question-response rows; new `question_count` counts distinct assessed question numbers. Topic and topic×Bloom evidence gates use distinct question coverage with the existing configured minimum2 and minimum10 students. Ten responses to one question remain insufficient; twenty responses across two questions can meet that coverage gate. This is still a policy threshold, not proof of persistent weakness.
- Insights describe distinct questions, not student-topic rows. Pydantic/API schemas preserve the new counts and nullable criterion values. Dashboard criteria show N/A when the denominator is unavailable, and heatmap tooltips separate students, responses and distinct questions.
- Exam analytics version1.1 replaces1.0. The existing cache completeness check requires the shared current version, so old snapshots are eligible for lazy rebuilding on the next lecturer analytics request. Rebuild failure retains the existing last-good fallback behavior; existing persisted snapshots were not directly edited.

## Verification

Before implementation, all four relevant baseline probes failed with `--runxfail`: pass rate50 instead of100, division by zero, criterion100 instead of40, and confirmed weakness from one question. Six new cases also failed before implementation, covering missing maxima, unequal criterion maxima, response/question separation, missing question records and duplicate question IDs. A seventh new cache test failed because version1.0 was still accepted before the version bump.

After the arithmetic/schema fixes, focused tests (`test_assessment_evidence_counts.py`, `test_independent_equation_audit.py`, `test_exam_analytics.py`, `test_exam_analytics_additional.py`) returned38 passed/11 expected failures. The subsequent cache test is included in the final offline selection.

Final command: `.\.venv\Scripts\python.exe scripts/run_audit_tests.py`. Result: **100 passed, 1 failed, 12 skipped, 17 strict expected failures**, exit1. [Saved output](audit_evidence/remediation_test_results.txt). The ordinary failure remains `test_normalize_submission_joins_questions_and_criteria`: the existing fixture passes a list-shaped rubric to a dictionary normalizer. The remaining expected failures are unrelated audit findings, and the skips are Windows async/temp-fixture limitations. Four repaired audit probes now run as ordinary passing regressions.

Frontend `npm run build` passed (3048 modules). Its first sandboxed attempt failed on Vite realpath permission; the approved build outside the sandbox succeeded. Existing npm config/dynamic-import/chunk-size warnings remain. No dependency was added and no rendered browser test was performed.

Live databases, deployed endpoints, model inference and cache rebuilding were not executed. Fresh or successfully rebuilt analytics use these corrections; previously saved results can remain visible if their rebuild fails. Diagram records missing criterion maxima display N/A rather than a guessed percentage.

## Lecturer home values and student request races

The user subsequently authorized fixes for DASH-02 and DASH-08.

- `Gradex_AI_Client/src/app/components/LecturerDashboard.tsx` now loads the existing exam-list API and shows returned exam and analyzed-exam counts, labelled as listed exams rather than unique students or graded papers. Loading, an empty response and a failed request are distinct states. Grading time, throughput and activity explicitly show unavailable states; class average directs the lecturer to select an exam. Hardcoded queue sizes, trends, risk alerts, activity records, lecturer identity and date were removed. No new backend metrics or speculative aggregate class average were introduced.
- `AnalyticsPage.tsx` gives each student load its own request identity. New student selections, exam changes, leaving student detail and component unmount invalidate obsolete requests. All asynchronous success/error/progress/fallback/health/timer paths check that identity before updating the display or its notifications. The render also checks the selected student and full course/session/year/month/semester URL identity, hiding old content/errors before the new request begins. Changing exams clears open topic/question dialogs.
- Existing saved-detail behavior, pending-student stream/fetch fallback, model errors and progress notifications are retained for the current request. Obsolete network requests may finish on the server; their client results and notifications are ignored.

Before these changes, the two new home-page cases and five initial race cases failed: fabricated values, A overwriting B, obsolete errors/loading completion, stale stream progress/fallback, old notification timers, and the same student across different exam years. Additional checks cover pending-stream late success, obsolete model-health failures and immediate URL selection changes.

From `Gradex_AI_Client`, `node --test --test-reporter=spec` ran the full existing frontend test discovery: **25 passed, 0 failed, 0 skipped**. The tests execute the actual transpiled page/handler code with controlled API promises and hook/render fixtures, following the repository's Node/esbuild test convention. `npm run build` also passed:3048 modules,21.61s, with existing npm configuration, dynamic-import and large-chunk warnings. No dependencies were added; live databases, browser rendering and backend model services were not exercised in this follow-up. Backend authentication and evidence-aware cache freshness remain separate audit findings.
