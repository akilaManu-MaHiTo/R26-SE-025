# Dashboard Architecture Restructure Design

Date: 2026-08-12
Status: Approved for planning

## Overview

Restructure the backend to match the data architecture in
`student_lecture_dashboard_data_structure.md`: separate exam/lecturer analytics
from student-specific analytics, generate personalized content on demand, and
avoid pre-generating expensive AI analysis for every student.

The work is delivered as three vertical slices, each self-contained
(spec -> plan -> test cycle):

1. **Slice 1 (Level 2)** — reshape the persisted student document to the spec's
   `studentExamAnalysis` structure and add on-demand generation.
2. **Slice 2 (Level 1)** — replace the old cohort pipeline with spec-shaped exam
   analytics and add lecturer endpoints (exam analytics + student list).
3. **Slice 3 (Level 3)** — add generated-question storage, schema, and an
   on-request generation endpoint.

## Decisions (from brainstorming)

- **Collection naming**: keep the current collection names and map concepts.
  No collection renames or migrations to new spec names.
- **Student analysis flow**: on-demand generation at first dashboard access with
  MongoDB caching; the existing `run_sample.py` batch materializer is kept as a
  precaching tool.
- **Level-3 scope**: full endpoint + storage (generatedQuestions collection).
- **Lecturer dashboard**: both endpoints (exam analytics + student list) and a
  reshaped exam-analytics document.
- **Old cohort pipeline**: replace `run_analytics`/`analytics_snapshots`/
  `exam_recommendations` with the new exam-analytics generator.
- **Login/auth**: simulated login, no real authentication; the student is
  identified by `student_id` path parameter.
- **Exam analytics timing**: computed as part of the post-processing pipeline run.
- **Student document shape**: reshape to the spec structure while keeping rich
  per-question detail.
- **Approach**: vertical slices, reshape-first.

## Collection Mapping

| Spec collection | Current collection | Role |
|---|---|---|
| `exams` | *(derived from `courses` + `session_name`)* | exam identity = `course.code + session_name` string key; no new `exams` collection |
| `rubrics` | `rubricCollection` | rubric metadata |
| `studentExamResults` | `submissions` | raw per-student grades (lecturer list) |
| `examAnalytics` | `analytics_snapshots` (reshaped) | precomputed class analytics |
| `studentExamAnalysis` | `student_analytics` (reshaped) | cached per-student analysis |
| `generatedQuestions` | `generatedQuestions` (new) | Level-3 output |

Because there is no `exams` collection, `exam_id` becomes a stable string key
`"{course_code}@{session_name}"` used consistently across both analytics
documents and generated questions. Exam metadata (`total_marks`,
`question_count`) is derived from the rubric and submissions.

## Data Processing Strategy

Three levels of processing:

- **Level 1 — Exam/Lecturer Analytics**: precomputed after submissions are
  processed. Class-level statistics, topic/Bloom/question performance, attention
  areas, insights. No per-student learning recommendations.
- **Level 2 — Student Analysis**: generated when the student first accesses the
  student dashboard, cached in MongoDB and reused on later logins.
- **Level 3 — Personalized AI Content**: generated only when the student
  actually requests practice questions.

### Status thresholds

Per spec section 10 (adjustable later as part of research methodology):

```text
80–100   Strong
60–79    Developing
40–59    Needs Improvement
0–39     Critical
```

## Slice 1 — Reshaped Student Document + On-Demand Generation

### Reshaped `student_analytics` document (maps to `studentExamAnalysis`)

```json
{
  "student_id": "IT21001234",
  "exam_id": "IT2040@Final Examination 2021",
  "course": { "code": "IT2040", "name": "Database Management Systems" },
  "overall_performance": {
    "score": 65, "maximum": 100, "percentage": 65, "status": "Needs Improvement"
  },
  "question_performance": [
    {
      "question_id": "Q01",
      "question_no": "01",
      "question_text": "...",
      "topic": "DBMS Design",
      "subtopic": "...",
      "bloom_analysis": { "level": "Understand", "confidence": 0.9, "reason": "..." },
      "performance": { "score": 6, "max_score": 8, "percentage": 75 },
      "criteria_performance": [
        { "criterion": "...", "max_marks": 2.0, "awarded_marks": 1.0, "achieved": true }
      ]
    }
  ],
  "topic_performance": [
    { "topic": "JDBC", "questions_attempted": 2, "score": 19,
      "max_score": 25, "percentage": 76, "status": "Strong" }
  ],
  "bloom_performance": [
    { "level": "Remember", "questions_attempted": 2, "average_score": 83,
      "status": "Strong" }
  ],
  "learning_analysis": {
    "overall_performance": "Needs Improvement",
    "strong_topics": ["JDBC"],
    "developing_topics": ["DBMS Design"],
    "weak_topics": ["Database Programming"],
    "critical_topics": ["SQL"],
    "learning_gaps": [
      { "topic": "SQL", "subtopic": "Authentication and Authorization", "priority": "Critical" }
    ]
  },
  "recommendations": [
    { "topic": "SQL", "priority": "Critical",
      "action": "Review SQL Server authentication, users and roles." }
  ],
  "next_question_strategy": {
    "recommended_topics": ["SQL", "Database Programming"],
    "recommended_bloom_levels": ["Understand", "Apply"],
    "recommended_difficulty": "Medium",
    "number_of_questions": 5
  },
  "model_metadata": {
    "bloom_model": "...", "bloom_model_type": "...",
    "grading_source": "colab", "rag_context_used": true
  },
  "generated_at": "2026-08-12T00:00:00Z",
  "analysis_version": "1.0"
}
```

