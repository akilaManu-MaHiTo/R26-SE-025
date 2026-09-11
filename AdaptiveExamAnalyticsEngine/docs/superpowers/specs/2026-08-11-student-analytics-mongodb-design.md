# Student Analytics MongoDB Materialization Design

## Objective

Replace the current public student dashboard structure with the canonical student
analytics document requested by the project. Build one complete document per
student, course, and assessment from the `courses`, `rubricCollection`, and
`submissions` MongoDB collections, then persist it in `student_analytics`.

The backend owns every numerical calculation. Qwen3-8B is limited to semantic
classification, explanations, learning gaps, recommendations, and question-
generation targeting.

Frontend changes are outside this implementation.

## Canonical Document

The persisted document and the response from
`GET /api/students/{student_id}/dashboard` use this top-level structure:

```json
{
  "student_id": "IT22145976",
  "course": {},
  "assessment": {},
  "question_analysis": [],
  "topic_performance": [],
  "bloom_performance": [],
  "learning_analysis": {},
  "recommendations": [],
  "next_question_generation": {},
  "model_metadata": {}
}
```

MongoDB may add its internal `_id`; `_id` is excluded from the API response.

The former public fields `student_key`, `run_id`, `generated_at`, `exams`,
`bloom_skills`, `topic_skills`, `weakest_topics`, and `cohort_comparison` are not
part of the replacement response.

## Persistence Identity

`student_analytics` has a unique compound index on:

```text
student_id + course.code + assessment.session_name
```

The pipeline uses `replace_one(..., upsert=True)` with that identity. Reprocessing
the same student assessment replaces the previous document rather than creating a
duplicate. A student document is written only after the complete document passes
schema validation.

## Source Data and Joins

The pipeline reads raw source documents from MongoDB collections named exactly:

- `courses`
- `rubricCollection`
- `submissions`

For local/sample execution, `run_sample.py` seeds those collections from
`app/sample_data/courses.json`, `app/sample_data/rubricCollection.json`, and every
`app/sample_data/submission*.json` file before running the materialization.

Source joins use:

- submission `rubric_ref` to rubric `_id` when both are usable;
- otherwise `subject_code` plus `session_name` as the sample-data fallback;
- normalized, zero-padded question numbers to join rubric `question_no` to
  submission `evaluation.results[].q_no`;
- course code from `course_code` or `subject_code` depending on the source shape.

The course name comes from the course document. The checked-in IT2040 sample may
fall back to `Database Management Systems` because its current `courses.json`
content duplicates the rubric-shaped document.

## Processing Architecture

```text
courses + rubricCollection + submissions
                 |
                 v
       raw-data normalization
                 |
                 v
       Qwen semantic classification
    Bloom + topic + subtopic + explanation
                 |
                 v
       deterministic Python analytics
 scores + percentages + aggregation + statuses
                 |
                 v
          Qwen learning analysis
       gaps + actions + generation targets
                 |
                 v
          validated MongoDB upsert
                 |
                 v
        persisted student API response
```

Qwen classification runs once per unique rubric question in a pipeline run and is
reused for every student who answered that question.

## Component Boundaries

### `app/schemas/student.py`

Defines Pydantic models for the exact canonical document, including nested course,
assessment, Bloom analysis, question performance, criterion performance, topic and
Bloom summaries, learning analysis, recommendations, generation targets, and model
metadata.

### `app/ingestion/student_data.py`

Normalizes source field aliases, validates marks, joins rubric questions to graded
results, and returns one normalized assessment input per submission. It performs no
LLM calls and no aggregate analytics.

### `app/analytics/student_document.py`

Contains pure functions for all numerical calculations and deterministic labels.
It has no database, HTTP, or model dependencies.

### `app/llm/roles/student_analysis.py`

Defines validated Qwen responses for question semantics and personalized learning
insights. Semantic topic and subtopic strings are course-aware and are not limited
to the existing DBMS taxonomy.

### `app/services/student_pipeline.py`

Coordinates source normalization, classification caching, deterministic analytics,
semantic insights, final schema validation, and persistence. It reports failures per
submission so one invalid student does not prevent valid students from being saved.

### `app/db/repository.py`

Adds raw collection readers, the `student_analytics` unique index, idempotent upsert,
and lookup by student with optional course and session filters.

### `app/api/dashboard.py`

Replaces the existing computed dashboard endpoint with a persisted-document lookup:

```text
GET /api/students/{student_id}/dashboard
GET /api/students/{student_id}/dashboard?course_code=SE3040
GET /api/students/{student_id}/dashboard?course_code=SE3040&session_name=Semester%201%20Final%20Exam
```

When filters are omitted, the most recently processed matching document is returned.
No matching document returns HTTP 404.

### `run_sample.py`

