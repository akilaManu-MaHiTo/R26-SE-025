# Adaptive exam analytics audit

Audit date: 2026-10-15 (Asia/Colombo). Baseline HEAD: `b455262cecab6d953fbcc852b6878404749006a2`. Scope is the current working tree, including existing staged changes, rather than HEAD alone.

## Executive verdict

The engine correctly computes several marks-weighted performance summaries, but **the system is not comprehensively validated**. Diagram calculations can materially overstate performance, evidence counts can turn a single assessed question into a “confirmed” weakness, and generated student recommendations can introduce unsupported topics. Current Bloom accuracy on genuinely unseen human-labelled questions is unverified. The dashboard supplies useful descriptive drill-downs, but some headline displays are fabricated and endpoints lack application-level access control.

This audit adds documentation, reproducible evidence and tests only. Production equations, models, labels, datasets, configuration and the existing staging area are unchanged. Defects remain visible as strict expected failures; they have not been silently fixed or relabelled. No live MongoDB, LLM request, model inference/download, retraining or deployment was performed. Credentials were never printed. The final offline runner suppresses dotenv loading and denies database/network transports.

| Required question | Evidence-based answer |
| --- | --- |
| Are equations correct? | Core student/topic/Bloom earned/available-mark percentages are correct for validated, deduplicated records. Diagram pass/criterion denominators are incorrect in demonstrated cases; evidence counts and NDCG also have verified defects. See [equation inventory](EQUATION_VALIDATION.md). |
| Are Bloom classifications empirically valid? | Not established. The user confirmed the sole training-source CSV; independent comparison found it byte-identical to the repository source. Gold-v2 has 500/500 texts in that pool; actual fitting/model-selection split membership is missing. The synthetic pilot has no lecturer gold labels. Its 9/20 requested-target agreement is not accuracy. See [Bloom validation](BLOOM_CLASSIFICATION_VALIDATION.md). |
| Are lecture results correctly calculated and mapped? | Active canonical aggregation correctly sums question marks. Topic mapping is keyword/approved-topic based and has not been independently adjudicated; a topic is not an independently validated lecture learning outcome. Static lecture-bank coverage and identifiers have demonstrated gaps. |
| Are weaknesses sufficiently supported? | They describe observed lost marks under policy thresholds. They are not persistent cognitive deficits or measured mastery; sample gates count student topic rows rather than distinct questions and recommendation consumers do not consistently retain uncertainty. |
| Is the lecturer dashboard useful? | Partly: question/topic/Bloom breakdowns and validated teaching-action numbers can guide review. Fake lecturer-home values, missing/zero conflation, weak evidence labels, and access-control gaps prevent trust in the complete dashboard. See [dashboard validation](LECTURE_DASHBOARD_VALIDATION.md). |
| What was independently reproduced? | Weighted percentages, moments/pass rates, composite scoring, ranking metrics, diagram counterexamples, two anonymous API reads, generated-practice contract violations, CSV duplication/overlap, stored pilot target agreement, and the stored ten-question usefulness-rater calculations. |
| What data are still required? | Checkpoint/split manifests; independently double-labelled contextual DBMS questions; adjudicated topic/lecture mappings; enrolment/participation denominators; complete paired usefulness ratings with provenance; and longitudinal/pre-post intervention evidence. |

## Baseline and architecture

No `AGENTS.md` was found by the repository file inventory. At entry, the following already had staged changes: `.env.example`, `.gitignore`, `MODEL_AUDIT.md`, `README.md`, `app/api/lecturer.py`, `app/classifier/bloom_classifier.py`, `app/classifier/rules.py`, `app/config.py`, `app/services/llm_service.py`, `requirements-embeddings.txt`, `requirements.txt`, `tests/test_model_cleanup.py`, and three files under `models/bloom_modernbert/tokenizer/`. These are pre-existing work, not audit fixes. Reports live beside the engine README because root `.gitignore:91` ignores directories named `docs`; no ignore rule or index was changed to deliver them.

