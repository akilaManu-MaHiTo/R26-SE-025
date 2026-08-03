# API, Persistence, Testing, and Deployment Plan

**Status:** Approved design package for review  
**Date:** 2026-08-03  
**Depends on:** All other QuestionExamPredictionEngine plans in this folder

## 1. API strategy

Preserve current endpoints during migration. Add versioned course-based workflow endpoints that read MongoDB data by identity rather than requiring callers to send entire datasets.

### 1.1 Start an analysis and forecast run

```http
POST /v2/courses/{subject_code}/prediction-runs
```

Example request:

```json
{
  "analysis_cutoff": "2026-07-26T05:12:00Z",
  "target_session": "Semester 2 Final Exam",
  "include_student_profiles": true,
  "include_topic_forecast": true,
  "include_structure_forecast": true,
  "include_performance_risk": true,
  "include_lecturer_support": true,
  "options": {
    "weak_threshold": 0.5,
    "minimum_students": 2
  }
}
```

The response returns `run_id`, status, processing mode, warnings, model versions, and authorized result identifiers.

### 1.2 Run status and result

```http
GET /v2/prediction-runs/{run_id}
GET /v2/prediction-runs/{run_id}/result
```

### 1.3 Course insights

```http
GET /v2/courses/{subject_code}/insights?cutoff=...
GET /v2/courses/{subject_code}/forecasts/latest
GET /v2/courses/{subject_code}/lecturer-support/latest
```

### 1.4 Student profile

```http
GET /v2/courses/{subject_code}/students/{student_id}/learning-profile
```

This endpoint requires student- or lecturer-authorized access and never exposes other students.

### 1.5 Lecturer review

```http
POST /v2/lecturer-support/{report_id}/recommendations/{recommendation_id}/review
POST /v2/generated-practice/{draft_id}/review
```

Review actions are append-only revisions containing reviewer identity, decision, comments, and timestamp.

## 2. Response provenance

Every output includes:

```text
run_id
subject_code
analysis_cutoff
target_session
source_document_ids
model_versions
policy_versions
feature_schema_version
status
warnings
created_at
```

Forecast items additionally include horizon, supporting features, training range, metrics artifact, calibration status, and supported-course decision.

## 3. Persistence

Persist immutable run bundles. Corrected data, lecturer review, model changes, or reruns create new revisions linked to earlier results.

### `prediction_runs`

- `run_id` and `idempotency_key`;
- requestor and tenant/course scope;
- source IDs/checksums, cutoff, and target;
- model/policy versions;
- status, warnings, and timings; and
- output document references.

### `course_insight_reports`

- question and topic summaries;
- misunderstood questions and cognitive gaps;
- weak-topic results; and
- historical feature summaries.

### `student_learning_profiles`

- pseudonymous student key;
- observed performance history;
- diagnosed mastery/cognitive gaps;
- advisory risk results; and
- visibility and retention metadata.

### `exam_forecasts`

- topic ranking/probabilities;
- structure predictions;
- performance-risk predictions;
- baseline comparisons; and
- evaluation/calibration metadata.

### `lecturer_support_reports`

- ranked actions and supporting evidence;
- affected scope and resources;
- review state; and
- feedback history.

### `model_registry`

- capability, version, and artifact location;
- manifest and supported courses;
- approval/promotion state;
- metrics and calibration; and
- deployed/retired timestamps.

## 4. Processing model

Start synchronously for small course datasets, but keep a job abstraction so the contract supports background execution. Move to a queue when measured processing time exceeds the agreed request timeout or model workloads become remote/GPU dependent.

Run states:

```text
accepted -> validating -> analyzing -> forecasting -> recommending
         -> completed | partial | failed | review_required
```

Transitions are append-only audit events.

## 5. Error handling

- Use stable machine-readable error codes.
- Reject invalid course/cutoff requests before model execution.
- Return data-quality issues separately from system failures.
- Preserve partial results for unaffected records.
- Do not expose internal exception strings or raw student content.
- Retry transient database/model-service failures with bounded backoff.
- Do not retry deterministic validation errors.
- Use dead-letter/review handling for repeatedly failing queued runs.

## 6. Authorization and privacy

Roles:

- student: own profile and approved feedback;
- lecturer: assigned-course cohort insights and student support views;
- academic administrator: authorized course/program summaries;
- model/research administrator: pseudonymized datasets and evaluation;
- system administrator: operations without default access to answer content.

Controls:

- course-scoped authorization on every endpoint and repository method;
- field-level filtering for student versus lecturer responses;
- pseudonymized model datasets;
- no raw answer text in normal logs, metrics, or traces;
- encryption in transit and at rest;
- retention/deletion propagation to derived profiles and vector stores;
- audit events for profile access, forecast creation, and lecturer approval; and
- documented consent/legal basis for research training data.

## 7. Test strategy

### 7.1 Unit tests