Key changes from the current document:

- `assessment` block -> `overall_performance` (score/maximum/percentage/status).
- `question_analysis` -> `question_performance`; spec field names are used but
  the rich per-question data is preserved (question text, topic, subtopic,
  `bloom_analysis` with confidence/reason, criteria breakdown). Optional
  per-question fields (e.g. a `part` component) are included only when the
  source data provides them.
- `next_question_generation` -> `next_question_strategy` with
  `recommended_bloom_levels` (list) instead of a single recommended level.
- `learning_analysis` gains the four buckets
  (`strong/developing/weak/critical_topics`) and structured
  `learning_gaps` (`{topic, subtopic, priority}`).
- New `exam_id` identity field, `generated_at`, and `analysis_version`.
- `model_metadata` is kept for traceability.

### On-demand generation service

```python
async def ensure_student_analytics(
    db, student_id: str, course_code: str, session_name: str
) -> StudentAnalyticsDocument:
    cached = await find_student_analytics(db, student_id, course_code, session_name)
    if cached:
        return cached
    return await build_and_save(db, student_id, course_code, session_name)
```

The existing `materialize_student_analytics` batch pipeline is refactored so its
per-student build logic (normalize -> classify -> numeric -> insights ->
validate -> save) is reused by `build_and_save`. `run_sample.py` continues to
batch-precache all sample students.

`GET /api/students/{student_id}/dashboard` calls the ensure function: the first
hit generates and saves, later hits load from MongoDB. HTTP 404 when the student
has no graded submission.

### Persistence identity

`student_analytics` unique compound index changes to:

```text
student_id + course.code + exam_id
```

Writes are idempotent `replace_one(..., upsert=True)` replacements.

## Slice 2 — Lecturer Exam Analytics + Student List

### Reshaped `analytics_snapshots` (maps to `examAnalytics`)

```json
{
  "exam_id": "IT2040@Final Examination 2021",
  "course": { "code": "IT2040", "name": "Database Management Systems" },
  "exam": { "session_name": "Final Examination 2021",
            "total_marks": 100, "question_count": 11 },
  "statistics": {
    "total_students": 5, "attempted_students": 5,
    "average_score": 67.4, "average_percentage": 67.4,
    "pass_rate": 81.5, "highest_score": 94, "lowest_score": 31
  },
  "topic_performance": [
    { "topic": "JDBC", "average_percentage": 76, "status": "Strong" }
  ],
  "bloom_performance": [
    { "level": "Remember", "average_percentage": 83 }
  ],
  "question_performance": [
    { "question_id": "Q01", "question_no": "01", "topic": "DBMS Design",
      "bloom_level": "Understand", "average_percentage": 75 }
  ],
  "attention_areas": [
    { "type": "topic", "name": "SQL", "average_percentage": 33, "priority": "Critical" }
  ],
  "insights": [
    "SQL is the weakest topic across the class.",
    "Students perform strongly on JDBC and Schema Refinement."
  ],
  "generated_at": "2026-08-12T00:00:00Z",
  "analytics_version": "1.0"
}
```

Class-level values are computed from **all** graded submissions; a single
student's results are never used as class statistics.

### Replacement of the old cohort pipeline

`app/services/analytics.py` (`run_analytics`), the `analytics_snapshots`
document, and the `exam_recommendations` / `analysis_runs` /
`question_attempts` machinery are replaced by a new
`compute_exam_analytics` generator that emits the spec-shaped document above.

Deterministic computation reuses existing helpers where possible:

- Topic/Bloom aggregation follows the patterns in
  `app/analytics/student_document.py` (sum marks, marks-weighted percentage,
  status thresholds).
- `topic_performance.status` uses the spec thresholds (80/60/40).
- `attention_areas` are derived from bottom-ranked topics with Critical/High
  priority.
- `insights` are generated deterministically from the computed statistics using
  rule templates.

### Lecturer endpoints (new router `app/api/lecturer.py`)

