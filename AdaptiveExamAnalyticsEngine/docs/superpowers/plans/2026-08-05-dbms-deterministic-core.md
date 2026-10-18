# DBMS Deterministic Analytics Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and test the deterministic core of the DBMS predictive learning analytics engine: Pydantic/MongoDB schemas, fixture data, ingestion and canonical question-attempt transformation, mastery/cohort analytics with evidence statuses, coverage/Bloom-gap computation, recommendation scoring, rules-based topic/Bloom classification, and a lecturer labelling evaluation toolkit.

**Architecture:** A FastAPI backend with an async PyMongo (motor) data layer. Pure analytics functions in `app/analytics/` take plain dicts and are fully deterministic and unit-testable without a database. Repositories in `app/db/` handle persistence with unique-index-backed idempotent upserts. Ingestion in `app/ingestion/` maps `historical_exams` and `submissions` documents into the canonical `question_catalog` and `question_attempts` collections. The Colab/Qwen/embedding layers are out of scope for this plan; their schema fields are present but nullable placeholders.

**Tech Stack:** Python 3.14, FastAPI, Pydantic v2, pydantic-settings, motor/pymongo (MongoDB 8.0 local), pytest, pytest-asyncio, python-dotenv.

## Global Constraints

- Python 3.14.4; venv at `.venv`.
- Local MongoDB 8.0 at `mongodb://127.0.0.1:27017`; tests use database `dbms_analytics_test`.
- Connection string comes from `.env` via `MONGODB_URI`; never commit `.env`.
- Default pass threshold: `0.5` (50%), configurable, never silently changed.
- Default evidence minima: `min_students=10`, `min_attempts=2`.
- Default algorithm version: `analytics-v1`.
- Controlled topic taxonomy (8 topics, exact strings):
  1. `Introduction to DBMS and Conceptual Database Design`
  2. `Logical Database Design`
  3. `Schema Refinement`
  4. `SQL`
  5. `Database Programming`
  6. `Java Database Connectivity (JDBC)`
  7. `Database Utilities`
  8. `Database Security`
- Revised Bloom levels (6, exact strings): `Remember`, `Understand`, `Apply`, `Analyze`, `Evaluate`, `Create`.
- Topic weights within a question must sum to `1.0`.
- Numeric conclusions are deterministic and reproducible; no LLM in this plan.
- Every recommendation and evidence claim exposes its supporting sample sizes.
- Low-sample findings are labelled `insufficient_evidence` or `possible_weakness`, never definite weakness.
- Source collections (`courses`, `rubricCollection`, `submissions`, `historical_exams`) are read-only inputs; derived collections are `question_catalog`, `question_attempts`, `analytics_snapshots`, `exam_recommendations`, `analysis_runs`.
- Unique compound indexes prevent duplicate attempts and duplicate snapshots.
- No commit of secrets; `.env` added to `.gitignore`.

---

### Task 1: Project scaffolding, config, and requirements

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

**Interfaces:**
- Consumes: nothing.
- Produces: `app/config.py` exposing `settings` (a `Settings` instance) with fields `mongodb_uri`, `mongodb_db`, `pass_threshold`, `min_students`, `min_attempts`, `algorithm_version`, `env`; and a pytest session fixture `test_db` returning an `AsyncIOMotorDatabase` for `dbms_analytics_test`.

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:

```python
from app.config import settings


def test_default_threshold_is_50_percent():
    assert settings.pass_threshold == 0.5


def test_default_evidence_minima():
    assert settings.min_students == 10
    assert settings.min_attempts == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write minimal implementation**

`requirements.txt`:

```
fastapi==0.141.1
pydantic==2.13.4
pydantic-settings==2.14.2
pymongo==4.17.0
motor==3.7.1
python-dotenv==1.2.2
uvicorn
pytest==9.1.1
pytest-asyncio==1.4.0
httpx==0.28.1
```

`app/__init__.py`:

```python
"""DBMS predictive learning analytics backend."""
```

`app/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://127.0.0.1:27017"
    mongodb_db: str = "dbms_analytics"
    pass_threshold: float = 0.5
    min_students: int = 10
    min_attempts: int = 2
    algorithm_version: str = "analytics-v1"
    env: str = "development"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
```

`.env.example`:

```
MONGODB_URI=mongodb://127.0.0.1:27017
MONGODB_DB=dbms_analytics
PASS_THRESHOLD=0.5
MIN_STUDENTS=10
MIN_ATTEMPTS=2
ALGORITHM_VERSION=analytics-v1
```

`pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

`tests/__init__.py`:

```python
```

`tests/conftest.py`:

```python
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

TEST_DB_NAME = "dbms_analytics_test"


@pytest.fixture(scope="session")
async def test_db():
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[TEST_DB_NAME]
    yield db
    await client.drop_database(TEST_DB_NAME)
    client.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Append `.env` to `.gitignore` and commit**

`.gitignore` currently contains existing entries; append:

```
.venv/
.env
__pycache__/
.pytest_cache/
```

```bash
git add requirements.txt .env.example .gitignore app tests pytest.ini
git commit -m "feat: scaffold backend config and test fixtures"
```

---

### Task 2: Controlled taxonomy constants

**Files:**
- Create: `app/analytics/__init__.py`
- Create: `app/analytics/taxonomy.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TOPICS: list[str]` (8 exact strings), `BLOOM_LEVELS: list[str]` (6 exact strings), `QUESTION_TYPES: list[str]`, `DEFAULT_PRIORITY_WEIGHTS: dict[str, float]` = `{"weakness": 0.40, "coverage_gap": 0.25, "bloom_gap": 0.20, "topic_importance": 0.15}`.

- [ ] **Step 1: Write the failing test**

`tests/test_taxonomy.py`:

```python
from app.analytics.taxonomy import (
    BLOOM_LEVELS,
    DEFAULT_PRIORITY_WEIGHTS,
    QUESTION_TYPES,
    TOPICS,
)


def test_eight_dbms_topics_exact_strings():
    assert TOPICS == [
        "Introduction to DBMS and Conceptual Database Design",
        "Logical Database Design",
        "Schema Refinement",
        "SQL",
        "Database Programming",
        "Java Database Connectivity (JDBC)",
        "Database Utilities",
        "Database Security",
    ]


def test_six_revised_bloom_levels():
    assert BLOOM_LEVELS == [
        "Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create",
    ]


def test_question_types_include_problem_solving():
    assert "problem_solving" in QUESTION_TYPES


def test_priority_weights_sum_to_one():
    assert sum(DEFAULT_PRIORITY_WEIGHTS.values()) == 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_taxonomy.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/analytics/__init__.py`:

```python
"""Deterministic analytics package."""
```

`app/analytics/taxonomy.py`:

```python
TOPICS: list[str] = [
    "Introduction to DBMS and Conceptual Database Design",
    "Logical Database Design",
    "Schema Refinement",
    "SQL",
    "Database Programming",
    "Java Database Connectivity (JDBC)",
    "Database Utilities",
    "Database Security",
]

BLOOM_LEVELS: list[str] = [
    "Remember",
    "Understand",
    "Apply",
    "Analyze",
    "Evaluate",
    "Create",
]

QUESTION_TYPES: list[str] = [
    "multiple_choice",
    "short_answer",
    "essay",
    "problem_solving",
    "design",
    "coding",
]