```text
graded submission + rubric + course
  -> ingestion/student_data.normalize_student_submission
     question/criterion join, bounds, identity, available marks
  -> services/student_pipeline._classify_questions
     cached/ModernBERT Bloom; approved metadata or taxonomy keyword topic
  -> analytics/student_document.build_numeric_analysis
     marks-weighted question/topic/Bloom percentages + heuristic fallbacks
  -> services/llm_service.generate_student_insights
  -> student_pipeline._assemble_document -> repository student_analytics
  -> services/exam_analytics.compute_exam_analytics
     cohort stats + canonical aggregation + confidence review flags
     + analytics/diagram_analysis.compute_diagram_analysis
  -> lecturer/student/dashboard APIs -> Gradex_AI_Client components

cohort topic/Bloom summaries + static question_bank.json
  -> analytics/weakness + services/recommendation.recommend_questions
     weighted lecture/tutorial/recent-exam/Bloom signals
  -> ranked lecturer practice/exam candidates

student next_question_strategy -> LLM practice generation -> generated_questions
priority cohort topics -> teaching_actions -> evidence-repaired action suggestions
```

`app/analytics/` contains the deterministic equations; `app/services/` orchestrates classification, evidence, generation and persistence; `app/db/repository.py` determines record identity and queries; `app/api/` exposes them. The active cohort service recalculates canonical performance from normalized question records. `services/topic_canonicalization.py::canonicalize_topics` has test callers but no active application caller found; its defects are documented as legacy risks, not misrepresented as active pipeline failures. Embedding cosine/duplication and clustering exist, but clustering is not a traced runtime mastery model. There is no independently evaluated learner ability/difficulty model or causal lecture-effect estimator in the traced flow.

## Significant findings and priorities

Severity follows the requested educational-impact scale. Critical findings materially misrepresent results; security findings are separately High even when they do not change arithmetic. Exact counterexamples and source line references are in the companion reports and tests.

