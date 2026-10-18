# Student Dashboard Design

Date: 2026-08-06
Status: Approved for planning

## Overview

Expose a per-student analytics dashboard through FastAPI REST endpoints so each
student can view their exam performance and identify how to improve. Today
`run_analytics` produces only cohort-level aggregates (`AnalyticsSnapshot`,
`ExamRecommendation`). The raw per-student signal already exists in
`question_attempts` (each attempt carries `student_key`, `bloom_level`,
`topic_assignments`, `normalized_score`, `criteria_breakdown`, `feedback`), so
the dashboard computes individual performance on-the-fly from those attempts.

The scope of this work is backend only: schemas + analytics math + service +
FastAPI endpoints that emit dashboard JSON. No frontend and no authentication
will be built now; the endpoint data is shaped for a future frontend.

## Decisions (from brainstorming)

- **Output**: REST API endpoints (FastAPI and uvicorn are already dependencies).
- **Identity**: no auth yet; the student is identified by `student_key` as a path
  parameter.
- **Contents**: grades (overall + per-question), cognitive/Bloom breakdown, topic
  strengths & weaknesses, missed criteria + feedback, cohort comparison, and
  study recommendations with exam-prep guidance.
- **Recommendations**: deterministic always; LLM `study_actions` role optional and
  called only when available (graceful degradation).
- **Recent**: recommendations are computed on-the-fly; the LLM call can be skipped
  via an `?include_llm` flag to avoid latency.

## Architecture

Six new files plus two small additions to the existing repository:

```
app/schemas/student.py                 Pydantic response models
app/analytics/student.py               Pure per-student math (no I/O)
app/services/student_dashboard.py      Orchestration (DB -> math -> optional LLM)
app/api/deps.py                        get_db() dependency
app/api/dashboard.py                   FastAPI router
app/main.py                            FastAPI app including the router
app/db/repository.py                   (modified) new query helpers
```

Boundaries:

| Unit                    | What it does                                      | Depends on |
|-------------------------|---------------------------------------------------|------------|
| `schemas/student.py`    | Declares the dashboard response shape             | pydantic, schemas.catalog |
| `analytics/student.py`  | Pure math: exam perf, bloom/topic profile, ranks  | schemas/student, analytics/mastery, analytics/recommender |
| `services/student_dashboard.py` | Read attempts, call math, call optional LLM, assemble | db/repository, analytics/student, services/llm_service |
| `api/deps.py`           | Provide a Mongo DB session                        | config |
| `api/dashboard.py`      | HTTP routes                                        | services/student_dashboard, api/deps |

## Endpoint

```
GET /api/students/{student_key}/dashboard?run_id=<optional>&include_llm=<bool>
```

Response model: `StudentDashboard` (below). Query params:

- `run_id`: optional; when omitted, the latest analysis run for the course is used.
- `include_llm`: optional, default `false`; when `true`, the service attempts the
  LLM study recommendations and returns them on success, otherwise returns
  deterministic recommendations.

## Data model

All new models live in `app/schemas/student.py`.

```python
class MissedCriterion(BaseModel):
    criterion: str
    awarded_marks: float
    max_marks: float

class QuestionPerformance(BaseModel):
    question_id: str
    question_number: str
    part: str
    question_text: str
    topic: str
    bloom_level: str
    question_type: str
    awarded_marks: float
    max_marks: float
    normalized_score: float
    passed: bool
    feedback: str
    missed_criteria: list[MissedCriterion]

class StudentExamPerformance(BaseModel):
    exam_id: str
    total_awarded: float
    total_max: float
    percentage: float
    grade: str
    attempt_count: int
    question_performances: list[QuestionPerformance]

class StudentBloomSkill(BaseModel):
    bloom_level: str
    mastery: float | None
    mean: float | None
    attempt_count: int
    evidence_status: str

class StudentTopicSkill(BaseModel):
    topic: str
    mastery: float | None
    mean: float | None
    attempt_count: int
    evidence_status: str
    rank: int                       # 1 = weakest
    priority_score: float           # from weakness_component

class StudentStudyAction(BaseModel):
    action: str
    topic: str
    rationale: str
    practice_topics: list[str]
    source: Literal["llm", "deterministic"]

class StudentDashboard(BaseModel):
    student_key: str
    course_code: str
    run_id: str
    generated_at: datetime
    exams: list[StudentExamPerformance]
    bloom_skills: list[StudentBloomSkill]
    topic_skills: list[StudentTopicSkill]
    weakest_topics: list[str]
    cohort_comparison: dict
    recommendations: list[StudentStudyAction]
```