- normalization and question-number joins;
- score/max-mark reconciliation;
- feature calculations and cutoff enforcement;
- contracts, manifests, confidence bounds, and warnings;
- recommendation rules; and
- authorization decisions.

### 7.2 Model evaluation tests

- reproduce stored metrics from frozen evaluation datasets;
- ensure preprocessing and label mappings match manifests;
- assert temporal split and leakage rules;
- compare baselines and enforce calibration gates;
- verify supported-course and out-of-distribution behavior; and
- verify artifact checksums and schema compatibility.

### 7.3 Agent and orchestration tests

- normal four-agent flow;
- one question mapping reused across students;
- optional-model failures and fallbacks;
- single-attempt failure isolation;
- idempotency and model-version invalidation;
- no mark mutation; and
- forecast omission when eligibility fails.

### 7.4 MongoDB integration tests

- representative source documents from all three confirmed collections;
- missing or invalid ObjectId references;
- duplicate attempts;
- absent answer splits and criteria breakdowns;
- indexes and query pagination; and
- partial-write behavior for result bundles.

### 7.5 API tests

- request validation and stable error codes;
- RBAC and cross-course access denial;
- synchronous and queued response compatibility;
- partial and review-required responses; and
- pagination and response-size limits.

### 7.6 Non-functional tests

- load and latency at expected and peak course sizes;
- memory usage when loading local models;
- concurrent prediction runs;
- backup/restore and disaster recovery;
- security scanning and dependency review; and
- privacy tests proving answers never enter logs.

## 8. Forecast evaluation and release gate

For each supported course or cross-course model:

1. Freeze canonical assessment order and topic labels.
2. Train only on assessments before the validation target.
3. Compare against frequency, recency, and score-risk baselines.
4. Report ranking metrics, probability metrics, and calibration.
5. Record insufficient-data and abstention behavior.
6. Obtain academic/model-owner approval.
7. Register the manifest as `approved` before enabling probabilities.

A trained artifact progresses through `candidate`, `shadow`, and `approved`. Shadow predictions are stored for evaluation but not displayed as authoritative lecturer output.

## 9. Monitoring

Operational metrics:

- run count, status rates, and latency;
- source-record rejection and question-join failures;
- model load failures and fallback usage;
- forecast eligibility and abstention rate;
- queue delay/retry count; and
- lecturer review backlog.

Model metrics:

- feature and label drift;
- topic mapping confidence;
- Bloom class distribution;
- weak-topic and risk-alert rates;
- forecast calibration and rolling temporal performance; and
- lecturer recommendation acceptance and correction rates.

Alerts must not contain student answers or direct identifiers.

## 10. Deployment environments

- **Development:** local artifacts, test MongoDB, synthetic/pseudonymized fixtures.
- **Research/staging:** frozen datasets, candidate evaluation, shadow forecasts.
- **Production:** approved manifests, restricted MongoDB credentials, monitoring, backups, audit, and rollback.

Use environment-specific secrets and databases. Model promotion is independent from code deployment but requires compatibility checks and rollback metadata.

## 11. Delivery sequence

### Release 1: MongoDB diagnostics

- Repositories and canonical normalization.
- Existing analytics/models with honest provenance and fallbacks.
- Course/student diagnostic endpoints.
- Immutable runs and RBAC.

### Release 2: Semantic understanding

- Topic/rubric mapping and course-material retrieval.
- Six-level Bloom improvement.
- Misconception and weak-topic evaluation.
- Evidence-backed learning profiles.

### Release 3: Forecasting

- Historical feature store and baselines.
- Topic, structure, and performance-risk shadow models.
- Temporal evaluation, calibration, and supported-course manifests.
- Approved forecast API output.

### Release 4: Lecturer support

- Ranked deterministic recommendations.
- Resource linking and lecturer review.
- Feedback collection.
- Optional controlled practice-question drafts.

### Release 5: Production hardening

- Queued processing, optimization, drift monitoring, automated evaluation, backup/restore, incident procedures, and retraining governance.

## 12. Final completion checklist

- [ ] Confirmed MongoDB documents normalize and join correctly.
- [ ] GradingEngine marks are preserved and traceable.
- [ ] Current model routing and provenance defects are corrected.
- [ ] Four agents and the orchestrator use typed contracts.
- [ ] Diagnostic reports work without optional forecast models.
- [ ] Six-level Bloom, weak-topic, and misconception capabilities pass their gates.
- [ ] Topic and performance-risk models beat temporal baselines.
- [ ] Published probabilities are calibrated and course-supported.
- [ ] Lecturer recommendations cite evidence and support review.
- [ ] Student and course RBAC is enforced.
- [ ] Logs contain no raw answers or direct identifiers.
- [ ] Unit, integration, API, temporal, load, security, and recovery tests pass.
- [ ] Monitoring, rollback, retention, and model governance are operational.