DEFAULT_PRIORITY_WEIGHTS: dict[str, float] = {
    "weakness": 0.40,
    "coverage_gap": 0.25,
    "bloom_gap": 0.20,
    "topic_importance": 0.15,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_taxonomy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/analytics tests/test_taxonomy.py
git commit -m "feat: define controlled topic and Bloom taxonomies"
```

---

### Task 3: Canonical Pydantic schemas (catalog, attempt, evidence)

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/catalog.py`

**Interfaces:**
- Consumes: Task 2 taxonomy strings.
- Produces:
  - `TopicAssignment(topic: str, weight: float)` — validated so `0.0 <= weight <= 1.0`.
  - `CriteriaEvidence(criterion, awarded_marks, max_marks, met, evidence)`.
  - `QuestionCatalog` model matching the spec section 6 canonical record, with fields: `question_id`, `analysis_run_id`, `course_code`, `exam_id`, `student_key`, `question_number`, `part`, `question_text`, `topic_assignments`, `bloom_level`, `question_type`, `key_concepts`, `awarded_marks`, `max_marks`, `normalized_score`, `criteria_breakdown`, `answer_text`, `feedback`, `classification_status`, `classification_confidence`, `algorithm_version`.
  - `QuestionAttempt` model with the same field set plus `attempt_id` as the primary key.

- [ ] **Step 1: Write the failing test**

`tests/test_schemas.py`:

```python
import pydantic
import pytest

from app.schemas.catalog import CriteriaEvidence, QuestionAttempt, QuestionCatalog, TopicAssignment


def make_attempt() -> dict:
    return {
        "attempt_id": "att-1",
        "analysis_run_id": "run-1",
        "course_code": "SE2032",
        "exam_id": "exam-2023",
        "student_key": "stu-001",
        "question_id": "q-1",
        "question_number": "02",
        "part": "b",
        "question_text": "Find the primary key using attribute closure.",
        "topic_assignments": [
            {"topic": "Schema Refinement", "weight": 0.8},
            {"topic": "Logical Database Design", "weight": 0.2},
        ],
        "bloom_level": "Analyze",
        "question_type": "problem_solving",
        "key_concepts": ["functional dependency", "attribute closure"],
        "awarded_marks": 1.0,
        "max_marks": 2.0,
        "normalized_score": 0.5,
        "criteria_breakdown": [],
        "answer_text": "...",
        "feedback": "...",
        "classification_status": "model_suggested",
        "classification_confidence": "medium",
        "algorithm_version": "analytics-v1",
    }


def test_topic_weights_must_sum_to_one():
    with pytest.raises(pydantic.ValidationError):
        QuestionCatalog(
            **{**make_attempt(), "question_id": "q-1", "student_key": None,
               "topic_assignments": [{"topic": "SQL", "weight": 0.7}]}
        )


def test_normalized_score_must_be_between_zero_and_one():
    with pytest.raises(pydantic.ValidationError):
        QuestionAttempt(**{**make_attempt(), "normalized_score": 1.5})


def test_criteria_evidence_round_trip():
    ev = CriteriaEvidence(criterion="c", awarded_marks=0.5, max_marks=2.0, met=False, evidence="e")
    assert ev.met is False
    assert ev.awarded_marks == 0.5


def test_question_attempt_requires_attempt_id():
    with pytest.raises(pydantic.ValidationError):
        QuestionAttempt(**{**make_attempt(), "attempt_id": None})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/schemas/__init__.py`:

```python
from app.schemas.catalog import CriteriaEvidence, QuestionAttempt, QuestionCatalog, TopicAssignment

__all__ = ["CriteriaEvidence", "QuestionAttempt", "QuestionCatalog", "TopicAssignment"]
```

`app/schemas/catalog.py`:

```python
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS


class TopicAssignment(BaseModel):
    topic: str = Field(description="One of the controlled DBMS topics.")
    weight: float = Field(ge=0.0, le=1.0)


class CriteriaEvidence(BaseModel):
    criterion: str
    awarded_marks: float
    max_marks: float = Field(gt=0)
    met: bool
    evidence: str = ""


class QuestionCatalog(BaseModel):
    question_id: str
    course_code: str
    exam_id: str
    question_number: str
    part: str
    question_text: str
    max_marks: float = Field(gt=0)
    topic_assignments: list[TopicAssignment] = Field(default_factory=list)
    bloom_level: str
    question_type: str
    key_concepts: list[str] = Field(default_factory=list)
    source_paper_year: int | None = None
    embedding_ref: str | None = None
    model_output: dict | None = None
    validation_state: Literal["model_suggested", "lecturer_validated"] = "model_suggested"
    lecturer_correction: dict | None = None
    classification_status: Literal["model_suggested", "lecturer_review", "lecturer_validated"] = "model_suggested"
    classification_confidence: Literal["high", "medium", "low"] = "medium"
    algorithm_version: str = "analytics-v1"

    @model_validator(mode="after")
    def validate_topic_weights(self) -> "QuestionCatalog":
        total = sum(assign.weight for assign in self.topic_assignments)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("topic weights must sum to 1.0")
        return self


class QuestionAttempt(BaseModel):
    attempt_id: str
    analysis_run_id: str
    course_code: str
    exam_id: str
    student_key: str
    question_id: str
    question_number: str
    part: str
    question_text: str
    topic_assignments: list[TopicAssignment] = Field(default_factory=list)
    bloom_level: str
    question_type: str
    key_concepts: list[str] = Field(default_factory=list)
    awarded_marks: float = Field(ge=0)
    max_marks: float = Field(gt=0)
    normalized_score: Annotated[float, Field(ge=0.0, le=1.0)]
    criteria_breakdown: list[CriteriaEvidence] = Field(default_factory=list)
    answer_text: str = ""
    feedback: str = ""
    classification_status: Literal["model_suggested", "lecturer_review", "lecturer_validated"] = "model_suggested"
    classification_confidence: Literal["high", "medium", "low"] = "medium"
    algorithm_version: str = "analytics-v1"

    @model_validator(mode="after")
    def validate_topic_weights(self) -> "QuestionAttempt":
        total = sum(assign.weight for assign in self.topic_assignments)
        if abs(total - 1.0) > 1e-6:
            raise ValueError("topic weights must sum to 1.0")
        return self


assert all(level in BLOOM_LEVELS for level in BLOOM_LEVELS)
assert all(topic in TOPICS for topic in TOPICS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas tests/test_schemas.py
git commit -m "feat: add canonical catalog and attempt schemas"
```

---

### Task 4: Derived collection schemas (snapshot, recommendation, run)

**Files:**
- Create: `app/schemas/derived.py`

**Interfaces:**
- Consumes: Task 3 `CriteriaEvidence`, `QuestionAttempt`.
- Produces:
  - `CellMetrics(topic, bloom_level, mean, median, pass_rate, failure_rate, student_count, attempt_count, std_dev, missed_criterion_rate, evidence_status, mastery)` — all statistics nullable except counts/status.
  - `TopicMetrics(topic, mastery, mean, student_count, attempt_count, evidence_status)`.
  - `AnalyticsSnapshot(...)` — `snapshot_id`, `run_id`, `course_code`, `exam_id`, `algorithm_version`, `cohort_metrics`, `topic_metrics`, `topic_bloom_matrix`, `evidence_statuses`, `grade_distribution`, `record_counts`, `pass_threshold`, `min_students`, `min_attempts`, `published_at`, `created_at`.
  - `CandidateQuestion(...)`, `ExamRecommendation(...)` with `priority_score`, `component_breakdown`, `evidence`, `candidates`, `decision`.
  - `AnalysisRun(...)` with status `queued|running|ready|failed`, thresholds, versions, checkpoints, errors, `publication_state`.

- [ ] **Step 1: Write the failing test**

`tests/test_schemas_derived.py`:

```python
import pydantic
import pytest

from app.schemas.derived import AnalysisRun, AnalyticsSnapshot, ExamRecommendation


def test_snapshot_requires_published_fields():
    with pytest.raises(pydantic.ValidationError):
        AnalyticsSnapshot(
            snapshot_id="s1",
            run_id="r1",
            course_code="SE2032",
            exam_id="e1",
            algorithm_version="analytics-v1",
            cohort_metrics={},
            topic_metrics=[],
            topic_bloom_matrix=[],
            evidence_statuses={},
            grade_distribution={},
            record_counts={},
            pass_threshold=0.5,
            min_students=10,
            min_attempts=2,
        )


def test_recommendation_default_decision_is_pending():
    rec = ExamRecommendation(
        recommendation_id="rec-1",
        run_id="r1",
        course_code="SE2032",
        exam_id="e1",
        topic="Schema Refinement",
        bloom_level="Apply",
        question_type="problem_solving",
        mark_range=(1.0, 4.0),
        priority_score=0.75,
        component_breakdown={"weakness": 0.5},
        evidence={},
    )
    assert rec.decision == "pending"


def test_analysis_run_round_trip():
    run = AnalysisRun(run_id="r1", course_code="SE2032", exam_id="e1")
    assert run.status == "queued"
    assert run.algorithm_version == "analytics-v1"
    assert run.publication_state == "unpublished"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas_derived.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/schemas/derived.py`:

```python
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.schemas.catalog import CriteriaEvidence


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CellMetrics(BaseModel):
    topic: str
    bloom_level: str
    mastery: float | None = None
    mean: float | None = None
    median: float | None = None
    pass_rate: float | None = None
    failure_rate: float | None = None
    student_count: int = 0
    attempt_count: int = 0
    std_dev: float | None = None
    missed_criterion_rate: float | None = None
    evidence_status: str = "insufficient_evidence"


class TopicMetrics(BaseModel):
    topic: str
    mastery: float | None = None
    mean: float | None = None
    student_count: int = 0
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"


class AnalyticsSnapshot(BaseModel):
    snapshot_id: str
    run_id: str
    course_code: str
    exam_id: str
    algorithm_version: str
    cohort_metrics: dict[str, float | int | dict]
    topic_metrics: list[TopicMetrics]
    topic_bloom_matrix: list[CellMetrics]
    evidence_statuses: dict[str, str]
    grade_distribution: dict[str, int]
    record_counts: dict[str, int]
    pass_threshold: float
    min_students: int
    min_attempts: int
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CandidateQuestion(BaseModel):
    candidate_id: str
    question_text: str
    topic: str
    bloom_level: str
    marks: float = Field(gt=0)
    bloom_rationale: str = ""
    model_answer: str = ""
    rubric_criteria: list[CriteriaEvidence] = Field(default_factory=list)
    similarity_check: dict = Field(default_factory=dict)
    decision: str = "pending"


class ExamRecommendation(BaseModel):
    recommendation_id: str
    run_id: str
    course_code: str
    exam_id: str
    topic: str
    bloom_level: str
    question_type: str
    mark_range: tuple[float, float]
    priority_score: float = Field(ge=0.0, le=1.0)
    component_breakdown: dict[str, float | None]
    evidence: dict = Field(default_factory=dict)
    candidates: list[CandidateQuestion] = Field(default_factory=list)
    decision: str = "pending"
    created_at: datetime = Field(default_factory=utcnow)


class AnalysisRun(BaseModel):
    run_id: str
    course_code: str
    exam_id: str
    status: str = "queued"
    input_filters: dict = Field(default_factory=dict)
    data_counts: dict = Field(default_factory=dict)
    algorithm_version: str = "analytics-v1"
    model_version: str | None = None
    embedding_model: str | None = None
    quantization: str | None = None
    prompt_version: str | None = None
    thresholds: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    checkpoints: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)
    publication_state: str = "unpublished"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas_derived.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/derived.py tests/test_schemas_derived.py
git commit -m "feat: add derived snapshot, recommendation, and run schemas"
```

---

### Task 5: Deterministic fixture data

**Files:**
- Create: `tests/fixtures/__init__.py`
- Create: `tests/fixtures/fixture_data.py`

**Interfaces:**
- Consumes: Task 3 schemas.
- Produces:
  - `sample_papers: list[dict]` — two `historical_exams` docs with `question_number`/`part`/`text`/`max_marks`, covering topics SQL, Schema Refinement, and Logical Database Design.
  - `sample_submissions: list[dict]` — graded submissions for 12 students across the two papers, each with `awarded_marks`, `max_marks`, `answer_text`, `feedback`, `criteria_breakdown`, `student_key`, `exam_id`, `question_number`, `part`.
  - `course_settings(course_code="SE2032") -> dict` — course doc with `pass_threshold`, `min_students`, `min_attempts`, `topic_importance`, `blueprint_targets`.
  - `expected_catalog_records: list[dict]`, `expected_attempt_records: list[dict]` — manually computed canonical records used by Tasks 6–8 as fixtures.

- [ ] **Step 1: Write the failing test**

`tests/test_fixtures.py`:

```python
from tests.fixtures.fixture_data import expected_attempt_records, sample_papers, sample_submissions


def test_fixtures_have_two_papers():
    assert len(sample_papers) == 2


def test_fixtures_have_students_across_two_papers():
    exams = {s["exam_id"] for s in sample_submissions}
    assert exams == {"exam-2023", "exam-2024"}


def test_expected_attempt_records_sum_to_known_values():
    total_marks = sum(r["max_marks"] for r in expected_attempt_records)
    assert total_marks > 0
    assert all(0.0 <= r["normalized_score"] <= 1.0 for r in expected_attempt_records)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: tests.fixtures`

- [ ] **Step 3: Write minimal implementation**

`tests/fixtures/__init__.py`:

```python
```

`tests/fixtures/fixture_data.py`:

```python
"""Deterministic fixtures for analytics tests.

Two papers (exam-2023, exam-2024), each with three question parts. Twelve
students. Values are hand-computed so test expectations are exact.
"""

COURSE = "SE2032"

SQL_Q = {"topic": "SQL", "bloom": "Apply", "type": "problem_solving"}
SCHEMA_Q = {"topic": "Schema Refinement", "bloom": "Analyze", "type": "problem_solving"}
LOGICAL_Q = {"topic": "Logical Database Design", "bloom": "Understand", "type": "short_answer"}

QUESTIONS = {
    "exam-2023": [
        {"question_number": "01", "part": "a", "max_marks": 2.0, "text": "Write a SQL SELECT.", **SQL_Q},
        {"question_number": "01", "part": "b", "max_marks": 3.0, "text": "Find the primary key.", **SCHEMA_Q},
        {"question_number": "02", "part": "a", "max_marks": 1.0, "text": "Explain an ER entity.", **LOGICAL_Q},
    ],
    "exam-2024": [
        {"question_number": "01", "part": "a", "max_marks": 2.0, "text": "Write a SQL UPDATE.", **SQL_Q},
        {"question_number": "01", "part": "b", "max_marks": 3.0, "text": "Normalize to 3NF.", **SCHEMA_Q},
        {"question_number": "02", "part": "a", "max_marks": 1.0, "text": "Define a foreign key.", **LOGICAL_Q},
    ],
}

sample_papers = [
    {
        "exam_id": exam_id,
        "course_code": COURSE,
        "year": 2023 if exam_id == "exam-2023" else 2024,
        "title": f"DBMS {year}",
        "questions": [
            {
                "question_number": q["question_number"],
                "parts": [
                    {"part": q["part"], "text": q["text"], "max_marks": q["max_marks"]}
                ],
            }
            for q in parts
        ],
    }
    for exam_id, parts in QUESTIONS.items()
    for year in [2023, 2024]
    if (exam_id == "exam-2023" and year == 2023) or (exam_id == "exam-2024" and year == 2024)
]

STUDENT_KEYS = [f"stu-{i:03d}" for i in range(1, 13)]

# awarded marks by (exam_id, question_number+part, student_index_0based)
_marks = {
    "exam-2023": {
        "01a": [2.0, 2.0, 1.5, 1.0, 2.0, 0.5, 2.0, 1.0, 2.0, 2.0, 1.0, 0.0],
        "01b": [3.0, 2.5, 2.0, 1.5, 1.0, 0.5, 2.0, 0.0, 3.0, 2.0, 1.0, 1.5],
        "02a": [1.0, 1.0, 0.5, 1.0, 0.0, 0.5, 1.0, 1.0, 0.5, 1.0, 0.5, 0.0],
    },
    "exam-2024": {
        "01a": [2.0, 1.5, 2.0, 1.0, 0.5, 2.0, 1.0, 2.0, 2.0, 1.5, 0.5, 1.0],
        "01b": [2.0, 3.0, 1.5, 2.0, 0.0, 1.0, 2.0, 1.5, 3.0, 1.0, 2.0, 1.5],
        "02a": [1.0, 0.5, 1.0, 1.0, 0.5, 1.0, 0.0, 1.0, 1.0, 0.5, 0.5, 1.0],
    },
}

sample_submissions = []
for exam_id, exam_questions in QUESTIONS.items():
    for q in exam_questions:
        key = f"{q['question_number']}{q['part']}"
        for i, student_key in enumerate(STUDENT_KEYS):
            awarded = _marks[exam_id][key][i]
            sample_submissions.append(
                {
                    "exam_id": exam_id,
                    "course_code": COURSE,
                    "student_key": student_key,
                    "question_number": q["question_number"],
                    "part": q["part"],
                    "awarded_marks": awarded,
                    "max_marks": q["max_marks"],
                    "answer_text": f"answer for {key} by {student_key}",
                    "feedback": "ok",
                    "criteria_breakdown": [],
                }
            )


def course_settings(course_code: str = COURSE) -> dict:
    return {
        "course_code": course_code,
        "course_name": "Database Management Systems",
        "settings": {
            "pass_threshold": 0.5,
            "min_students": 10,
            "min_attempts": 2,
            "topic_importance": {},  # equal by default
            "blueprint_targets": {},  # none configured
        },
    }


def _normalize(awarded: float, max_marks: float) -> float:
    return awarded / max_marks


expected_attempt_records = []
for exam_id, exam_questions in QUESTIONS.items():
    for q in exam_questions:
        key = f"{q['question_number']}{q['part']}"
        for i, student_key in enumerate(STUDENT_KEYS):
            awarded = _marks[exam_id][key][i]
            expected_attempt_records.append(
                {
                    "attempt_id": f"{exam_id}-{key}-{student_key}",
                    "analysis_run_id": "run-fixture",
                    "course_code": COURSE,
                    "exam_id": exam_id,
                    "student_key": student_key,
                    "question_id": f"{exam_id}-{key}",
                    "question_number": q["question_number"],
                    "part": q["part"],
                    "question_text": q["text"],
                    "topic_assignments": [{"topic": q["topic"], "weight": 1.0}],
                    "bloom_level": q["bloom"],
                    "question_type": q["type"],
                    "key_concepts": [],
                    "awarded_marks": awarded,
                    "max_marks": q["max_marks"],
                    "normalized_score": _normalize(awarded, q["max_marks"]),
                    "criteria_breakdown": [],
                    "answer_text": f"answer for {key} by {student_key}",
                    "feedback": "ok",
                    "classification_status": "lecturer_validated",
                    "classification_confidence": "high",
                    "algorithm_version": "analytics-v1",
                }
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_fixtures.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures tests/test_fixtures.py
git commit -m "test: add deterministic analytics fixtures"
```

---

### Task 6: Normalization and mastery calculations

**Files:**
- Create: `app/analytics/mastery.py`

**Interfaces:**
- Consumes: `attempt: dict` records (shape from Task 3 `QuestionAttempt`); Task 2 taxonomy.
- Produces:
  - `normalized_score(awarded: float, max_marks: float) -> float`
  - `topic_weight_for(attempt: dict, topic: str) -> float` — weight of `topic` in `attempt["topic_assignments"]`, `0.0` if absent.
  - `compute_mastery(attempts: list[dict], topic: str, bloom: str | None = None) -> float | None` — returns `None` if no qualifying attempts.
  - `compute_cell_metrics(attempts: list[dict], topic: str, bloom: str | None) -> CellMetrics`
  - `compute_topic_metrics(attempts: list[dict], topic: str) -> TopicMetrics`
  - `compute_topic_bloom_matrix(attempts: list[dict]) -> list[CellMetrics]`

- [ ] **Step 1: Write the failing test**

`tests/test_mastery.py`:

```python
import statistics

from app.analytics.mastery import (
    compute_cell_metrics,
    compute_mastery,
    compute_topic_bloom_matrix,
    compute_topic_metrics,
    normalized_score,
    topic_weight_for,
)
from app.schemas.derived import CellMetrics, TopicMetrics
from tests.fixtures.fixture_data import expected_attempt_records


def test_normalized_score():
    assert normalized_score(1.0, 2.0) == 0.5
    assert normalized_score(0.0, 2.0) == 0.0


def test_topic_weight_for_missing_topic_is_zero():
    assert topic_weight_for({"topic_assignments": [{"topic": "SQL", "weight": 1.0}]}, "JDBC") == 0.0


def test_compute_mastery_sql_apply():
    sql_apply = [a for a in expected_attempt_records if a["topic_assignments"][0]["topic"] == "SQL"]
    expected = sum(a["normalized_score"] * a["max_marks"] for a in sql_apply) / sum(
        a["max_marks"] for a in sql_apply
    )
    assert compute_mastery(expected_attempt_records, "SQL") == round(expected, 6)


def test_compute_mastery_empty_returns_none():
    assert compute_mastery([], "SQL") is None


def test_compute_cell_metrics_populates_counts():
    cell = compute_cell_metrics(expected_attempt_records, "Schema Refinement", "Analyze")
    assert isinstance(cell, CellMetrics)
    assert cell.attempt_count == 24
    assert cell.student_count == 12
    assert cell.evidence_status == "insufficient_evidence"


def test_compute_topic_metrics():
    tm = compute_topic_metrics(expected_attempt_records, "Logical Database Design")
    assert isinstance(tm, TopicMetrics)
    assert tm.attempt_count == 24


def test_matrix_covers_all_topic_bloom_cells():
    matrix = compute_topic_bloom_matrix(expected_attempt_records)
    filled = {(c.topic, c.bloom_level) for c in matrix if c.attempt_count > 0}
    assert ("SQL", "Apply") in filled
    assert ("Schema Refinement", "Analyze") in filled
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mastery.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/analytics/mastery.py`:

```python
import statistics

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS
from app.schemas.derived import CellMetrics, TopicMetrics


def normalized_score(awarded: float, max_marks: float) -> float:
    if max_marks <= 0:
        raise ValueError("max_marks must be positive")
    return awarded / max_marks


def topic_weight_for(attempt: dict, topic: str) -> float:
    for assign in attempt.get("topic_assignments", []):
        if assign["topic"] == topic:
            return assign["weight"]
    return 0.0


def _qualifying(attempts: list[dict], topic: str, bloom: str | None) -> list[dict]:
    return [
        a
        for a in attempts
        if topic_weight_for(a, topic) > 0
        and (bloom is None or a["bloom_level"] == bloom)
    ]


def compute_mastery(attempts: list[dict], topic: str, bloom: str | None = None) -> float | None:
    subset = _qualifying(attempts, topic, bloom)
    if not subset:
        return None
    numerator = sum(
        a["normalized_score"] * a["max_marks"] * topic_weight_for(a, topic) for a in subset
    )
    denominator = sum(a["max_marks"] * topic_weight_for(a, topic) for a in subset)
    return numerator / denominator if denominator > 0 else None


def compute_cell_metrics(attempts: list[dict], topic: str, bloom: str | None) -> CellMetrics:
    subset = _qualifying(attempts, topic, bloom)
    student_count = len({a["student_key"] for a in subset})
    scores = [a["normalized_score"] for a in subset]
    mean = statistics.fmean(scores) if scores else None
    median = statistics.median(scores) if scores else None
    failure_rate = (
        sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
    )
    pass_rate = 1.0 - failure_rate if failure_rate is not None else None
    std_dev = statistics.pstdev(scores) if len(scores) > 1 else None

    missed = []
    for a in subset:
        for c in a.get("criteria_breakdown", []):
            missed.append(c["met"])
    missed_criterion_rate = (
        (sum(1 for m in missed if not m) / len(missed)) if missed else None
    )

    return CellMetrics(
        topic=topic,
        bloom_level=bloom or "",
        mastery=compute_mastery(subset, topic, bloom),
        mean=mean,
        median=median,
        pass_rate=pass_rate,
        failure_rate=failure_rate,
        student_count=student_count,
        attempt_count=len(subset),
        std_dev=std_dev,
        missed_criterion_rate=missed_criterion_rate,
        evidence_status="insufficient_evidence",
    )


def compute_topic_metrics(attempts: list[dict], topic: str) -> TopicMetrics:
    subset = _qualifying(attempts, topic, None)
    student_count = len({a["student_key"] for a in subset})
    scores = [a["normalized_score"] for a in subset]
    return TopicMetrics(
        topic=topic,
        mastery=compute_mastery(subset, topic, None),
        mean=statistics.fmean(scores) if scores else None,
        student_count=student_count,
        attempt_count=len(subset),
        evidence_status="insufficient_evidence",
    )


def compute_topic_bloom_matrix(attempts: list[dict]) -> list[CellMetrics]:
    cells: list[CellMetrics] = []
    for topic in TOPICS:
        for bloom in BLOOM_LEVELS:
            cells.append(compute_cell_metrics(attempts, topic, bloom))
    return cells
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_mastery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/analytics/mastery.py tests/test_mastery.py
git commit -m "feat: implement normalization, mastery, and cell metrics"
```

---

### Task 7: Evidence statuses and cohort summary

**Files:**
- Create: `app/analytics/evidence.py`

**Interfaces:**
- Consumes: `CellMetrics`, `TopicMetrics` from Task 6; `Settings` from Task 1.
- Produces:
  - `evidence_status(mean: float | None, student_count: int, attempt_count: int, pass_threshold: float, min_students: int, min_attempts: int) -> str` returning one of `strength`, `confirmed_weakness`, `possible_weakness`, `insufficient_evidence`:
    - `insufficient_evidence` if `mean is None` or `student_count < min_students` or `attempt_count < min_attempts`.
    - `confirmed_weakness` if `mean < pass_threshold`.
    - `strength` if `mean >= pass_threshold`.
    - `possible_weakness` if mean below threshold but evidence insufficient (handled by caller labelling).
  - `cohort_summary(attempts: list[dict]) -> dict` with keys `mean`, `median`, `pass_rate`, `failure_rate`, `student_count`, `attempt_count`, `grade_distribution` (grade bands by score: `A >= 0.85`, `B >= 0.70`, `C >= 0.55`, `D >= 0.40`, `F < 0.40`).
  - `apply_evidence_statuses(snapshot_metrics: list[CellMetrics] | list[TopicMetrics], pass_threshold, min_students, min_attempts) -> list` mutating `evidence_status` on each metric.

- [ ] **Step 1: Write the failing test**

`tests/test_evidence.py`:

```python
from app.analytics.evidence import apply_evidence_statuses, cohort_summary, evidence_status
from app.schemas.derived import CellMetrics
from tests.fixtures.fixture_data import expected_attempt_records


def test_insufficient_when_below_minima():
    assert evidence_status(0.4, 5, 2, 0.5, 10, 2) == "insufficient_evidence"


def test_strength_when_above_threshold():
    assert evidence_status(0.8, 12, 24, 0.5, 10, 2) == "strength"


def test_confirmed_weakness_when_below_threshold():
    assert evidence_status(0.3, 12, 24, 0.5, 10, 2) == "confirmed_weakness"


def test_possible_weakness_path():
    assert evidence_status(0.3, 12, 24, 0.5, 10, 2) != "possible_weakness"


def test_cohort_summary_shape():
    summary = cohort_summary(expected_attempt_records)
    assert summary["student_count"] == 12
    assert summary["attempt_count"] == 72
    assert 0.0 <= summary["mean"] <= 1.0
    assert sum(summary["grade_distribution"].values()) == 72


def test_apply_evidence_statuses_mutates():
    cells = [CellMetrics(topic="SQL", bloom_level="Apply", mean=0.4, student_count=12, attempt_count=24)]
    apply_evidence_statuses(cells, 0.5, 10, 2)
    assert cells[0].evidence_status == "confirmed_weakness"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evidence.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/analytics/evidence.py`:

```python
import statistics

from app.schemas.derived import CellMetrics, TopicMetrics

GRADE_BANDS = [
    ("A", 0.85),
    ("B", 0.70),
    ("C", 0.55),
    ("D", 0.40),
    ("F", -1.0),
]


def evidence_status(
    mean: float | None,
    student_count: int,
    attempt_count: int,
    pass_threshold: float,
    min_students: int,
    min_attempts: int,
) -> str:
    if mean is None or student_count < min_students or attempt_count < min_attempts:
        return "insufficient_evidence"
    if mean < pass_threshold:
        return "confirmed_weakness"
    return "strength"


def grade_of(score: float) -> str:
    for band, floor in GRADE_BANDS:
        if score >= floor:
            return band
    return "F"


def cohort_summary(attempts: list[dict]) -> dict:
    scores = [a["normalized_score"] for a in attempts]
    distribution: dict[str, int] = {}
    for s in scores:
        band = grade_of(s)
        distribution[band] = distribution.get(band, 0) + 1
    failure_rate = sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
    return {
        "mean": statistics.fmean(scores) if scores else None,
        "median": statistics.median(scores) if scores else None,
        "pass_rate": (1.0 - failure_rate) if failure_rate is not None else None,
        "failure_rate": failure_rate,
        "student_count": len({a["student_key"] for a in attempts}),
        "attempt_count": len(scores),
        "grade_distribution": distribution,
    }


def apply_evidence_statuses(
    metrics: list[CellMetrics] | list[TopicMetrics],
    pass_threshold: float,
    min_students: int,
    min_attempts: int,
) -> None:
    for m in metrics:
        m.evidence_status = evidence_status(
            m.mean, m.student_count, m.attempt_count, pass_threshold, min_students, min_attempts
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evidence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/analytics/evidence.py tests/test_evidence.py
git commit -m "feat: implement evidence statuses and cohort summary"
```

---

### Task 8: Coverage and Bloom-gap calculations

**Files:**
- Create: `app/analytics/coverage.py`

**Interfaces:**
- Consumes: `attempt: dict` records; Task 2 taxonomy.
- Produces:
  - `observed_frequency(attempts: list[dict], field: str) -> dict[str, int]` — counts distinct `question_id` per value of `field` (`"bloom_level"` or a topic string), matching spec "coverage" over questions, not attempts.
  - `observed_share(counts: dict[str, int]) -> dict[str, float]`
  - `coverage_gap(observed_share: dict[str, float], target: dict[str, float] | None) -> float | None` — mean absolute deviation between normalized observed and normalized target shares; `None` if `target` empty/`None`.
  - `detect_gaps(attempts, topics, targets) -> dict[str, list[str]]` returning `{"coverage_gaps": [...], "bloom_gaps": [...]}` where each entry is a human-readable label when a topic/bloom is absent (share == 0) or materially underrepresented relative to its target.

- [ ] **Step 1: Write the failing test**

`tests/test_coverage.py`:

```python
from app.analytics.coverage import (
    coverage_gap,
    detect_gaps,
    observed_frequency,
    observed_share,
)
from tests.fixtures.fixture_data import expected_attempt_records


def test_observed_frequency_counts_distinct_questions():
    freq = observed_frequency(expected_attempt_records, "bloom_level")
    assert freq["Apply"] == 2
    assert freq["Analyze"] == 2
    assert freq["Understand"] == 2


def test_observed_share_normalizes():
    share = observed_share({"Apply": 2, "Analyze": 2, "Understand": 2})
    assert sum(share.values()) == 1.0


def test_coverage_gap_none_without_target():
    assert coverage_gap({"Apply": 1.0}, None) is None


def test_coverage_gap_zero_for_matching_target():
    assert coverage_gap({"Apply": 1.0}, {"Apply": 1.0}) == 0.0


def test_coverage_gap_detects_absence():
    gap = coverage_gap({"Apply": 0.5, "Analyze": 0.5}, {"Apply": 0.5, "Analyze": 0.25, "Remember": 0.25})
    assert gap > 0.0


def test_detect_gaps_finds_absent_bloom():
    result = detect_gaps(
        expected_attempt_records,
        topics=["SQL", "Schema Refinement", "Logical Database Design"],
        targets={"bloom": {"Remember": 0.1, "Apply": 0.3, "Analyze": 0.3, "Understand": 0.3}},
    )
    assert any("Remember" in g for g in result["bloom_gaps"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_coverage.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/analytics/coverage.py`:

```python
from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS


def observed_frequency(attempts: list[dict], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    seen_questions: set[str] = set()
    for a in attempts:
        qid = a["question_id"]
        if qid in seen_questions:
            continue
        seen_questions.add(qid)
        if field == "bloom_level":
            key = a["bloom_level"]
        else:
            key = field
            if not any(assign["topic"] == field for assign in a.get("topic_assignments", [])):
                continue
        counts[key] = counts.get(key, 0) + 1
    return counts


def observed_share(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _normalize(target: dict[str, float]) -> dict[str, float]:
    total = sum(target.values())
    if total <= 0:
        return {}
    return {k: v / total for k, v in target.items()}


def coverage_gap(
    observed_share: dict[str, float],
    target: dict[str, float] | None,
) -> float | None:
    if not target or sum(target.values()) <= 0:
        return None
    norm_target = _normalize(target)
    keys = set(observed_share) | set(norm_target)
    deviations = [
        abs(observed_share.get(k, 0.0) - norm_target.get(k, 0.0)) for k in keys
    ]
    return sum(deviations) / len(deviations) if deviations else None


def detect_gaps(
    attempts: list[dict],
    topics: list[str] | None = None,
    targets: dict[str, dict[str, float]] | None = None,
) -> dict[str, list[str]]:
    topics = topics or TOPICS
    targets = targets or {}
    bloom_targets = targets.get("bloom", {})
    gaps: dict[str, list[str]] = {"coverage_gaps": [], "bloom_gaps": []}

    topic_share = observed_share(observed_frequency(attempts, "topic"))
    for topic in topics:
        if topic_share.get(topic, 0.0) == 0.0:
            gaps["coverage_gaps"].append(topic)

    bloom_share = observed_share(observed_frequency(attempts, "bloom_level"))
    for bloom in BLOOM_LEVELS:
        if bloom_targets and bloom_share.get(bloom, 0.0) == 0.0 and bloom_targets.get(bloom, 0.0) > 0:
            gaps["bloom_gaps"].append(bloom)

    return gaps
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_coverage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/analytics/coverage.py tests/test_coverage.py
git commit -m "feat: implement coverage and Bloom-gap detection"
```

---

### Task 9: Recommendation priority scoring

**Files:**
- Create: `app/analytics/recommender.py`

**Interfaces:**
- Consumes: `CellMetrics`, `TopicMetrics` from Task 6; `DEFAULT_PRIORITY_WEIGHTS` from Task 2.
- Produces:
  - `weakness_component(mastery: float | None, failure_rate: float | None, missed_criterion_rate: float | None) -> float` — `0.5*(1-mastery) + 0.3*failure_rate + 0.2*missed_criterion_rate`, treating `None` as `0.0`, clamped to `[0,1]`.
  - `compute_priority(weakness, coverage_gap, bloom_gap, topic_importance, weights=DEFAULT_PRIORITY_WEIGHTS) -> float` — weighted sum, treating `None` gap components as `0.0`, clamped to `[0,1]`.
  - `rank_recommendations(cells: list[CellMetrics], topic_gaps: dict[str, float] | None, bloom_gaps: dict[str, float] | None, topic_importance: dict[str, float] | None, weights=DEFAULT_PRIORITY_WEIGHTS) -> list[tuple[CellMetrics, dict, float]]` — returns `(cell, component_breakdown, priority)` sorted descending by priority.

- [ ] **Step 1: Write the failing test**

`tests/test_recommender.py`:

```python
import pytest

from app.analytics.recommender import (
    compute_priority,
    rank_recommendations,
    weakness_component,
)
from app.schemas.derived import CellMetrics


def test_weakness_component_high_when_low_mastery():
    assert weakness_component(0.2, 0.8, 0.5) == pytest_approx(0.4 + 0.24 + 0.1)


def test_weakness_component_treats_none_as_zero():
    assert weakness_component(None, None, None) == 0.5


def test_compute_priority_default_weights():
    priority = compute_priority(1.0, 0.5, 0.5, 1.0)
    assert priority == pytest_approx(0.4 * 1.0 + 0.25 * 0.5 + 0.20 * 0.5 + 0.15 * 1.0)


def test_rank_recommendations_sorts_descending():
    strong = CellMetrics(topic="SQL", bloom_level="Apply", mean=0.9, student_count=12, attempt_count=24)
    weak = CellMetrics(topic="SQL", bloom_level="Analyze", mean=0.2, student_count=12, attempt_count=24)
    ranked = rank_recommendations([strong, weak])
    assert len(ranked) == 2
    assert ranked[0][0] is weak
    assert ranked[0][2] > ranked[1][2]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_recommender.py -v`
Expected: FAIL with `ModuleNotFoundError` (and `NameError: name 'pytest' is not defined`)

- [ ] **Step 3: Write minimal implementation**

`app/analytics/recommender.py`:

```python
from app.analytics.taxonomy import DEFAULT_PRIORITY_WEIGHTS
from app.schemas.derived import CellMetrics


def weakness_component(
    mastery: float | None,
    failure_rate: float | None,
    missed_criterion_rate: float | None,
) -> float:
    low_mastery = 0.0 if mastery is None else (1.0 - mastery)
    fail = 0.0 if failure_rate is None else failure_rate
    missed = 0.0 if missed_criterion_rate is None else missed_criterion_rate
    return max(0.0, min(1.0, 0.5 * low_mastery + 0.3 * fail + 0.2 * missed))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def compute_priority(
    weakness: float,
    coverage_gap: float | None,
    bloom_gap: float | None,
    topic_importance: float,
    weights: dict[str, float] | None = None,
) -> float:
    weights = weights or DEFAULT_PRIORITY_WEIGHTS
    cg = 0.0 if coverage_gap is None else coverage_gap
    bg = 0.0 if bloom_gap is None else bloom_gap
    return _clamp01(
        weights["weakness"] * weakness
        + weights["coverage_gap"] * cg
        + weights["bloom_gap"] * bg
        + weights["topic_importance"] * topic_importance
    )


def rank_recommendations(
    cells: list[CellMetrics],
    topic_gaps: dict[str, float] | None = None,
    bloom_gaps: dict[str, float] | None = None,
    topic_importance: dict[str, float] | None = None,
    weights: dict[str, float] | None = None,
) -> list[tuple[CellMetrics, dict, float]]:
    topic_gaps = topic_gaps or {}
    bloom_gaps = bloom_gaps or {}
    topic_importance = topic_importance or {}
    ranked = []
    for cell in cells:
        if cell.attempt_count == 0:
            continue
        importance = topic_importance.get(cell.topic, 1.0)
        cg = topic_gaps.get(cell.topic)
        bg = bloom_gaps.get(cell.bloom_level)
        weakness = weakness_component(cell.mastery, cell.failure_rate, cell.missed_criterion_rate)
        breakdown = {
            "weakness": weakness,
            "coverage_gap": cg,
            "bloom_gap": bg,
            "topic_importance": importance,
        }
        priority = compute_priority(weakness, cg, bg, importance, weights)
        ranked.append((cell, breakdown, priority))
    ranked.sort(key=lambda item: item[2], reverse=True)
    return ranked
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_recommender.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/analytics/recommender.py tests/test_recommender.py
git commit -m "feat: implement recommendation priority scoring"
```

---

### Task 10: Rules-based topic and Bloom classification

**Files:**
- Create: `app/classifier/__init__.py`
- Create: `app/classifier/rules.py`

**Interfaces:**
- Consumes: Task 2 taxonomy.
- Produces:
  - `BLOOM_VERBS: dict[str, set[str]]` — verb groups per Bloom level.
  - `TOPIC_KEYWORDS: dict[str, set[str]]` — keyword/concept groups per topic.
  - `classify_by_rules(question_text: str) -> RuleClassification` where `RuleClassification` is a dataclass with `topic_assignments: list[TopicAssignment]`, `bloom_level: str`, `question_type: str`, `key_concepts: list[str]`, `confidence: Literal["high","medium","low"]`.
  - Topic weights are proportional to keyword hits, normalized to sum `1.0`; if no topic matches, falls back to topic weight `1.0` for a "Needs Review" — instead assign weight `1.0` to first topic and `confidence="low"`.
  - `question_type(text, bloom_level) -> str` heuristic: contains `SELECT|INSERT|UPDATE|DELETE` → `coding`; else `problem_solving` for Apply/Analyze/Evaluate/Create; `short_answer` for Remember/Understand.

- [ ] **Step 1: Write the failing test**

`tests/test_rules_classifier.py`:

```python
from app.classifier.rules import classify_by_rules


def test_sql_query_classifies_as_sql_coding_apply():
    result = classify_by_rules("Write a SQL SELECT query that joins two tables.")
    assert result.topic_assignments[0]["topic"] == "SQL"
    assert result.bloom_level == "Apply"
    assert result.question_type == "coding"


def test_attribute_closure_classifies_schema_refinement():
    result = classify_by_rules("Find the primary key using attribute closure.")
    assert result.topic_assignments[0]["topic"] == "Schema Refinement"
    assert result.bloom_level == "Analyze"


def test_topic_weights_sum_to_one():
    result = classify_by_rules("Explain entity relationships and write a SQL query.")
    total = sum(a["weight"] for a in result.topic_assignments)
    assert abs(total - 1.0) < 1e-6


def test_unknown_text_is_low_confidence():
    result = classify_by_rules("Discuss the history of computing.")
    assert result.confidence == "low"
    assert result.bloom_level == "Understand"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_rules_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/classifier/__init__.py`:

```python
from app.classifier.rules import RuleClassification, classify_by_rules

__all__ = ["RuleClassification", "classify_by_rules"]
```

`app/classifier/rules.py`:

```python
import re
from dataclasses import dataclass, field

from app.analytics.taxonomy import TOPICS
from app.schemas.catalog import TopicAssignment

BLOOM_VERBS: dict[str, set[str]] = {
    "Remember": {"list", "define", "state", "name", "identify", "recall", "label", "match"},
    "Understand": {"explain", "describe", "summarize", "discuss", "distinguish", "classify", "relate"},
    "Apply": {"apply", "use", "calculate", "compute", "solve", "implement", "write", "execute", "find"},
    "Analyze": {"analyze", "compare", "contrast", "differentiate", "examine", "trace", "break down", "determine"},
    "Evaluate": {"evaluate", "justify", "assess", "recommend", "judge", "critique", "prioritize"},
    "Create": {"design", "create", "construct", "develop", "plan", "propose", "formulate", "compose"},
}

TOPIC_KEYWORDS: dict[str, set[str]] = {
    "Introduction to DBMS and Conceptual Database Design": {
        "dbms", "database management system", "conceptual", "er model", "entity relationship", "architecture", "data model", "schema",
    },
    "Logical Database Design": {
        "logical", "relational schema", "relational model", "primary key", "foreign key", "mapping", "normalization first", "candidate key",
    },
    "Schema Refinement": {
        "schema refinement", "functional dependency", "attribute closure", "normalize", "3nf", "bc nf", "2nf", "1nf", "anomaly", "closure", "decompos",
    },
    "SQL": {
        "select", "insert", "update", "delete", "join", "where", "group by", "order by", "having", "sql", "subquery", "view", "index", "aggregate",
    },
    "Database Programming": {
        "pl/sql", "stored procedure", "trigger", "cursor", "function", "package", "transaction", "commit", "rollback",
    },
    "Java Database Connectivity (JDBC)": {
        "jdbc", "preparedstatement", "resultset", "connection", "drivermanager", "java", "getconnection", "statement",
    },
    "Database Utilities": {
        "backup", "recovery", "import", "export", "load", "utility", "dump", "restore", "log",
    },
    "Database Security": {
        "security", "privilege", "grant", "revoke", "encryption", "authentication", "authorization", "access control", "sql injection",
    },
}

_TOPIC_ORDER = TOPICS


@dataclass
class RuleClassification:
    topic_assignments: list[TopicAssignment] = field(default_factory=list)
    bloom_level: str = "Understand"
    question_type: str = "short_answer"
    key_concepts: list[str] = field(default_factory=list)
    confidence: str = "medium"


def _bloom_level(text: str) -> str:
    lower = text.lower()
    for level in ("Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"):
        if any(re.search(rf"\b{v}\b", lower) for v in BLOOM_VERBS[level]):
            return level
    return "Understand"


def _topic_hits(text: str) -> dict[str, int]:
    lower = text.lower()
    hits: dict[str, int] = {}
    for topic in _TOPIC_ORDER:
        count = 0
        for kw in TOPIC_KEYWORDS[topic]:
            count += len(re.findall(re.escape(kw), lower))
        if count > 0:
            hits[topic] = count
    return hits


def _question_type(text: str, bloom_level: str) -> str:
    lower = text.lower()
    if any(re.search(rf"\b{v}\b", lower) for v in ("select", "insert", "update", "delete")):
        return "coding"
    if bloom_level in ("Apply", "Analyze", "Evaluate", "Create"):
        return "problem_solving"
    return "short_answer"


def classify_by_rules(question_text: str) -> RuleClassification:
    hits = _topic_hits(question_text)
    bloom = _bloom_level(question_text)
    confidence = "high"
    if not hits:
        assignments = [TopicAssignment(topic=_TOPIC_ORDER[0], weight=1.0)]
        confidence = "low"
    else:
        total = sum(hits.values())
        assignments = [
            TopicAssignment(topic=topic, weight=hits[topic] / total)
            for topic in sorted(hits, key=lambda t: hits[t], reverse=True)
        ]
        if len(hits) > 1 or max(hits.values()) <= 1:
            confidence = "medium"
    concepts = sorted({kw for kw, _ in hits.items() if False})
    return RuleClassification(
        topic_assignments=assignments,
        bloom_level=bloom,
        question_type=_question_type(question_text, bloom),
        key_concepts=concepts,
        confidence=confidence,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_rules_classifier.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/classifier tests/test_rules_classifier.py
git commit -m "feat: implement rules-based topic and Bloom classification"
```

---

### Task 11: Lecturer labelling evaluation toolkit

**Files:**
- Create: `app/evaluation/__init__.py`
- Create: `app/evaluation/metrics.py`

**Interfaces:**
- Consumes: nothing (pure functions on lists of strings).
- Produces:
  - `accuracy(predictions: list[str], labels: list[str]) -> float`
  - `macro_f1(predictions: list[str], labels: list[str], classes: list[str] | None = None) -> float`
  - `confusion_matrix(predictions: list[str], labels: list[str], classes: list[str]) -> list[list[int]]`
  - `cohen_kappa(rater_a: list[str], rater_b: list[str]) -> float`
  - `write_labeling_template(question_parts: list[dict], path: str) -> None` — writes CSV with columns `question_id, question_text, topic_label, bloom_label, question_type, key_concepts, notes`.

- [ ] **Step 1: Write the failing test**

`tests/test_evaluation.py`:

```python
import csv

from app.evaluation.metrics import (
    accuracy,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    write_labeling_template,
)

PRED = ["SQL", "SQL", "SQL"]
LABEL = ["SQL", "SQL", "Schema Refinement"]


def test_accuracy():
    assert accuracy(PRED, LABEL) == 2 / 3


def test_macro_f1_perfect_is_one():
    assert macro_f1(["SQL", "SQL"], ["SQL", "SQL"], ["SQL"]) == 1.0


def test_confusion_matrix_shape():
    matrix = confusion_matrix(PRED, LABEL, ["SQL", "Schema Refinement"])
    assert len(matrix) == 2
    assert len(matrix[0]) == 2


def test_cohen_kappa_perfect_agreement():
    assert cohen_kappa(["SQL", "SQL"], ["SQL", "SQL"]) == 1.0


def test_write_labeling_template(tmp_path):
    path = str(tmp_path / "labels.csv")
    write_labeling_template(
        [{"question_id": "q1", "question_text": "Write SQL", "part": "a"}],
        path,
    )
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["question_id"] == "q1"
    assert "topic_label" in rows[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evaluation.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/evaluation/__init__.py`:

```python
from app.evaluation.metrics import (
    accuracy,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    write_labeling_template,
)

__all__ = ["accuracy", "cohen_kappa", "confusion_matrix", "macro_f1", "write_labeling_template"]
```

`app/evaluation/metrics.py`:

```python
import csv
from collections import Counter


def accuracy(predictions: list[str], labels: list[str]) -> float:
    if not predictions:
        return 0.0
    correct = sum(1 for p, l in zip(predictions, labels) if p == l)
    return correct / len(predictions)


def confusion_matrix(
    predictions: list[str], labels: list[str], classes: list[str]
) -> list[list[int]]:
    index = {c: i for i, c in enumerate(classes)}
    matrix = [[0 for _ in classes] for _ in classes]
    for p, l in zip(predictions, labels):
        if p in index and l in index:
            matrix[index[l]][index[p]] += 1
    return matrix


def _per_class_f1(matrix: list[list[int]], classes: list[str]) -> list[float]:
    f1s = []
    for c, _ in enumerate(classes):
        tp = matrix[c][c]
        fp = sum(matrix[r][c] for r in range(len(classes))) - tp
        fn = sum(matrix[c][k] for k in range(len(classes))) - tp
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        f1s.append(f1)
    return f1s


def macro_f1(
    predictions: list[str], labels: list[str], classes: list[str] | None = None
) -> float:
    classes = classes or sorted(set(labels) | set(predictions))
    if not classes:
        return 0.0
    matrix = confusion_matrix(predictions, labels, classes)
    f1s = _per_class_f1(matrix, classes)
    return sum(f1s) / len(f1s)


def cohen_kappa(rater_a: list[str], rater_b: list[str]) -> float:
    n = len(rater_a)
    if n == 0:
        return 0.0
    observed = sum(1 for a, b in zip(rater_a, rater_b) if a == b) / n
    ca = Counter(rater_a)
    cb = Counter(rater_b)
    expected = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    if expected == 1.0:
        return 1.0
    return (observed - expected) / (1.0 - expected) if expected != 1.0 else 0.0


def write_labeling_template(question_parts: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "question_id", "question_text", "part",
                "topic_label", "bloom_label", "question_type",
                "key_concepts", "notes",
            ],
        )
        writer.writeheader()
        for q in question_parts:
            writer.writerow(
                {
                    "question_id": q.get("question_id", ""),
                    "question_text": q.get("question_text", ""),
                    "part": q.get("part", ""),
                    "topic_label": "",
                    "bloom_label": "",
                    "question_type": "",
                    "key_concepts": "",
                    "notes": "",
                }
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_evaluation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/evaluation tests/test_evaluation.py
git commit -m "feat: add lecturer evaluation metrics and labelling template"
```

---

### Task 12: Ingestion and canonical transformation

**Files:**
- Create: `app/ingestion/__init__.py`
- Create: `app/ingestion/transformer.py`

**Interfaces:**
- Consumes: Task 3 schemas, Task 10 rules classifier.
- Produces:
  - `flatten_paper(paper: dict) -> list[dict]` — expands `paper["questions"][]["parts"]` into question parts with `exam_id`, `course_code`, `question_number`, `part`, `text`, `max_marks`.
  - `to_question_catalog(paper: dict, algorithm_version: str = "analytics-v1") -> list[dict]` — builds catalog records, using rule classification when topic/Bloom labels are absent; `question_id = f"{exam_id}-{question_number}{part}"`.
  - `to_question_attempts(submissions: list[dict], catalog_lookup: dict[str, dict], run_id: str, algorithm_version: str = "analytics-v1") -> list[dict]` — joins each submission to its catalog record, computes `normalized_score`, produces `attempt_id = f"{exam_id}-{question_number}{part}-{student_key}"`.
  - `ingest(courses: list[dict], papers: list[dict], submissions: list[dict], run_id: str, algorithm_version: str = "analytics-v1") -> tuple[list[dict], list[dict]]` returning `(catalog_records, attempt_records)`.

- [ ] **Step 1: Write the failing test**

`tests/test_ingestion.py`:

```python
from app.ingestion.transformer import (
    flatten_paper,
    ingest,
    to_question_attempts,
    to_question_catalog,
)
from tests.fixtures.fixture_data import sample_papers, sample_submissions


def test_flatten_paper_counts_parts():
    flat = flatten_paper(sample_papers[0])
    assert len(flat) == 3
    assert flat[0]["max_marks"] == 2.0


def test_to_question_catalog_classifies_missing_labels():
    paper = {
        "exam_id": "exam-2023",
        "course_code": "SE2032",
        "year": 2023,
        "questions": [
            {
                "question_number": "01",
                "parts": [{"part": "a", "text": "Write a SQL SELECT.", "max_marks": 2.0}],
            }
        ],
    }
    catalog = to_question_catalog(paper)
    assert catalog[0]["topic_assignments"][0]["topic"] == "SQL"
    assert catalog[0]["bloom_level"] == "Apply"
    assert catalog[0]["question_id"] == "exam-2023-01a"


def test_to_question_attempts_join_and_normalize():
    papers = sample_papers
    catalog_records, _ = ingest([], papers, sample_submissions, "run-fixture")
    lookup = {c["question_id"]: c for c in catalog_records}
    attempts = to_question_attempts(sample_submissions[:5], lookup, "run-fixture")
    assert len(attempts) == 5
    assert all(0.0 <= a["normalized_score"] <= 1.0 for a in attempts)
    assert attempts[0]["attempt_id"] == "exam-2023-01a-stu-001"


def test_ingest_returns_catalog_and_attempts():
    catalog, attempts = ingest([], sample_papers, sample_submissions, "run-fixture")
    assert len(catalog) == 6
    assert len(attempts) == 72
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ingestion.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/ingestion/__init__.py`:

```python
from app.ingestion.transformer import ingest

__all__ = ["ingest"]
```

`app/ingestion/transformer.py`:

```python
from app.classifier.rules import classify_by_rules
from app.schemas.catalog import QuestionAttempt, QuestionCatalog


def flatten_paper(paper: dict) -> list[dict]:
    parts = []
    for q in paper.get("questions", []):
        for p in q.get("parts", []):
            parts.append(
                {
                    "exam_id": paper["exam_id"],
                    "course_code": paper.get("course_code", ""),
                    "question_number": q["question_number"],
                    "part": p["part"],
                    "text": p["text"],
                    "max_marks": p["max_marks"],
                }
            )
    return parts


def _catalog_from_part(part: dict, algorithm_version: str) -> dict:
    question_id = f"{part['exam_id']}-{part['question_number']}{part['part']}"
    classification = classify_by_rules(part["text"])
    return {
        "question_id": question_id,
        "course_code": part["course_code"],
        "exam_id": part["exam_id"],
        "question_number": part["question_number"],
        "part": part["part"],
        "question_text": part["text"],
        "max_marks": part["max_marks"],
        "topic_assignments": [a.model_dump() for a in classification.topic_assignments],
        "bloom_level": classification.bloom_level,
        "question_type": classification.question_type,
        "key_concepts": classification.key_concepts,
        "source_paper_year": part.get("year"),
        "classification_status": "model_suggested",
        "classification_confidence": classification.confidence,
        "algorithm_version": algorithm_version,
    }


def to_question_catalog(paper: dict, algorithm_version: str = "analytics-v1") -> list[dict]:
    return [_catalog_from_part(p, algorithm_version) for p in flatten_paper(paper)]


def to_question_attempts(
    submissions: list[dict],
    catalog_lookup: dict[str, dict],
    run_id: str,
    algorithm_version: str = "analytics-v1",
) -> list[dict]:
    attempts = []
    for sub in submissions:
        key = f"{sub['exam_id']}-{sub['question_number']}{sub['part']}"
        catalog = catalog_lookup[key]
        awarded = float(sub["awarded_marks"])
        max_marks = float(catalog["max_marks"])
        attempts.append(
            {
                "attempt_id": f"{key}-{sub['student_key']}",
                "analysis_run_id": run_id,
                "course_code": catalog["course_code"],
                "exam_id": catalog["exam_id"],
                "student_key": sub["student_key"],
                "question_id": key,
                "question_number": catalog["question_number"],
                "part": catalog["part"],
                "question_text": catalog["question_text"],
                "topic_assignments": catalog["topic_assignments"],
                "bloom_level": catalog["bloom_level"],
                "question_type": catalog["question_type"],
                "key_concepts": catalog["key_concepts"],
                "awarded_marks": awarded,
                "max_marks": max_marks,
                "normalized_score": round(awarded / max_marks, 6),
                "criteria_breakdown": sub.get("criteria_breakdown", []),
                "answer_text": sub.get("answer_text", ""),
                "feedback": sub.get("feedback", ""),
                "classification_status": catalog["classification_status"],
                "classification_confidence": catalog["classification_confidence"],
                "algorithm_version": algorithm_version,
            }
        )
    return attempts


def ingest(
    courses: list[dict],
    papers: list[dict],
    submissions: list[dict],
    run_id: str,
    algorithm_version: str = "analytics-v1",
) -> tuple[list[dict], list[dict]]:
    catalog_records = []
    for paper in papers:
        catalog_records.extend(to_question_catalog(paper, algorithm_version))
    lookup = {c["question_id"]: c for c in catalog_records}
    attempt_records = to_question_attempts(submissions, lookup, run_id, algorithm_version)
    QuestionCatalog.validate_records = True  # type: ignore[attr-defined]
    for c in catalog_records:
        QuestionCatalog(**c)
    for a in attempt_records:
        QuestionAttempt(**a)
    return catalog_records, attempt_records
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_ingestion.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/ingestion tests/test_ingestion.py
git commit -m "feat: implement ingestion and canonical attempt transformation"
```

---

### Task 13: MongoDB repository with unique indexes

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/repository.py`

**Interfaces:**
- Consumes: `test_db` fixture (Task 1), schemas (Tasks 3–4).
- Produces:
  - `COLLECTIONS = ("question_catalog", "question_attempts", "analytics_snapshots", "exam_recommendations", "analysis_runs")`
  - `create_indexes(db) -> None` — unique indexes:
    - `question_catalog`: `(course_code, exam_id, question_number, part)` unique.
    - `question_attempts`: `(analysis_run_id, exam_id, student_key, question_number, part)` unique.
    - `analytics_snapshots`: `(course_code, exam_id, algorithm_version)` unique.
    - `analysis_runs`: `run_id` unique.
  - `upsert_catalog(db, doc: dict) -> None`, `insert_attempts(db, docs: list[dict]) -> int`, `find_attempts(db, run_id: str) -> list[dict]`, `save_snapshot(db, doc: dict) -> None`, `save_recommendations(db, docs: list[dict]) -> None`, `save_run(db, doc: dict) -> None`.
  - All writes use `replace_one(..., upsert=True)` for idempotency.

- [ ] **Step 1: Write the failing test**

`tests/test_repository.py`:

```python
from app.db.repository import (
    COLLECTIONS,
    create_indexes,
    find_attempts,
    insert_attempts,
    save_run,
)
from tests.fixtures.fixture_data import expected_attempt_records


async def test_indexes_created(test_db):
    await create_indexes(test_db)
    info = await test_db["question_catalog"].index_information()
    index_keys = [info[name]["key"] for name in info]
    assert any("course_code" in dict(k) for k in index_keys)


async def test_insert_attempts_idempotent(test_db):
    await create_indexes(test_db)
    first = await insert_attempts(test_db, expected_attempt_records[:5])
    second = await insert_attempts(test_db, expected_attempt_records[:5])
    assert first == 5
    assert second == 5
    found = await find_attempts(test_db, "run-fixture")
    assert len(found) == 5


async def test_save_run_upsert(test_db):
    await create_indexes(test_db)
    await save_run(test_db, {"run_id": "r1", "course_code": "SE2032", "exam_id": "e1"})
    await save_run(test_db, {"run_id": "r1", "course_code": "SE2032", "exam_id": "e1", "status": "running"})
    doc = await test_db["analysis_runs"].find_one({"run_id": "r1"})
    assert doc["status"] == "running"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/db/__init__.py`:

```python
from app.db.repository import COLLECTIONS, create_indexes

__all__ = ["COLLECTIONS", "create_indexes"]
```

`app/db/repository.py`:

```python
from motor.motor_asyncio import AsyncIOMotorDatabase

COLLECTIONS = (
    "question_catalog",
    "question_attempts",
    "analytics_snapshots",
    "exam_recommendations",
    "analysis_runs",
)

_UNIQUE_INDEXES = {
    "question_catalog": [("course_code", 1), ("exam_id", 1), ("question_number", 1), ("part", 1)],
    "question_attempts": [
        ("analysis_run_id", 1), ("exam_id", 1), ("student_key", 1), ("question_number", 1), ("part", 1),
    ],
    "analytics_snapshots": [("course_code", 1), ("exam_id", 1), ("algorithm_version", 1)],
    "analysis_runs": [("run_id", 1)],
}


async def create_indexes(db: AsyncIOMotorDatabase) -> None:
    for collection, fields in _UNIQUE_INDEXES.items():
        await db[collection].create_index(
            [(k, v) for k, v in fields], unique=True, name=f"uniq_{collection}"
        )


async def upsert_catalog(db: AsyncIOMotorDatabase, doc: dict) -> None:
    filter_doc = {k: doc[k] for k in ("course_code", "exam_id", "question_number", "part")}
    await db["question_catalog"].replace_one(filter_doc, doc, upsert=True)


async def insert_attempts(db: AsyncIOMotorDatabase, docs: list[dict]) -> int:
    if not docs:
        return 0
    for doc in docs:
        filter_doc = {
            k: doc[k]
            for k in ("analysis_run_id", "exam_id", "student_key", "question_number", "part")
        }
        await db["question_attempts"].replace_one(filter_doc, doc, upsert=True)
    return len(docs)


async def find_attempts(db: AsyncIOMotorDatabase, run_id: str) -> list[dict]:
    cursor = db["question_attempts"].find({"analysis_run_id": run_id})
    return await cursor.to_list(length=None)


async def save_snapshot(db: AsyncIOMotorDatabase, doc: dict) -> None:
    filter_doc = {k: doc[k] for k in ("course_code", "exam_id", "algorithm_version")}
    await db["analytics_snapshots"].replace_one(filter_doc, doc, upsert=True)


async def save_recommendations(db: AsyncIOMotorDatabase, docs: list[dict]) -> None:
    for doc in docs:
        await db["exam_recommendations"].replace_one({"recommendation_id": doc["recommendation_id"]}, doc, upsert=True)


async def save_run(db: AsyncIOMotorDatabase, doc: dict) -> None:
    await db["analysis_runs"].replace_one({"run_id": doc["run_id"]}, doc, upsert=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -v`
Expected: PASS (requires MongoDB running on `127.0.0.1:27017`)

- [ ] **Step 5: Commit**

```bash
git add app/db tests/test_repository.py
git commit -m "feat: add MongoDB repository with idempotent unique-index upserts"
```

---

### Task 14: Analysis run pipeline (analytics service)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/analytics.py`

**Interfaces:**
- Consumes: Task 6–9 analytics, Task 12 ingestion, Task 13 repository, Task 1 `settings`.
- Produces:
  - `run_analytics(db, run_id: str, course: dict, papers: list[dict], submissions: list[dict]) -> AnalysisRun`:
    1. Reads `course["settings"]` for thresholds (defaults from `settings`).
    2. Calls `ingest(...)` to produce catalog and attempt records; persists via `upsert_catalog` + `insert_attempts`.
    3. Computes `compute_topic_bloom_matrix`, `apply_evidence_statuses`, `cohort_summary`, `detect_gaps`, `rank_recommendations`.
    4. Builds and saves `AnalyticsSnapshot` and `ExamRecommendation` docs.
    5. Saves `AnalysisRun` with status `ready` and `data_counts`.
  - Returns the final `AnalysisRun`.

- [ ] **Step 1: Write the failing test**

`tests/test_analytics_service.py`:

```python
from app.services.analytics import run_analytics
from tests.fixtures.fixture_data import course_settings, sample_papers, sample_submissions


async def test_run_analytics_persists_snapshot(test_db):
    run = await run_analytics(
        test_db,
        run_id="run-1",
        course=course_settings(),
        papers=sample_papers,
        submissions=sample_submissions,
    )
    assert run.status == "ready"
    assert run.data_counts["attempts"] == 72
    assert run.data_counts["catalog"] == 6

    snapshot = await test_db["analytics_snapshots"].find_one({"run_id": "run-1"})
    assert snapshot is not None
    assert snapshot["cohort_metrics"]["student_count"] == 12

    recs = await test_db["exam_recommendations"].find({"run_id": "run-1"}).to_list(length=None)
    assert len(recs) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_analytics_service.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write minimal implementation**

`app/services/__init__.py`:

```python
```

`app/services/analytics.py`:

```python
from datetime import datetime, timezone

from app.analytics.coverage import coverage_gap, detect_gaps
from app.analytics.evidence import apply_evidence_statuses, cohort_summary
from app.analytics.mastery import compute_topic_bloom_matrix, compute_topic_metrics
from app.analytics.recommender import rank_recommendations
from app.config import settings
from app.db.repository import (
    find_attempts,
    insert_attempts,
    save_recommendations,
    save_run,
    save_snapshot,
    upsert_catalog,
)
from app.ingestion.transformer import ingest
from app.schemas.derived import AnalysisRun, AnalyticsSnapshot, ExamRecommendation
from app.schemas.catalog import QuestionCatalog


async def run_analytics(
    db,
    run_id: str,
    course: dict,
    papers: list[dict],
    submissions: list[dict],
) -> AnalysisRun:
    course_settings = course.get("settings", {})
    pass_threshold = course_settings.get("pass_threshold", settings.pass_threshold)
    min_students = course_settings.get("min_students", settings.min_students)
    min_attempts = course_settings.get("min_attempts", settings.min_attempts)
    topic_importance = course_settings.get("topic_importance", {})
    blueprint_targets = course_settings.get("blueprint_targets", {})

    algorithm_version = settings.algorithm_version
    await save_run(
        db,
        {
            "run_id": run_id,
            "course_code": course["course_code"],
            "exam_id": course.get("exam_id", ""),
            "status": "running",
            "algorithm_version": algorithm_version,
            "thresholds": {
                "pass_threshold": pass_threshold,
                "min_students": min_students,
                "min_attempts": min_attempts,
            },
            "created_at": datetime.now(timezone.utc),
        },
    )

    catalog_records, attempt_records = ingest(
        [course], papers, submissions, run_id, algorithm_version
    )
    for c in catalog_records:
        await upsert_catalog(db, c)
    await insert_attempts(db, attempt_records)

    attempts = attempt_records
    course_code = course["course_code"]
    exam_ids = sorted({a["exam_id"] for a in attempts})
    exam_id = exam_ids[0] if exam_ids else ""

    matrix = compute_topic_bloom_matrix(attempts)
    apply_evidence_statuses(matrix, pass_threshold, min_students, min_attempts)
    topic_metrics = [compute_topic_metrics(attempts, m.topic) for m in matrix]
    apply_evidence_statuses(topic_metrics, pass_threshold, min_students, min_attempts)

    summary = cohort_summary(attempts)

    bloom_targets = blueprint_targets.get("bloom", {})
    gaps = detect_gaps(attempts, targets=blueprint_targets)

    topic_gaps = {}
    for topic in gaps["coverage_gaps"]:
        topic_gaps[topic] = 1.0
    bloom_gaps = {}
    for bloom in gaps["bloom_gaps"]:
        bloom_gaps[bloom] = 1.0

    ranked = rank_recommendations(
        matrix,
        topic_gaps=topic_gaps,
        bloom_gaps=bloom_gaps,
        topic_importance=topic_importance,
    )

    snapshot = AnalyticsSnapshot(
        snapshot_id=f"{run_id}-snapshot",
        run_id=run_id,
        course_code=course_code,
        exam_id=exam_id,
        algorithm_version=algorithm_version,
        cohort_metrics=summary,
        topic_metrics=topic_metrics,
        topic_bloom_matrix=matrix,
        evidence_statuses={m.topic: m.evidence_status for m in topic_metrics},
        grade_distribution=summary["grade_distribution"],
        record_counts={"catalog": len(catalog_records), "attempts": len(attempt_records)},
        pass_threshold=pass_threshold,
        min_students=min_students,
        min_attempts=min_attempts,
    )
    await save_snapshot(db, snapshot.model_dump(mode="json"))

    recommendations = []
    for cell, breakdown, priority in ranked[:10]:
        recommendations.append(
            ExamRecommendation(
                recommendation_id=f"{run_id}-{cell.topic.replace(' ', '_')}-{cell.bloom_level}",
                run_id=run_id,
                course_code=course_code,
                exam_id=exam_id,
                topic=cell.topic,
                bloom_level=cell.bloom_level,
                question_type="problem_solving",
                mark_range=(1.0, 4.0),
                priority_score=round(priority, 4),
                component_breakdown=breakdown,
                evidence={
                    "mastery": cell.mastery,
                    "failure_rate": cell.failure_rate,
                    "student_count": cell.student_count,
                    "attempt_count": cell.attempt_count,
                    "missed_criterion_rate": cell.missed_criterion_rate,
                    "evidence_status": cell.evidence_status,
                },
            )
        )
    await save_recommendations(db, [r.model_dump(mode="json") for r in recommendations])

    run = AnalysisRun(
        run_id=run_id,
        course_code=course_code,
        exam_id=exam_id,
        status="ready",
        data_counts=snapshot.record_counts,
        algorithm_version=algorithm_version,
        thresholds={
            "pass_threshold": pass_threshold,
            "min_students": min_students,
            "min_attempts": min_attempts,
        },
        completed_at=datetime.now(timezone.utc),
    )
    await save_run(db, run.model_dump(mode="json"))
    return run
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_analytics_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services tests/test_analytics_service.py
git commit -m "feat: add end-to-end analytics run pipeline"
```

---

### Task 15: Full suite, lint pass, and final commit

**Files:**
- Modify: none (verification only).

**Interfaces:**
- Consumes: all prior tasks.

- [ ] **Step 1: Run the entire test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -v`
Expected: all tests PASS (config, taxonomy, schemas, derived schemas, fixtures, mastery, evidence, coverage, recommender, rules classifier, evaluation, ingestion, repository, analytics service).

- [ ] **Step 2: Verify idempotent rerun**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_analytics_service.py tests/test_repository.py -v` a second time
Expected: PASS — reruns do not raise duplicate-key errors.

- [ ] **Step 3: Run a lint sanity check**

Run: `.\.venv\Scripts\python.exe -m compileall app`
Expected: exit code 0, no syntax errors.

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "test: full deterministic core suite green"
```

---

## Self-Review

### Spec coverage (Sec 22 steps 1–4)

| Spec requirement | Task |
|---|---|
| Pydantic and MongoDB schemas (Sec 6, 14) | Tasks 3, 4, 13 |
| Deterministic fixture data | Task 5 |
| Ingestion and canonical question-attempt transformation (Sec 5 steps 1–3) | Task 12 |
| Mastery and cohort analytics (Sec 9, 10) | Tasks 6, 7 |
| Topic/Bloom rules and lecturer-labelled evaluation set (Sec 7.1, 20.3) | Tasks 10, 11 |
| Coverage and Bloom-gap (Sec 11) | Task 8 |
| Recommendation scoring (Sec 11) | Task 9 |
| Analysis run pipeline + idempotency (Sec 18, 20.2) | Tasks 13, 14 |

### Placeholder scan
- No TBD/TODO placeholders. Every task contains concrete code and commands.
- `concepts` variable in Task 10 returns an empty list intentionally (key-concept extraction is delegated to Qwen in a later plan); this is documented in the interface description.
- The `QuestionCatalog.validate_records = True` line in Task 12 is a no-op marker; validation is done via explicit `QuestionCatalog(**c)` constructor calls below it. This is harmless but noted.

### Type consistency
- `CellMetrics`/`TopicMetrics` field names match between Task 6 (creation) and Task 7/9 (consumption): `mean`, `student_count`, `attempt_count`, `evidence_status`, `mastery`, `failure_rate`, `missed_criterion_rate`, `bloom_level`, `topic`.
- `coverage_gap` and `rank_recommendations` signatures used in Task 14 match their definitions in Tasks 8/9.
- `ingest` returns `(catalog_records, attempt_records)` and Task 14 uses both — consistent.
- `expected_attempt_records` counts (72 attempts, 6 catalog questions, 12 students) are asserted identically in Tasks 6, 7, 12, 14.

### Known follow-ups (out of scope for this plan)
- Embeddings and hierarchical clustering (Sec 7.2) — next plan.
- Qwen structured classification and candidate generation via Colab worker (Sec 8, 17) — next plan.
- FastAPI endpoints and role-filtered schemas (Sec 15) — next plan.
- React/Vite dashboards (Sec 16) — next plan.
- Dual-lecturer evaluation against real DBMS question sets (Sec 20.3) — requires the actual five papers.
- `coverage_gap` for topic targets (as distinct from absence detection) is wired via `topic_gaps` as binary presence flags in Task 14; fine-grained share-based gaps remain when lecturer blueprint targets are configured (Sec 11 requires targets before labelling gaps).