| ID / severity | Source and evidence | Impact and smallest remediation |
| --- | --- | --- |
| A1 Critical | `analytics/diagram_analysis.py::compute_diagram_analysis:91-94,118-136`, EQ-01/EQ-03. Students 6/10 and 60/100 are both at60%, yet pass rate is50% rather than100%. Two awards2/5 become100% by using highest awarded2 as denominator. | Incorrect pass/criterion labels can conceal teaching needs. Use each student's authoritative maximum for pass decisions; join criterion rubric maxima or show an explicitly unscored criterion when absent. Reject nonpositive maxima consistently. |
| A2 Critical | `analytics/exam_analytics.py::compute_exam_analytics_stats:236-256`, `build_insights:75-77`, EQ-09. Ten students on one distinct question satisfy the attempt gate and can be described as ten questions. | Unwarranted confirmed weakness and false coverage. Carry unique question counts separately from students and response attempts, and use the intended assessment-coverage gate. |
| A3 High | `api/dashboard.py`, `api/lecturer.py`, `api/deps.py`; DASH-01. Controlled ASGI reads of another student's profile and lecturer exam inventory return200 without credentials. | Identifiable student information and lecturer data lack backend ownership/role enforcement. Add authenticated identity/role dependencies and verify student ownership. Frontend login/local storage is insufficient. External gateway controls, if any, were not inspected. |
| A4 High | `classifier/bloom_classifier.py::predict_bloom_batch`, source/gold CSVs; 500/500 normalized overlaps,13 source texts with conflicting labels, fixed version string and missing split manifest. | No defensible unseen-data accuracy or calibrated-confidence claim. Recover provenance and independently annotate a frozen source-group holdout; preserve ambiguous/unclassified cases and review flags. |
| A5 High | `services/llm_service.py::generate_student_insights:122-153`, `student_pipeline.py::_validated_insights:355-374`, `_assemble_document:401-432`; R3/R4 and passing baseline characterization. | Schema-valid advice can recommend unassessed Botany to a SQL student, arbitrary topics/difficulty can overwrite backend strategy, and every free-text gap attaches to the first weak topic. Validate topic/level/evidence references against backend sets; retain backend-owned priorities/strategy and structured gap identifiers. |
| A6 High | `llm_service.py::generate_practice_questions:162-182`, `llm/roles/generate_practice.py`; R3. Five SQL/Apply/Medium questions requested; one Botany/Remember/Hard question returns status ok. | Practice may be unavailable, unrelated or at the wrong level. Check exact requested count, topic/level/difficulty membership and duplicate prompts before persisting; schema validity does not prove answerability or cognitive demand. Have a lecturer review content quality. |
| A7 High | `services/recommendation.py::recommend_questions:130-234`; R1/R2. Empty analytics still produce a candidate; duplicate bank rows are ranked twice. Static bank has179 records,18 generated records with IDs absent from current taxonomy. | Candidate scores can look personalized without performance evidence; coverage and useful diversity are unreliable. Separate curriculum suggestions from evidence-based practice, deduplicate identities/text, and reconcile taxonomy IDs before ranking. |
| A8 Critical | Lecturer-home frontend mock metrics (DASH-08; exact component/lines in dashboard report). | Plausible invented counts/trends can be mistaken for measured cohort results. Replace with backend values or explicit unavailable states before using home summaries for decisions. |
| A9 High | `evaluation/metrics.py::ndcg_at_k:174-179`, EQ-06; tuning/rater scripts call it. Relevance[T,F,T], k2 returns1 instead of0.613147. | Ranking evaluation/tuning can be inflated. Compute ideal gain over the full judged candidate set before cutoff; reject mismatched/unknown metric inputs and preserve held-out validation. |
| A10 Medium | `analytics/weakness.py::compute_weakness_scores`, recommendation consumers; `student_document.py` fallback decisions. | Lost marks and heuristic cognitive levels are presented without enough repeated observations/uncertainty. Preserve evidence counts/status in recommendations and describe observed performance; avoid persistent mastery claims. |
| A11 Medium | Diagram50/65/80 status vs shared40/60/80; question modal75 vs backend80 (EQ-04/DASH report); Bloom absent=0 displays. | Identical numbers yield conflicting categories; true zero and missing assessment evidence are conflated. Use one declared policy, explicit missing values, displayed assessed-question/student counts. |
| A12 Medium | Classification cache in `student_pipeline.py`, UI request handling and static lecture assets (dashboard report). | Changed models/taxonomy can reuse old semantics; old student requests can overwrite a new selection. Fingerprint evidence/model/taxonomy and reject stale UI responses. Reconcile lecture IDs and upload-to-bank provenance. |
| A13 Low | Existing `tests/test_student_data_ingestion.py::test_normalize_submission_joins_questions_and_criteria:51-58`. Sample rubric artifact is now a list of2; test passes that list to a function requiring a dictionary. | Baseline suite is not green. Select/join the intended sample rubric explicitly and keep assertions against that actual rubric. This is fixture-shape drift, not evidence that production accepts a malformed list. |

Default recommendation weights form a valid convex sum, but custom negative weights pass the sum check (EQ-05). Tutorial count heuristics, exam novelty and Bloom coverage are curriculum signals rather than measures of learning benefit. No attempted/mastered-question exclusion, outcome measurement or independently proven difficulty appropriateness was demonstrated. Teaching-action validation is a positive counterexample: `_validate_llm_output` discards unknown topic names and repairs supplied percentages/priorities to backend evidence; the tests reproduce this protection. Its free-text suggestions still need pedagogical review.

## Independent test evidence

Final consolidated command from this engine directory:

```powershell
.\.venv\Scripts\python.exe scripts/run_audit_tests.py
```

The runner executes a fixed offline selection, preserves the existing pytest convention, blocks `.env` reads, Motor construction and external HTTP transports, and skips coroutine tests and `tmp_path` fixtures because this Windows sandbox cannot reliably initialize those fixtures. Synchronous privacy probes drive immediately completing mocked ASGI coroutines; they execute the actual HTTP routing with no real DB. Equation tests sometimes isolate unchanged function bodies with AST; this does not claim full schema/model integration. The interpreter warning about locating its Python3.14 executable is retained as an environment limitation.

