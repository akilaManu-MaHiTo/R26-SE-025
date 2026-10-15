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

## Recommendations and generated practice bound to evidence

The next user-authorized change fixes recommendation audit cases R1–R4 and the associated student-insight overwrite/persistence paths.

- `student_pipeline.py` retains the backend's structured topic/criterion learning gaps, priorities and practice strategy. It accepts AI action text only for an eligible assessed topic and its observed, non-full-mark Bloom pair. Unsupported advice causes the deterministic fallback to be used. Every saved recommendation includes supporting question IDs and earned/available marks in its action text. Unclassified or already-Strong topics do not produce personal practice targets. Backend learning gaps are retained even when they concern an Unclassified question, so missing mapping remains visible rather than being assigned a fabricated topic.
- `student_document.py` supplies question IDs, Bloom levels and actual criterion marks in lost-criterion evidence. Its fallback recommendations now choose a Bloom level from that topic's own questions, rather than the globally lowest Bloom result from another topic. The existing practice difficulty/level strategy remains a heuristic, not a validated mastery estimator.
- `generate_practice.py::practice_batch_matches_target` checks the requested count, exact topic/level/difficulty membership and prompt uniqueness after case/whitespace normalization. `llm_service.py` also checks the model's reported requested count. Invalid batches return degraded/target_mismatch; empty targets return degraded/insufficient_evidence without an LLM call. The persistence service repeats validation before saving, and the existing API error path returns503 rather than accepting a bad batch.
- `recommendation.py` uses finite observed topic percentages and the existing configured coverage minima (10 students/2 distinct questions), rejects missing/invalid coverage and explicit insufficient-evidence statuses, and excludes unassessed/Strong topics. Question IDs and normalized duplicate texts are not ranked twice. Reasons include the observed percentage and observed_performance basis. This introduces no new scoring weights or mastery thresholds.
- The exam creator legitimately builds curriculum-balanced papers without student results. Its existing caller explicitly requests `require_evidence=False`; those candidates are labelled curriculum_coverage, and existing blueprint/mark-allocation behavior is retained. The lecturer practice recommendation path uses the evidence-required default.
- Student analytics and generated practice are version1.1. Legacy student analytics are rebuilt lazily from original graded submissions before reuse. A cached practice batch must have the current generation version, match the current backend target and pass batch validation. Old batches remain stored until replaced, but are not returned as validated current practice. Rebuild/generation may be unavailable when original data or model services are unavailable; no old advice is silently promoted to validated evidence.

Regression evidence: the initial new file produced20 failures/1 pass before fixes; a later independent case reproduced the fallback's incorrect cross-topic Bloom choice. The repaired audit markers R1–R4 are ordinary passing regressions now. Existing tests that expected AI to overwrite backend gaps/targets were updated to assert the new evidence-preserving contract. Valid practice/cache fixtures contain five distinct questions with complete targeting. A mocked exam-creator endpoint test now overrides its unused database dependency, preventing an unintended real connection.

Final affected-file verification, with dotenv loading disabled and database/external HTTP transports blocked: `pytest --noconftest tests/test_student_pipeline.py tests/test_student_dashboard_service.py tests/test_practice_questions.py tests/test_llm_student_analysis.py tests/test_recommendation_evidence.py tests/test_student_document_analytics.py tests/test_exam_creator.py -q --tb=short` returned **109 passed in1.03s**, exit0. This async run used an approved process outside the Windows sandbox, where the event loop can initialize. [Saved output](audit_evidence/recommendation_async_results.txt).

The broader sandboxed `scripts/run_audit_tests.py` selection returned **151 passed, 1 failed, 18 skipped, 13 strict expected failures**, exit1. [Saved output](audit_evidence/recommendation_fix_results.txt). Its sole ordinary failure remains the pre-existing list-shaped rubric fixture in `test_normalize_submission_joins_questions_and_criteria`. This selection still skips async/temp fixtures; the affected async paths were separately exercised by the passing109-test run. The remaining expected failures are other audit findings.

No live database, model inference, retraining or annotation changes were performed. These checks validate evidence linkage and generated metadata/counts; they do not establish semantic relevance, answerability, cognitive-demand correctness or learning gains. Duplicate detection is case/whitespace based, not semantic similarity. Lecturer review of generated question content is still needed, and general evidence-fingerprint cache freshness remains outside this version migration.


## Evaluation metrics and independent Bloom holdout preparation

The user authorized repairs for EQ-06, EQ-07 and EQ-11, then supplied the local
`datasets/bloom_dataset/Final exam` directory as a possible holdout source.

- `app/evaluation/metrics.py`: NDCG builds its ideal ranking from the complete
  supplied relevance list before truncating to k; zero cutoff returns zero and
  negative cutoff raises ValueError. Accuracy, confusion matrix, macro F1 and
  Cohen kappa reject unequal paired lengths. Confusion matrices reject duplicate
  classes and classes missing observed labels rather than dropping observations.
  Valid-input formulas, empty-set conventions and the existing unanimous-rater
  kappa convention remain unchanged. All three baseline probes now run normally.
- `scripts/evaluate_bloom_holdout.py` validates external question text, recorded
  independent rater IDs/labels, adjudication, provenance fields, duplicate IDs/text
  and normalized overlap with the complete confirmed training source plus supplied
  tuning pools. Validation precedes any model import/inference. Optional local
  frozen-model evaluation emits hashes, predictions, accuracy, six-class macro F1,
  per-class precision/recall/F1/support and confusion matrix JSON. No model fallback,
  retraining or dependency was added.
- `final_exam_holdout_candidates.csv` contains 14 unlabeled text-question candidates
  from the supplied 2022/2023 papers. Selected pages were rendered and checked;
  contextual schema/FD questions retain context and explicit primary keys. No
  normalized exact training-source overlap was found. Source/candidate hashes and
  limitations are saved in `audit_evidence/final_exam_holdout_preparation.json`.
  Narrow ignore exceptions keep only the two review CSVs visible to Git.
- [Holdout instructions](BLOOM_HOLDOUT.md) explain the pending lecturer annotation,
  historical non-use confirmation, semantic overlap review and class/family
  coverage checks. The pilot is not an independent gold set. Diagram questions,
  unreliable scan/code extraction and the apparent 2024-filename/2018-cover mismatch
  remain for human review. Long schema inputs may reach runtime truncation limits.

Before the metric fix, 17 new regressions failed; afterward they passed. Holdout
validation tests initially failed because the validation feature was absent.
Final focused command (`--noconftest`, evaluation/holdout/evidence tests, excluding
only the existing temporary-path labeling-template test) returned **43 passed,
1 deselected**. CLI tests confirm blank/unlabeled sheets fail before model loading;
a model-boundary stub checks the successful evaluation/reporting path with real
hand-calculated metrics, not model accuracy.

Final `scripts/run_audit_tests.py`: **189 passed, 1 failed, 18 skipped, 10 strict
expected failures**, exit1. [Saved output](audit_evidence/metrics_holdout_results.txt).
The ordinary failure remains `test_normalize_submission_joins_questions_and_criteria`
(list-shaped rubric fixture passed to a dictionary normalizer). The selection
blocks external HTTP/database connections and skips Windows async/temp fixtures;
the entire integration suite was not run because its DB fixture can drop a database.
Both staged and unstaged `git diff --check` passed.

No real model inference, retraining, live database operation or lecturer labeling
was performed. Independent Bloom accuracy remains unmeasured pending human labels
and provenance review; exact overlap checks cannot detect all paraphrases or prior
use. Existing reports/results are preserved as historical baseline evidence.