Seeds raw sample collections, processes every sample submission, prints a per-student
success/failure summary, and confirms the number of documents saved in
`student_analytics`.

## Model Responsibilities

### Question classification

For each unique rubric question, Qwen receives course context, question text, and
rubric criteria. It returns:

- Bloom level;
- topic;
- subtopic;
- confidence between 0 and 1;
- a concise classification reason.

The supported Bloom values are `Remember`, `Understand`, `Apply`, `Analyze`,
`Evaluate`, and `Create`.

If Qwen is unavailable or produces invalid structured output, the existing rule
classifier supplies the Bloom level and topic where possible. The fallback uses an
explicit subtopic derived from key concepts or the dominant topic, a conservative
confidence value, and a reason identifying rule-based fallback behavior.

### Personalized learning analysis

Qwen receives only backend-calculated performance evidence, classified subtopics,
and missed rubric criteria. It returns:

- learning-gap descriptions;
- personalized recommendation actions;
- semantic question-generation targets when appropriate.

Qwen may explain calculated evidence but may not replace, alter, or recalculate a
score, percentage, average, status, question count, or marks total.

If the insight call fails validation or is unavailable, deterministic gaps are built
from missed criteria and deterministic recommendation templates are used.

## Deterministic Calculation Rules

### Assessment

```text
total_score = sum(question awarded marks)
max_score = sum(question maximum marks)
percentage = round(total_score / max_score * 100, 2)
```

The pipeline recalculates totals from question results instead of trusting a source
aggregate or model output. `max_score <= 0` is invalid.

### Question performance

```text
percentage = round(score / max_score * 100, 2)
```

Criterion values are normalized to `criterion`, `max_marks`, `awarded_marks`, and
`achieved`. Partial credit counts as achieved:

```text
achieved = awarded_marks > 0
```

### Topic performance

Questions are grouped by their primary topic. Each group contains the number of
questions attempted, summed awarded marks, summed maximum marks, marks-weighted
percentage, and deterministic status.

### Bloom performance

Questions are grouped by Bloom level. `average_score` is the marks-weighted group
percentage so differently weighted questions contribute proportionally. Each group
also contains the number of questions attempted and deterministic status.

### Status thresholds

Thresholds are configurable and initially use:

- `Strong`: percentage greater than or equal to 75;
- `Needs Improvement`: percentage greater than or equal to 50 and less than 75;
- `Critical`: percentage less than 50.

`learning_analysis.overall_performance` is the assessment status. Weak topics and
Bloom levels are non-`Strong` groups. Strong topics are `Strong` groups. Weak
subtopics are subtopics attached to non-`Strong` questions.

### Next-question generation

The materialized document stores a request target rather than generated question
content because generated questions are not part of the canonical student JSON.
The request contains:

- a Qwen-recommended Bloom level;
- a Qwen-recommended difficulty;
- recommended weak topics/subtopics;
- `number_of_questions` fixed at 5.

The separate intelligent question generator can consume this target later.

## Model Metadata

`model_metadata` records:

- configured Bloom model name;
- configured model type;
- `grading_source` copied from submission evaluation metadata;
- `rag_context_used` copied from submission evaluation metadata.

Metadata reflects actual configuration and source values; it must not claim a
fine-tuned model when the configured runtime is a base model.

## Failure and Consistency Policy

- Missing rubric question, invalid marks, awarded marks greater than maximum marks,
  or non-positive maximum marks fails that student build before persistence.
- Model unavailability is recoverable through deterministic fallbacks.
- Invalid model JSON is treated the same as model unavailability.
- A persistence error is surfaced and does not intentionally modify the previous
  materialized document.
- Each student is processed independently; failures are collected and reported while
  other valid submissions continue.
- API responses never expose raw answer transcripts, Mongo `_id`, or another
  student's data.

## Verification Strategy

Tests cover:

1. Pydantic validation and exact serialized canonical shape.
2. Course, rubric, submission, question, and criterion joins.
3. Total, question, topic, and Bloom calculations without model involvement.
4. Status boundaries immediately below, at, and above 50 and 75 percent.
5. Qwen classification success and rule-based fallback.
6. Qwen insight success and deterministic fallback.
7. Classification reuse across multiple students.
8. Unique-index creation and idempotent `student_analytics` replacement.
9. Per-student failure isolation in batch processing.
10. Sample files producing one stored document per valid submission.
11. GET endpoint filters, latest-document selection, 404 behavior, and `_id` removal.

All automated tests used for this feature must remain offline and deterministic; live
model tests are excluded from the required verification command.

## Out of Scope

- Frontend changes.
- Authentication and authorization.
- Saving generated question content in the student document.
- Regrading answers or changing Colab grading output.
- Cohort-wide lecturer dashboard redesign.