Final observed result: **89 passed, 1 failed, 12 skipped, 21 strict xfailed; exit code 1**. Counts, timing and output are saved in [audit_evidence/test_results.txt](audit_evidence/test_results.txt). Strict xfails represent known uncorrected production defects; they do not mean that the desired contract passed. There are no fresh model-quality results in this test run. The full MongoDB/live-LLM suite was not executed; its `tests/conftest.py::test_db` cleanup drops its named database, which this audit excludes.

An initial unrestricted selection was interrupted when async/temp-fixture setup stalled; a first broad network-blocking dashboard experiment broke Windows internal asyncio sockets. Neither is represented as a completed baseline or successful test. The final runner uses narrower transport guards and explicit skips. The only ordinary failure in the final selection is the list-shaped rubric fixture above.

Covered independent cases include unequal maximum marks, correct/incorrect and zero scores, empty datasets, two topic coverage sizes, duplicate candidates, missing/unassessed advice, no-topic mappings and Bloom absent classes. A true unanswered response must be a recorded zero-mark result to enter the complete-input normalizer; absent evaluation rows are rejected, rather than silently interpreted as knowledge failure. Multi-topic questions are currently single-dominant-topic in student semantics; allocation validation remains a proposed test after the intended multi-topic policy is specified. Keyword ambiguities are evidence probes in the Bloom report, not invented human gold.

## Reproduced research artifacts

Training-source clarification: the user identified the sole ModernBERT training CSV at `C:\Users\liyan\OneDrive\Documents\SLIIT\Y4\Research\Dataset\bloom model\blooms_taxonomy_dataset.csv`. [Independent comparison](audit_evidence/training_source_comparison.json) confirms identical bytes/hash to the repository source and all500 gold texts in the pool. This resolves the source-file uncertainty, while actual training/validation/test membership remains unknown. If every row was fitted, gold-v2 cannot serve as an unseen test. If the CSV was split before fitting, verify membership against the fitting and model-selection rows before concluding leakage.

[audit_evidence/bloom_evidence.json](audit_evidence/bloom_evidence.json) records source/pilot hashes, class counts, text overlap, confusion/per-class target-agreement metrics and saved-input hash checks. Recreate with `python scripts/audit_bloom_evidence.py`. Source8,767 rows include46 duplicate records and13 conflicting-label texts. Gold-v2 is balanced500 rows but shares all500 source texts. Pilot20 current question predictions agree with requested generator targets9 times, six-class macro target-agreement F1=0.306349. These are historical diagnostics, **not empirical classification accuracy**. Three notebooks have no saved outputs; duplicated eight-prediction smoke artifacts have no gold.

`python scripts/score_two_raters.py` selects `usefulness_lec01.csv` and `usefulness_lec02.csv`, ten rows each. All ten question IDs align in row order, independently checked with CSV parsing. [Saved output](audit_evidence/rater_reproduction.txt) reproduces overall means3.80/4.40, weakness-fit means3.30/5.00, exact overall kappa−0.153846, and would-edit kappa0.137931. Would-use is unanimously true; code returns kappa1 at the degenerate expected-agreement1 case, and P@5/NDCG@5=1 cannot distinguish rankings in that all-relevant sample. These measurements remain conditional on recorded ratings and undocumented annotation provenance. The script prints a fixed /10 denominator; it is not a general sample-size calculation. No learning-gain claim follows from lecturer usefulness ratings.

No optimization/retraining was run. Tuning scripts search weights on workshop ratings; a second rater of the same candidate rows is not a new candidate/source-group holdout, and NDCG has the reproduced ideal-denominator error. Existing research metrics must be audited by split/identity before adopting tuned weights. Stronger labels, controlled temporal evaluation and outcome data are needed before calling the recommendation system a proven learning intervention.