```
GET /api/lecturers/exams/{course_code}/{session_name}/analytics
GET /api/lecturers/exams/{course_code}/{session_name}/students
```

Student-list response shape (maps to `studentExamResults`):

```json
{
  "student_id": "IT21001234",
  "score": { "obtained": 65, "maximum": 100, "percentage": 65 },
  "status": "Needs Improvement",
  "analysis_status": "generated",
  "submitted_at": "2026-08-10T10:00:00Z"
}
```

`analysis_status` is `"generated"` when a matching document exists in
`student_analytics`, otherwise `"pending"`. HTTP 404 when the exam has no
submissions or no computed analytics.

## Slice 3 — Personalized Question Generation

### `generatedQuestions` collection + schema

```json
{
  "student_id": "IT21001234",
  "exam_id": "IT2040@Final Examination 2021",
  "course": { "code": "IT2040", "name": "Database Management Systems" },
  "request": {
    "recommended_topics": ["SQL", "Database Programming"],
    "recommended_bloom_levels": ["Understand", "Apply"],
    "recommended_difficulty": "Medium",
    "number_of_questions": 5
  },
  "questions": [
    {
      "prompt": "...",
      "bloom_level": "Understand",
      "topic": "SQL",
      "difficulty": "Medium",
      "hints": ["..."]
    }
  ],
  "generated_at": "2026-08-12T00:00:00Z",
  "generation_version": "1.0"
}
```

### Endpoints

```
POST /api/students/{student_id}/practice-questions
GET  /api/students/{student_id}/practice-questions?fresh=false
```

`POST` behavior:

1. Load the student's cached analysis (generating it first via
   `ensure_student_analytics` if missing) to obtain `next_question_strategy`.
2. Call Qwen (`llm_service`) with that target to generate practice questions.
3. Validate output; cache in `generatedQuestions`; return the questions.
4. If Qwen is unavailable -> HTTP 503 with the target echoed in the detail.

`GET` returns the last cached batch; `fresh=true` (or no cache) regenerates.

## API Surface Summary

| Method | Path | Notes |
|---|---|---|
| GET | `/api/students/{student_id}/dashboard` | generate-on-miss, load-on-hit |
| POST | `/api/students/{student_id}/practice-questions` | Level-3 generation |
| GET | `/api/students/{student_id}/practice-questions` | cached batch; `fresh` param |
| GET | `/api/lecturers/exams/{course_code}/{session_name}/analytics` | class analytics |
| GET | `/api/lecturers/exams/{course_code}/{session_name}/students` | student list |

## Error Handling

| Case | Behavior |
|---|---|
| Student not found anywhere (no submission) | 404 on student dashboard / practice endpoints |
| Qwen unavailable at student-analysis time | deterministic fallbacks (rule classifier + fallback gaps/recommendations) |
| Qwen unavailable at practice-question time | 503 with stored target echoed |
| Invalid marks / join failure | per-student failure isolated; batch run continues others |
| No exam analytics yet | 404 on lecturer analytics endpoint |
| Mongo unavailable | 500, logged, no stack trace leak |

## Model Responsibilities

- Qwen is responsible for: question Bloom/topic/subtopic semantics,
  personalized learning insights (gaps, recommendations, generation targets),
  and Level-3 practice-question generation.
- The backend owns every numerical calculation: percentages, weighted
  averages, status labels, class statistics, pass rate, attention areas,
  thresholds, and question counts.

## Testing

All tests are offline and deterministic; live-model tests are excluded from the
required verification command. Each slice follows TDD (failing test -> RED ->
implementation -> GREEN).

**Slice 1:**

- Schema contract tests for the reshaped document (exact top-level keys,
  validation of new fields, status threshold boundaries 80/60/40).
- Deterministic analytics tests (marks-weighted aggregation, structured
  learning gaps, four-bucket topic classification).
- On-demand service tests (generate-on-miss, load-on-hit, 404).
- Updated pipeline and API tests for the new shape and identity index.

**Slice 2:**

- Class-statistics math tests from the sample submissions with hand-computed
  expectations (total_students, average_percentage, pass_rate,
  attention_areas, insights).
- Lecturer endpoint tests (happy path, 404, analysis_status derivation).

**Slice 3:**

- Question-generation service tests (target from cache, Qwen success 200,
  Qwen down 503, caching behavior).
- `generatedQuestions` repository upsert/find tests.

Tests asserting the old shapes are updated or removed in-slice:
`test_schemas_student.py`, `test_student_document_analytics.py`,
`test_api_dashboard.py`, `test_analytics_service.py`,
`test_schemas_derived.py`, and related repository/run-sample tests.

### Verification command

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```

Plus `git diff --check` and `compileall` per slice.

## Out of Scope

- Frontend changes.
- Real authentication / login / authorization.
- Creating an `exams` collection.
- Regrading answers or changing grading output.
- Renaming MongoDB collections.