The response is grouped by exam (each exam is its own `StudentExamPerformance`),
giving both overall and per-question views.

## Analytics math (`app/analytics/student.py`)

Reuses the existing per-cohort math unchanged by filtering attempts to one
student first:

- Mastery per topic/Bloom uses `compute_mastery` and `_qualifying` from
  `app/analytics/mastery.py`.
- Weakness ranking uses `weakness_component` from `app/analytics/recommender.py`.
- Grade bands derived from the course `pass_threshold`:
  - A: >= 0.85
  - B: >= 0.70
  - C: >= 0.55
  - D: >= pass_threshold
  - F: below pass_threshold

Functions (all pure, take attempt dicts):

```python
student_exam_performance(attempts, pass_threshold) -> StudentExamPerformance
question_performance(attempt, pass_threshold)       -> QuestionPerformance
bloom_skill_profile(student_attempts)                -> list[StudentBloomSkill]
topic_skill_profile(student_attempts, topic_importance=None) -> list[StudentTopicSkill]
rank_weakest_topics(topic_skills)                    -> list[str]
deterministic_study_actions(weakest_topics)          -> list[StudentStudyAction]
cohort_comparison(student_attempts, all_attempts)    -> dict
```

`cohort_comparison` computes per-bloom and per-topic: student mastery vs cohort
mastery, plus a percentile (fraction of cohort members scoring below the
student).

## Service layer (`app/services/student_dashboard.py`)

```python
async def build_student_dashboard(db, student_key, run_id=None, include_llm=False) -> StudentDashboard
```

Steps:
1. Resolve `run_id` (query param, else `latest_run_id(db)`); raise NotFound if absent.
2. Load the student's attempts (repository helper) and all attempts (for the cohort).
3. Build the deterministic sections.
4. If `include_llm` and Ollama is reachable, call the existing `llm_service.study_actions`; on success mark `source="llm"`, otherwise keep the deterministic actions and log.
5. Assemble and return the `StudentDashboard`.

`deterministic_study_actions` produces canned "Review" / "Practice" / "Revisit"
actions keyed to the weakest topics so the dashboard always has recommendations.

## Repository additions (`app/db/repository.py`)

```python
async def find_attempts_by_student(db, run_id, student_key) -> list[dict]
async def latest_run_id(db, course_code=None) -> str | None
```

`latest_run_id` reads the most recently created `analysis_runs` document.

## Error handling

- Unknown `student_key` (no attempts) -> `404` with detail message.
- `run_id` not found -> `404`.
- Mongo unavailable -> `500`, logged, does not leak stack traces.
- Ollama unavailable while `include_llm=true` -> dashboard still returns fully with
  `source="deterministic"`.
- Invalid `student_key` (path traversal chars) -> 422 via FastAPI path validation.

## Testing

Add tests using the existing `test_db` fixture and deterministic fixtures
(`tests/fixtures/fixture_data.py`, 12 students / 2 exams):

- `tests/test_student_analytics.py` — pure functions: exam performance math and
  grades, bloom/topic profile, weakest ranking, deterministic actions, cohort
  comparison. Expectations hand-computed from the fixture data.
- `tests/test_student_dashboard_service.py` — build a dashboard from
  `sample_submissions`; assert all sections present; verify LLM and deterministic
  recommendation sources via monkeypatch; verify run/student not-found behavior.
- `tests/test_api_dashboard.py` — `fastapi.testclient` with the test Mongo DB:
  endpoint happy path, schema, 404 for missing student/run, and deterministic
  fallback when Ollama is off.

## Out of scope

- Frontend / UI.
- Authentication / login / authorization.
- Persisting per-student dashboards (computed on demand).
- Any change to the existing `run_analytics` cohort pipeline.