## Ordered remediation plan

1. **Protect access and correct displayed evidence first.** Enforce backend ownership/roles; replace fake lecturer-home figures; correct diagram per-student and rubric denominators. Expected effects: accurate API/UI values and safer use, without changing Bloom models. Compatibility: real authorization tokens will be required; corrected percentages/statuses may change substantially. Acceptance: anonymous/wrong-owner reads reject; existing positive-role requests succeed; EQ-01/02/03 pass on authoritative data.
2. **Make evidence counts honest.** Separate distinct students, distinct assessed questions, response attempts, missing/unanswered and coverage. Gate weakness labels/recommendations with those quantities; preserve missingness in charts. Expected effects: low-coverage topics stop becoming confirmed weaknesses. Compatibility: additive API fields first; keep existing percentages while clarifying their denominators. Acceptance: one question across ten students still displays one-question coverage; duplicate records do not inflate counts; topic totals reconcile.
3. **Bind recommendations to evidence.** Validate generated topics/levels/counts; retain backend strategy/priorities, structured gap links, unique candidates and assessed coverage; reconcile generated IDs and static/uploaded lecture bank. Expected effects: fewer unsupported recommendations and actionable topic-specific practice. Compatibility: invalid batches become degraded/unavailable instead of ok; clients need explicit empty/error states. Acceptance: R1–R4 pass, unrelated topics rejected, deterministic fallback survives service failure.
4. **Repair evaluation arithmetic and obtain independent labels.** Correct NDCG, paired-length/weight validation; recover ModernBERT manifest and annotate source-group-held-out DBMS question/mapping samples with two lecturers and adjudication. Expected effects: mathematically correct ranking evidence and measurable classification/mapping validity. Compatibility: reported metrics will change; archive old values and checkpoint identity. Acceptance: hand-calculated metric tests pass; split overlap zero; class support/confusion/annotation agreement/calibration/abstention coverage reported honestly.
5. **Improve instructional decisions and assess outcomes.** Show per-topic/Bloom counts, observed marks, uncertainty/coverage, evidence drill-down and suggested action provenance; harmonize thresholds/cache fingerprints/stale request handling. Track revision/pre-post practice outcomes by assessment identity with consent and appropriate access. Expected effects: lecturers can inspect why an action is suggested and whether later observed performance changes. Compatibility: additional metadata and refresh requirements; do not attribute causal gains without an intervention design. Acceptance: selected student/exam never shows stale values; zero and unassessed differ; action evidence links resolve; outcome study has a predefined comparison and metric.

No production remediation was bundled into the baseline audit. Formula choices involving criterion maxima, missingness, multi-topic allocation and role access require their intended contracts to be explicit; trained educational validity additionally requires human/data evidence that code changes cannot manufacture. The reports and counterexample tests make the proposed fixes reviewable without altering the original evidence.

## Evidence strength and limits

**Verified by source inspection:** architecture, current ModernBERT-only label path, mapping/cache policy, schema-only student advice checks, static candidate bank, UI constants and route dependency structure.

**Verified by independent calculations and tests:** arithmetic cases and failures above, ASGI anonymous reads, target/count/duplicate violations, teaching evidence repair, CSV/pilot/rater calculations.

**Verified by held-out empirical evaluation:** none for the current checkpoint, lecture mappings, calibrated confidence, recommendation learning benefit or causal teaching effectiveness.

**Plausible but unverified:** independent human utility of generated activities, relative cognitive demand, lecture learning-outcome mastery and effectiveness of the chosen cutoffs/weights.

**Unsupported by current evidence:** blanket claims of validated Bloom accuracy, persistent cognitive deficiency from one exam, probabilities of mastery from softmax, or proven learning gains from recommendations. Synthetic student/sample data cannot establish those claims.

Skipped live DB/model/LLM and browser visual verification. Arithmetic, privacy, mapping and recommendation defects remain in production; do not treat this audit as a certification or a passing full-suite result.
