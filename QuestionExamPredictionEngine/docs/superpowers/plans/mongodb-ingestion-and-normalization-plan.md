# MongoDB Ingestion and Normalization Plan

**Status:** Approved design package for review  
**Date:** 2026-08-03  
**Depends on:** `question-exam-prediction-engine-master-plan.md`

## 1. Objective

Create a read-safe integration boundary between the GradingEngine MongoDB collections and QuestionExamPredictionEngine. External MongoDB documents are converted into stable internal records before analytics or models run.

## 2. Source collections

### 2.1 `courses`

Required fields are `_id`, `code`, `name`, and `description`. `code` becomes the external course key. The normalized value is trimmed and uppercased, while the original is preserved for traceability.

### 2.2 `rubricCollection`

Required fields:

- `_id`, `session_name`, and `subject_code`;
- `questions[].question_no`;
- `questions[].question_text`;
- `questions[].max_marks`; and
- `questions[].criteria[]`.

Optional but valuable fields are `filename`, `parsed_at`, `questions[].model_answer`, and future topic, Bloom, question-type, and difficulty annotations.

### 2.3 `submissions`

Required fields:

- `_id`, `rubric_ref`, `session_name`, and `subject_code`;
- `student_id`;
- `evaluation.results[].q_no`;
- `evaluation.results[].score`; and
- `status`.

Recommended fields are paper/question maximum marks, raw OCR transcript, criteria breakdown, justification, feedback, grading/RAG metadata, answer-split metadata, and `processed_at`.

Only `status="graded"` submissions are eligible for authoritative performance analytics unless a request explicitly includes another status for data-quality diagnostics.

## 3. Canonical internal contracts

### 3.1 CourseRecord

```text
course_id
subject_code
name
description
source_collection
source_document_id
```

### 3.2 AssessmentRecord

```text
assessment_id
course_id
subject_code
session_name
rubric_id
rubric_filename
parsed_at
assessment_order
```

`assessment_order` comes from an explicit assessment date when available. `parsed_at` is not an exam date and is only a last-resort ordering signal with a warning.

### 3.3 QuestionRecord

```text
question_id
assessment_id
question_no_raw
question_no_normalized
question_text
max_marks
topic_id
model_answer
rubric_criteria[]
```

Question normalization removes surrounding whitespace and normalizes numeric forms so `"01"`, `"1"`, and integer `1` join to the same key. The raw value is retained.

### 3.4 StudentAttemptRecord

```text
attempt_id
submission_id
student_id_pseudonymous
course_id
assessment_id
question_id
score
max_marks
performance_score
criteria_breakdown[]
student_answer
feedback
justification
grading_source
rag_metadata
processed_at
```

`performance_score = score / max_marks`. Values outside the expected range create an error or explicit data-quality warning; they are not silently clipped during ingestion.

## 4. Field mapping

| Source | Source field | Canonical field | Rule |
|---|---|---|---|
| courses | `_id` | `course_id` | String representation of ObjectId |
| courses | `code` | `subject_code` | Trim and uppercase |
| rubric | `_id` | `rubric_id` | String representation |
| rubric | `session_name` | `session_name` | Trim and retain exact source value |
| rubric question | `question_no` | `question_no_normalized` | Normalize numeric representation |
| rubric question | `criteria` | `rubric_criteria` | Preserve point and marks |
| submission | `_id` | `submission_id` | String representation |
| submission | `student_id` | `student_id_pseudonymous` | Hash/map before logs and model exports |
| submission result | `q_no` | question join key | Join against normalized rubric number |
| submission result | `score` | `score` | Numeric and range validation |
| max-marks array | `max_marks` | `max_marks` | Rubric value wins when consistent |
| submission | `raw_ocr_transcript` | answer source | Split only when per-question text is unavailable |
| evaluation | `grading_source` | provenance | Preserve exactly |
| evaluation | `rag_context_used` | provenance | Metadata, not a learning feature by default |

## 5. Repository interfaces

Define protocols rather than importing the MongoDB driver in domain code:

```text
CourseRepository.get_by_code(subject_code)
RubricRepository.list_for_course(subject_code, cutoff=None)
SubmissionRepository.list_graded(subject_code, rubric_ids=None, cutoff=None)
PredictionRunRepository.get_by_idempotency_key(key)
PredictionRunRepository.save_immutable(result)
```

Concrete MongoDB repositories own ObjectId conversion, queries, projection, pagination, indexes, and driver errors. Agents receive canonical records only.

## 6. Join and validation rules

1. `subject_code` matches across course, rubric, and submission after normalization.
2. `rubric_ref` resolves to an existing rubric.
3. Every evaluation `q_no` resolves to one rubric question or is quarantined.
4. Duplicate student submissions follow an explicit attempt/revision policy.
5. Question score is numeric and no greater than the authoritative maximum without a warning.
6. Paper total reconciles with question totals within a configured tolerance.
7. Missing criteria breakdown reduces diagnostic depth but does not invalidate a score.
8. Missing raw answer text disables semantic and misconception models but not score analytics.
9. `processed_at` and source IDs remain in provenance.
10. Malformed records enter a data-quality report while unrelated valid records continue.

## 7. Historical grouping

Forecasting requires chronologically ordered assessments. Add or derive:

- `assessment_date` or academic year and semester;
- assessment type such as quiz, midterm, final, or repeat;
- course/module version where curricula change; and
- stable canonical topic identifiers across rubrics.

Do not infer chronological order from session names alone. If no reliable assessment date exists, diagnostics run but temporal forecasting is disabled with `missing_assessment_time`.

## 8. Proposed output collections

### `prediction_runs`

Immutable run context, input hash, cutoff, model versions, warnings, status, timings, and output references.

### `student_learning_profiles`

Revisioned student-course summaries, observed performance, diagnosed gaps, advisory risk outputs, visibility, and provenance.

### `course_insight_reports`

Question, topic, cohort, and longitudinal summaries for one course and cutoff.

### `exam_forecasts`

Forecast target, horizon, ranked output, probability/confidence, features, training range, calibration status, and artifact version.

### `lecturer_support_reports`

Ranked recommendations, supporting evidence IDs, affected cohort, priority, approval state, and lecturer feedback.

## 9. Indexes

Recommended indexes:

- `courses.code` unique;
- `rubricCollection.subject_code + session_name`;
- `submissions.subject_code + rubric_ref + status`;
- `submissions.student_id + subject_code + processed_at`;
- `prediction_runs.idempotency_key` unique;
- output collections by `subject_code + cutoff + model_version`; and
- lecturer reports by `subject_code + status + created_at`.

Validate indexes with real query plans before production.

## 10. Privacy and security

- Pseudonymize student IDs at the ingestion boundary for model datasets.
- Never write raw OCR transcripts or full answers to application logs.
- Encrypt connections and stored operational data according to deployment policy.
- Keep raw student text out of lecture-material vector collections.
- Enforce course-level authorization in every repository query.
- Record who initiated a prediction run and approved lecturer-facing output.
- Define retention and deletion propagation for derived student profiles.

## 11. Implementation sequence

1. Add canonical Pydantic contracts and validation tests.
2. Implement repository protocols with in-memory test doubles.
3. Implement MongoDB repositories with projections and pagination.
4. Implement course/rubric/submission normalization.
5. Add question-number joining and reconciliation reports.
6. Adapt the orchestrator to accept canonical records.
7. Add immutable result repositories and idempotency.
8. Add integration tests using representative MongoDB documents.
9. Add privacy, authorization, and malformed-record tests.
10. Benchmark expected course and submission volumes.

## 12. Acceptance criteria

- The supplied example documents normalize without losing source IDs or grading provenance.
- `01`, `1`, and numeric `1` join consistently while retaining raw values.
- Invalid records are reported without corrupting valid analytics.
- Forecasting is blocked when no trustworthy assessment ordering exists.
- Full student answers do not appear in logs or lecture-vector storage.
- Repeating the same cutoff, inputs, and model versions returns the same run.
- Tests cover missing rubric, missing question, duplicate attempt, invalid score, absent answer text, and partial criteria data.

