# Student Dashboard API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-student dashboard REST endpoint that reports a student's exam grades, cognitive (Bloom) skill breakdown, topic strengths/weaknesses, missed criteria + feedback, cohort comparison, and study recommendations.

**Architecture:** Compute the dashboard on-the-fly from `question_attempts` (already persisted with per-student data). A pure analytics module does deterministic math (reusing `mastery.py` and `recommender.py`), a service layer orchestrates DB reads + optional LLM study actions, and a FastAPI router exposes `GET /api/students/{student_key}/dashboard`.

**Tech Stack:** FastAPI, uvicorn (already in requirements), Motor/MongoDB, Pydantic, pytest + pytest-asyncio.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-06-student-dashboard-design.md`
- Endpoint: `GET /api/students/{student_key}/dashboard?run_id=<optional>&include_llm=<bool>` (include_llm default `false`)
- Reuse `compute_mastery`, `_qualifying`, `topic_weight_for` from `app/analytics/mastery.py`; `weakness_component` from `app/analytics/recommender.py`; `evidence_status` and `grade_of` from `app/analytics/evidence.py`; `TOPICS`/`BLOOM_LEVELS` from `app/analytics/taxonomy.py`.
- Grade bands (from `evidence.grade_of`): A>=0.85, B>=0.70, C>=0.55, D>=0.40, else F.
- `source` field on study actions is `Literal["llm", "deterministic"]`.
- Mongo tests use the existing `test_db` session fixture (`tests/conftest.py`).
- Never import real Mongo in pure analytics module (`app/analytics/student.py`).
- No comments in code unless they document non-obvious logic.

---

### Task 1: Student dashboard schemas

**Files:**
- Create: `app/schemas/student.py`
- Test: `tests/test_schemas_student.py`

**Interfaces:**
- Produces: `MissedCriterion`, `QuestionPerformance`, `StudentExamPerformance`, `StudentBloomSkill`, `StudentTopicSkill`, `StudentStudyAction`, `StudentDashboard` — all Pydantic models. Later tasks import these.

- [ ] **Step 1: Write the failing test**

Create `tests/test_schemas_student.py`:

```python
from datetime import datetime, timezone

from app.schemas.student import (
    MissedCriterion,
    QuestionPerformance,
    StudentBloomSkill,
    StudentDashboard,
    StudentExamPerformance,
    StudentStudyAction,
    StudentTopicSkill,
)


def test_student_dashboard_shape():
    dash = StudentDashboard(
        student_key="stu-001",
        course_code="SE2032",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        exams=[
            StudentExamPerformance(
                exam_id="exam-2023",
                total_awarded=6.0,
                total_max=6.0,
                percentage=100.0,
                grade="A",
                attempt_count=3,
                question_performances=[
                    QuestionPerformance(
                        question_id="q1",
                        question_number="01",
                        part="a",
                        question_text="Write a SQL SELECT.",
                        topic="SQL",
                        bloom_level="Apply",
                        question_type="problem_solving",
                        awarded_marks=2.0,
                        max_marks=2.0,
                        normalized_score=1.0,
                        passed=True,
                        feedback="ok",
                        missed_criteria=[
                            MissedCriterion(criterion="JOIN", awarded_marks=0.0, max_marks=1.0)
                        ],
                    )
                ],
            )
        ],
        bloom_skills=[
            StudentBloomSkill(bloom_level="Apply", mastery=1.0, mean=1.0, attempt_count=1, evidence_status="strength")
        ],
        topic_skills=[
            StudentTopicSkill(topic="SQL", mastery=1.0, mean=1.0, attempt_count=1, evidence_status="strength", rank=1, priority_score=0.0)
        ],
        weakest_topics=["SQL"],
        cohort_comparison={"topics": {"SQL": {"student_mastery": 1.0, "cohort_mastery": 0.7, "delta": 0.3, "percentile": 0.5}}},
        recommendations=[
            StudentStudyAction(action="Review core concepts", topic="SQL", rationale="weak", practice_topics=["SQL"], source="deterministic")
        ],
    )
    assert dash.student_key == "stu-001"
    assert dash.exams[0].question_performances[0].missed_criteria[0].criterion == "JOIN"
    assert dash.recommendations[0].source == "deterministic"


def test_study_action_source_restricted_to_llm_or_deterministic():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StudentStudyAction(action="a", topic="SQL", rationale="r", practice_topics=[], source="unsupported")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas_student.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.student'`

- [ ] **Step 3: Write the schemas**

Create `app/schemas/student.py`:

```python
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
    missed_criteria: list[MissedCriterion] = []


class StudentExamPerformance(BaseModel):
    exam_id: str
    total_awarded: float
    total_max: float
    percentage: float
    grade: str
    attempt_count: int
    question_performances: list[QuestionPerformance] = []


class StudentBloomSkill(BaseModel):
    bloom_level: str
    mastery: float | None = None
    mean: float | None = None
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"


class StudentTopicSkill(BaseModel):
    topic: str
    mastery: float | None = None
    mean: float | None = None
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"
    rank: int = 0
    priority_score: float = 0.0


class StudentStudyAction(BaseModel):
    action: str
    topic: str
    rationale: str = ""
    practice_topics: list[str] = []
    source: Literal["llm", "deterministic"] = "deterministic"


class StudentDashboard(BaseModel):
    student_key: str
    course_code: str
    run_id: str
    generated_at: datetime = Field(default_factory=utcnow)
    exams: list[StudentExamPerformance] = []
    bloom_skills: list[StudentBloomSkill] = []
    topic_skills: list[StudentTopicSkill] = []
    weakest_topics: list[str] = []
    cohort_comparison: dict = {}
    recommendations: list[StudentStudyAction] = []
```

Note: add `Field` to the pydantic import.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas_student.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/schemas/student.py tests/test_schemas_student.py
git commit -m "feat: add student dashboard schemas"
```

---

### Task 2: Repository query helpers

**Files:**
- Modify: `app/db/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: existing `save_run`, `insert_attempts`, `find_attempts`.
- Produces:
  - `async find_attempts_by_student(db, run_id, student_key) -> list[dict]`
  - `async latest_run_id(db) -> str | None`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_repository.py`:

```python
from datetime import datetime, timezone

from app.db.repository import find_attempts_by_student, insert_attempts, latest_run_id, save_run


async def test_find_attempts_by_student_filters_by_student(test_db):
    from tests.fixtures.fixture_data import expected_attempt_records

    await insert_attempts(test_db, expected_attempt_records)
    rows = await find_attempts_by_student(test_db, "run-fixture", "stu-001")
    assert len(rows) == 6
    assert all(r["student_key"] == "stu-001" for r in rows)


async def test_find_attempts_by_student_unknown_returns_empty(test_db):
    rows = await find_attempts_by_student(test_db, "run-fixture", "nobody")
    assert rows == []


async def test_latest_run_id_returns_most_recent(test_db):
    now = datetime.now(timezone.utc)
    await save_run(test_db, {"run_id": "older", "course_code": "SE2032", "exam_id": "e", "status": "ready", "created_at": now.replace(minute=0)})
    await save_run(test_db, {"run_id": "newer", "course_code": "SE2032", "exam_id": "e", "status": "ready", "created_at": now.replace(minute=1)})
    assert await latest_run_id(test_db) == "newer"


async def test_latest_run_id_empty_returns_none(test_db):
    assert await latest_run_id(test_db) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_repository.py -v`
Expected: FAIL with `ImportError` / `AttributeError` for `find_attempts_by_student` / `latest_run_id`

- [ ] **Step 3: Write the helpers**

Append to `app/db/repository.py`:

```python
async def find_attempts_by_student(
    db: AsyncIOMotorDatabase, run_id: str, student_key: str
) -> list[dict]:
    cursor = db["question_attempts"].find(
        {"analysis_run_id": run_id, "student_key": student_key}
    )
    return await cursor.to_list(length=None)


async def latest_run_id(db: AsyncIOMotorDatabase) -> str | None:
    doc = await db["analysis_runs"].find_one(sort=[("created_at", -1)])
    return doc["run_id"] if doc else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_repository.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add app/db/repository.py tests/test_repository.py
git commit -m "feat: add per-student and latest-run repository queries"
```

---

### Task 3: Pure analytics — exam & question performance

**Files:**
- Create: `app/analytics/student.py`
- Test: `tests/test_student_analytics.py`

**Interfaces:**
- Consumes: `QuestionPerformance`, `StudentExamPerformance` (Task 1); `grade_of` from `app/analytics/evidence.py`.
- Produces:
  - `student_exam_performances(attempts, pass_threshold) -> list[StudentExamPerformance]` (one per exam, sorted by exam_id)
  - `question_performance(attempt, pass_threshold) -> QuestionPerformance`

- [ ] **Step 1: Write the failing test**

Create `tests/test_student_analytics.py`:

```python
from app.analytics.student import question_performance, student_exam_performances
from app.schemas.student import QuestionPerformance, StudentExamPerformance
from tests.fixtures.fixture_data import expected_attempt_records


def _stu1():
    return [a for a in expected_attempt_records if a["student_key"] == "stu-001"]


def test_student_exam_performances_groups_by_exam_and_grades():
    exams = student_exam_performances(_stu1(), 0.5)
    assert isinstance(exams, list) and all(isinstance(e, StudentExamPerformance) for e in exams)
    by_id = {e.exam_id: e for e in exams}
    assert set(by_id) == {"exam-2023", "exam-2024"}
    e2023 = by_id["exam-2023"]
    assert e2023.total_awarded == 6.0
    assert e2023.total_max == 6.0
    assert e2023.percentage == 100.0
    assert e2023.grade == "A"
    assert e2023.attempt_count == 3
    e2024 = by_id["exam-2024"]
    assert e2024.total_awarded == 5.0
    assert e2024.total_max == 6.0
    assert e2024.grade == "B"
    assert e2024.percentage == round(5.0 / 6.0 * 100.0, 4)


def test_question_performance_populates_fields():
    attempt = next(a for a in _stu1() if a["question_id"] == "exam-2023-01a")
    qp = question_performance(attempt, 0.5)
    assert isinstance(qp, QuestionPerformance)
    assert qp.topic == "SQL"
    assert qp.bloom_level == "Apply"
    assert qp.normalized_score == 1.0
    assert qp.passed is True
    assert qp.missed_criteria == []


def test_question_performance_reports_missed_criteria_and_fail():
    attempt = {
        "question_id": "exam-2023-01b",
        "question_number": "01",
        "part": "b",
        "question_text": "Find the primary key.",
        "topic_assignments": [{"topic": "Schema Refinement", "weight": 1.0}],
        "bloom_level": "Analyze",
        "question_type": "problem_solving",
        "awarded_marks": 1.0,
        "max_marks": 3.0,
        "normalized_score": round(1.0 / 3.0, 6),
        "feedback": "fix it",
        "criteria_breakdown": [
            {"criterion": "Closure", "awarded_marks": 0.0, "max_marks": 2.0, "met": False},
            {"criterion": "Declare key", "awarded_marks": 1.0, "max_marks": 1.0, "met": True},
        ],
    }
    qp = question_performance(attempt, 0.5)
    assert qp.passed is False
    assert [m.criterion for m in qp.missed_criteria] == ["Closure"]
    assert qp.missed_criteria[0].max_marks == 2.0
    assert qp.feedback == "fix it"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_analytics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.analytics.student'`

- [ ] **Step 3: Write the module**

Create `app/analytics/student.py`:

```python
from app.analytics.evidence import grade_of
from app.schemas.student import QuestionPerformance, StudentExamPerformance


def _dominant_topic(attempt: dict) -> str:
    assignments = attempt.get("topic_assignments", [])
    if not assignments:
        return ""
    return max(assignments, key=lambda a: a["weight"])["topic"]


def question_performance(attempt: dict, pass_threshold: float) -> QuestionPerformance:
    missed = [
        {
            "criterion": c["criterion"],
            "awarded_marks": c["awarded_marks"],
            "max_marks": c["max_marks"],
        }
        for c in attempt.get("criteria_breakdown", [])
        if not c.get("met")
    ]
    return QuestionPerformance(
        question_id=attempt["question_id"],
        question_number=attempt["question_number"],
        part=attempt["part"],
        question_text=attempt["question_text"],
        topic=_dominant_topic(attempt),
        bloom_level=attempt["bloom_level"],
        question_type=attempt["question_type"],
        awarded_marks=attempt["awarded_marks"],
        max_marks=attempt["max_marks"],
        normalized_score=attempt["normalized_score"],
        passed=attempt["normalized_score"] >= pass_threshold,
        feedback=attempt.get("feedback", ""),
        missed_criteria=missed,
    )


def student_exam_performances(
    attempts: list[dict], pass_threshold: float
) -> list[StudentExamPerformance]:
    by_exam: dict[str, list[dict]] = {}
    for a in attempts:
        by_exam.setdefault(a["exam_id"], []).append(a)
    exams = []
    for exam_id in sorted(by_exam):
        exam_attempts = by_exam[exam_id]
        total_awarded = sum(a["awarded_marks"] for a in exam_attempts)
        total_max = sum(a["max_marks"] for a in exam_attempts)
        fraction = (total_awarded / total_max) if total_max else 0.0
        exams.append(
            StudentExamPerformance(
                exam_id=exam_id,
                total_awarded=total_awarded,
                total_max=total_max,
                percentage=round(fraction * 100.0, 4),
                grade=grade_of(fraction),
                attempt_count=len(exam_attempts),
                question_performances=[
                    question_performance(a, pass_threshold) for a in exam_attempts
                ],
            )
        )
    return exams
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_student_analytics.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/analytics/student.py tests/test_student_analytics.py
git commit -m "feat: add per-student exam and question performance analytics"
```

---

### Task 4: Pure analytics — bloom & topic profiles, weakest ranking

**Files:**
- Modify: `app/analytics/student.py`
- Test: `tests/test_student_analytics.py`

**Interfaces:**
- Consumes: `StudentBloomSkill`, `StudentTopicSkill` (Task 1); `compute_mastery`, `topic_weight_for` from `app/analytics/mastery.py`; `weakness_component` from `app/analytics/recommender.py`; `evidence_status` from `app/analytics/evidence.py`; `TOPICS`, `BLOOM_LEVELS` from `app/analytics/taxonomy.py`.
- Produces:
  - `bloom_skill_profile(attempts, pass_threshold) -> list[StudentBloomSkill]`
  - `topic_skill_profile(attempts, pass_threshold, topic_importance=None) -> list[StudentTopicSkill]` (sorted weakest-first, `rank` 1 = weakest)
  - `rank_weakest_topics(topic_skills) -> list[str]` (weakest-first topic names)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_student_analytics.py`:

```python
from app.analytics.student import (
    bloom_skill_profile,
    rank_weakest_topics,
    topic_skill_profile,
)


def test_bloom_skill_profile_per_bloom():
    skills = {s.bloom_level: s for s in bloom_skill_profile(_stu1(), 0.5)}
    assert skills["Apply"].mastery == 1.0
    assert skills["Apply"].attempt_count == 2
    assert skills["Analyze"].attempt_count == 2
    assert skills["Analyze"].mastery == round(5.0 / 6.0, 6)
    assert skills["Understand"].mastery == 1.0


def test_topic_skill_profile_ranks_weakest_first():
    profile = topic_skill_profile(_stu1(), 0.5)
    names = [s.topic for s in profile]
    assert names[0] == "Schema Refinement"
    by_topic = {s.topic: s for s in profile}
    assert by_topic["Schema Refinement"].rank == 1
    assert by_topic["Schema Refinement"].priority_score > 0.0
    assert by_topic["SQL"].mastery == 1.0
    assert by_topic["SQL"].attempt_count == 2


def test_rank_weakest_topics_returns_weakest_first():
    profile = topic_skill_profile(_stu1(), 0.5)
    ranked = rank_weakest_topics(profile)
    assert ranked[0] == "Schema Refinement"
    assert set(ranked) >= {"Schema Refinement", "SQL"}
```

Hand-computed expectations for `stu-001`:
- 2 exams × 3 questions. Bloom Apply (01a): normalized [1.0, 1.0] → mastery 1.0. Bloom Analyze (01b): normalized [1.0, 2/3] → mastery `(1.0*3 + 2/3*3)/6 = 5/6`. Bloom Understand (02a): [1.0, 1.0] → mastery 1.0.
- Topic SQL mastery 1.0; Schema Refinement mastery `5/6` → weakness_component(5/6, None, None) = 0.5*(1-5/6) > 0 → ranked weakest. Logical Database Design mastery 1.0.
- `weakness_component` treats `None` failure/missed rates as 0.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_analytics.py -v`
Expected: FAIL with `ImportError` for `bloom_skill_profile`

- [ ] **Step 3: Write the functions**

Append to `app/analytics/student.py`:

```python
import statistics

from app.analytics.evidence import evidence_status, grade_of
from app.analytics.mastery import compute_mastery, topic_weight_for
from app.analytics.recommender import weakness_component
from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS
from app.schemas.student import (
    QuestionPerformance,
    StudentBloomSkill,
    StudentExamPerformance,
    StudentTopicSkill,
)


def _weighted_mastery(attempts: list[dict]) -> float | None:
    if not attempts:
        return None
    den = sum(a["max_marks"] for a in attempts)
    if den <= 0:
        return None
    num = sum(a["normalized_score"] * a["max_marks"] for a in attempts)
    return round(num / den, 6)


def bloom_skill_profile(attempts: list[dict], pass_threshold: float) -> list[StudentBloomSkill]:
    profile = []
    for bloom in BLOOM_LEVELS:
        subset = [a for a in attempts if a["bloom_level"] == bloom]
        scores = [a["normalized_score"] for a in subset]
        profile.append(
            StudentBloomSkill(
                bloom_level=bloom,
                mastery=_weighted_mastery(subset),
                mean=statistics.fmean(scores) if scores else None,
                attempt_count=len(subset),
                evidence_status=evidence_status(
                    statistics.fmean(scores) if scores else None,
                    1,
                    len(subset),
                    pass_threshold,
                    1,
                    1,
                ),
            )
        )
    return profile


def topic_skill_profile(
    attempts: list[dict],
    pass_threshold: float,
    topic_importance: dict[str, float] | None = None,
) -> list[StudentTopicSkill]:
    profile = []
    for topic in TOPICS:
        subset = [a for a in attempts if topic_weight_for(a, topic) > 0]
        scores = [a["normalized_score"] for a in subset]
        missed = [c for a in subset for c in a.get("criteria_breakdown", [])]
        missed_rate = (
            sum(1 for c in missed if not c["met"]) / len(missed) if missed else None
        )
        failure_rate = (
            sum(1 for s in scores if s < 0.5) / len(scores) if scores else None
        )
        mastery = compute_mastery(attempts, topic)
        profile.append(
            StudentTopicSkill(
                topic=topic,
                mastery=mastery,
                mean=statistics.fmean(scores) if scores else None,
                attempt_count=len(subset),
                evidence_status=evidence_status(
                    statistics.fmean(scores) if scores else None,
                    1,
                    len(subset),
                    pass_threshold,
                    1,
                    1,
                ),
                rank=0,
                priority_score=weakness_component(mastery, failure_rate, missed_rate),
            )
        )
    profile.sort(key=lambda s: (-s.priority_score, s.topic))
    for i, skill in enumerate(profile, start=1):
        skill.rank = i
    return profile


def rank_weakest_topics(topic_skills: list[StudentTopicSkill]) -> list[str]:
    return [s.topic for s in sorted(topic_skills, key=lambda s: (-s.priority_score, s.topic))]
```

Note: the existing imports `from app.analytics.evidence import grade_of` at the top of the file must be extended to also import `evidence_status`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_student_analytics.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add app/analytics/student.py tests/test_student_analytics.py
git commit -m "feat: add bloom and topic skill profiles with weakest-first ranking"
```

---

### Task 5: Pure analytics — deterministic study actions & cohort comparison

**Files:**
- Modify: `app/analytics/student.py`
- Test: `tests/test_student_analytics.py`

**Interfaces:**
- Consumes: `StudentStudyAction` (Task 1); `compute_mastery`, `topic_weight_for` from `app/analytics/mastery.py`; `TOPICS`, `BLOOM_LEVELS` from `app/analytics/taxonomy.py`.
- Produces:
  - `deterministic_study_actions(weakest_topics) -> list[StudentStudyAction]` (source="deterministic")
  - `cohort_comparison(student_attempts, all_attempts) -> dict` with keys `topics` and `blooms`, each mapping name → `{"student_mastery", "cohort_mastery", "delta", "percentile"}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_student_analytics.py`:

```python
import pytest

from app.analytics.student import cohort_comparison, deterministic_study_actions


def test_deterministic_study_actions_shape():
    actions = deterministic_study_actions(["Schema Refinement", "SQL"])
    assert len(actions) == 2
    assert actions[0].topic == "Schema Refinement"
    assert actions[0].source == "deterministic"
    assert actions[0].practice_topics == ["Schema Refinement", "SQL"]


def test_deterministic_study_actions_caps_at_three():
    actions = deterministic_study_actions(["A", "B", "C", "D"])
    assert len(actions) == 3


def test_cohort_comparison_percentile_and_delta():
    comparison = cohort_comparison(_stu1(), expected_attempt_records)
    sql = comparison["topics"]["SQL"]
    assert sql["student_mastery"] == 1.0
    assert sql["cohort_mastery"] == pytest.approx(round(8.5 / 12.0, 6))
    assert sql["delta"] == pytest.approx(1.0 - 8.5 / 12.0)
    assert sql["percentile"] == pytest.approx(10 / 12)
    assert "Apply" in comparison["blooms"]
```

Hand-computed expectations:
- Cohort SQL per-student masteries (2 SQL attempts each, both max_marks 2.0): [1.0, 0.875, 0.875, 0.5, 0.625, 0.625, 0.75, 0.75, 1.0, 0.875, 0.375, 0.25]; sum = 8.5, so cohort_mastery = 8.5/12.
- stu-001 SQL mastery = 1.0. Students strictly below 1.0: 10 of 12 → percentile = 10/12.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_analytics.py::test_cohort_comparison_percentile_and_delta -v`
Expected: FAIL with `ImportError` for `cohort_comparison`

- [ ] **Step 3: Write the functions**

Append to `app/analytics/student.py`:

```python
from app.schemas.student import StudentStudyAction


def deterministic_study_actions(weakest_topics: list[str]) -> list[StudentStudyAction]:
    templates = [
        "Review core concepts",
        "Practice exam-style questions",
        "Revisit missed criteria",
    ]
    actions = []
    for i, topic in enumerate(weakest_topics[:3]):
        actions.append(
            StudentStudyAction(
                action=templates[i],
                topic=topic,
                rationale=f"{topic} is one of your weakest topics and should be prioritized in your exam preparation.",
                practice_topics=weakest_topics[:3],
                source="deterministic",
            )
        )
    return actions


def _student_masteries(all_attempts: list[dict]) -> dict[str, list[dict]]:
    by_student: dict[str, list[dict]] = {}
    for a in all_attempts:
        by_student.setdefault(a["student_key"], []).append(a)
    return by_student


def _percentile(student_value: float, others: list[float | None]) -> float | None:
    present = [v for v in others if v is not None]
    if not present:
        return None
    return sum(1 for v in present if v < student_value) / len(present)


def cohort_comparison(student_attempts: list[dict], all_attempts: list[dict]) -> dict:
    by_student = _student_masteries(all_attempts)

    topics: dict[str, dict] = {}
    for topic in TOPICS:
        student_mastery = compute_mastery(student_attempts, topic)
        if student_mastery is None:
            continue
        cohort_mastery = compute_mastery(all_attempts, topic)
        others = [
            compute_mastery(att, topic) for att in by_student.values()
        ]
        topics[topic] = {
            "student_mastery": student_mastery,
            "cohort_mastery": cohort_mastery,
            "delta": round(student_mastery - cohort_mastery, 6)
            if cohort_mastery is not None
            else None,
            "percentile": _percentile(student_mastery, others),
        }

    blooms: dict[str, dict] = {}
    for bloom in BLOOM_LEVELS:
        student_mastery = _weighted_mastery(
            [a for a in student_attempts if a["bloom_level"] == bloom]
        )
        if student_mastery is None:
            continue
        cohort_mastery = _weighted_mastery(
            [a for a in all_attempts if a["bloom_level"] == bloom]
        )
        others = [
            _weighted_mastery([a for a in att if a["bloom_level"] == bloom])
            for att in by_student.values()
        ]
        blooms[bloom] = {
            "student_mastery": student_mastery,
            "cohort_mastery": cohort_mastery,
            "delta": round(student_mastery - cohort_mastery, 6)
            if cohort_mastery is not None
            else None,
            "percentile": _percentile(student_mastery, others),
        }

    return {"topics": topics, "blooms": blooms}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_student_analytics.py -v`
Expected: PASS (all tests in file)

- [ ] **Step 5: Commit**

```bash
git add app/analytics/student.py tests/test_student_analytics.py
git commit -m "feat: add deterministic study actions and cohort comparison"
```

---

### Task 6: Service layer — build_student_dashboard

**Files:**
- Create: `app/services/student_dashboard.py`
- Test: `tests/test_student_dashboard_service.py`

**Interfaces:**
- Consumes: `find_attempts_by_student`, `find_attempts`, `latest_run_id` (Task 2); all `analytics.student` functions (Tasks 3-5); `StudentDashboard` (Task 1); `llm_service.study_actions` (existing); `settings.pass_threshold`.
- Produces:
  - `class StudentDashboardNotFound(Exception)`
  - `async build_student_dashboard(db, student_key, run_id=None, include_llm=False) -> StudentDashboard`

- [ ] **Step 1: Write the failing test**

Create `tests/test_student_dashboard_service.py`:

```python
from datetime import datetime, timezone

import pytest

from app.db.repository import insert_attempts, save_run
from app.schemas.student import StudentDashboard
from app.services import student_dashboard
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard
from tests.fixtures.fixture_data import COURSE, expected_attempt_records

FAKE_RUN = "run-fixture"


async def _seed(test_db):
    await insert_attempts(test_db, expected_attempt_records)
    await save_run(
        test_db,
        {
            "run_id": FAKE_RUN,
            "course_code": COURSE,
            "exam_id": "exam-2023",
            "status": "ready",
            "created_at": datetime.now(timezone.utc),
        },
    )


async def test_build_dashboard_returns_full_dashboard(test_db):
    await _seed(test_db)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN)
    assert isinstance(dash, StudentDashboard)
    assert dash.student_key == "stu-001"
    assert dash.course_code == COURSE
    assert len(dash.exams) == 2
    assert len(dash.bloom_skills) == 6
    assert len(dash.topic_skills) == 8
    assert dash.weakest_topics
    assert dash.recommendations
    assert all(r.source == "deterministic" for r in dash.recommendations)
    assert "topics" in dash.cohort_comparison


async def test_build_dashboard_resolves_latest_run(test_db):
    await _seed(test_db)
    dash = await build_student_dashboard(test_db, "stu-001")
    assert dash.run_id == FAKE_RUN


async def test_build_dashboard_unknown_student_raises(test_db):
    await _seed(test_db)
    with pytest.raises(StudentDashboardNotFound):
        await build_student_dashboard(test_db, "nobody", run_id=FAKE_RUN)


async def test_build_dashboard_llm_failure_falls_back_to_deterministic(test_db, monkeypatch):
    await _seed(test_db)

    async def raise_unavailable(*a, **k):
        raise Exception("ollama down")

    monkeypatch.setattr(student_dashboard, "study_actions", raise_unavailable)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN, include_llm=True)
    assert all(r.source == "deterministic" for r in dash.recommendations)


async def test_build_dashboard_llm_ok_uses_llm_source(test_db, monkeypatch):
    await _seed(test_db)

    class FakeActions:
        def model_dump(self):
            return {
                "student_key": "stu-001",
                "actions": [
                    {"action": "review", "topic": "Schema Refinement", "rationale": "r", "practice_topics": ["joins"]}
                ],
            }

    async def fake_study_actions(student_key, weak_topics, evidence):
        return {"status": "ok", **FakeActions().model_dump()}

    monkeypatch.setattr(student_dashboard, "study_actions", fake_study_actions)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN, include_llm=True)
    assert dash.recommendations[0].source == "llm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_student_dashboard_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.student_dashboard'`

- [ ] **Step 3: Write the service**

Create `app/services/student_dashboard.py`:

```python
import logging

from app.analytics import student as student_analytics
from app.config import settings
from app.db.repository import find_attempts, find_attempts_by_student, latest_run_id
from app.schemas.student import StudentDashboard, StudentStudyAction
from app.services.llm_service import study_actions

logger = logging.getLogger(__name__)


class StudentDashboardNotFound(Exception):
    pass


async def build_student_dashboard(
    db, student_key: str, run_id: str | None = None, include_llm: bool = False
) -> StudentDashboard:
    if run_id is None:
        run_id = await latest_run_id(db)
    if run_id is None:
        raise StudentDashboardNotFound("no analysis run found")

    attempts = await find_attempts_by_student(db, run_id, student_key)
    if not attempts:
        raise StudentDashboardNotFound("no attempts found for student")

    all_attempts = await find_attempts(db, run_id)
    pass_threshold = settings.pass_threshold

    exams = student_analytics.student_exam_performances(attempts, pass_threshold)
    bloom_skills = student_analytics.bloom_skill_profile(attempts, pass_threshold)
    topic_skills = student_analytics.topic_skill_profile(attempts, pass_threshold)
    weakest = student_analytics.rank_weakest_topics(topic_skills)
    recommendations = student_analytics.deterministic_study_actions(weakest)

    if include_llm:
        try:
            result = await study_actions(student_key, weakest[:3], {"weak_topics": weakest[:3]})
            if result.get("status") == "ok":
                recommendations = [
                    StudentStudyAction(**{**action, "source": "llm"})
                    for action in result.get("actions", [])
                ]
        except Exception:
            logger.exception("LLM study actions failed; keeping deterministic")

    return StudentDashboard(
        student_key=student_key,
        course_code=attempts[0]["course_code"],
        run_id=run_id,
        exams=exams,
        bloom_skills=bloom_skills,
        topic_skills=topic_skills,
        weakest_topics=weakest,
        cohort_comparison=student_analytics.cohort_comparison(attempts, all_attempts),
        recommendations=recommendations,
    )
```

Note: `study_actions` (from `llm_service`) already catches `OllamaUnavailable` and returns `{"status": "degraded", ...}`, so the `try/except` is a safety net for other failures. The monkeypatched service in tests raises a plain `Exception`, so importing `study_actions` at module level (as above) lets tests patch `student_dashboard.study_actions`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_student_dashboard_service.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add app/services/student_dashboard.py tests/test_student_dashboard_service.py
git commit -m "feat: add student dashboard service with deterministic and LLM recommendations"
```

---

### Task 7: FastAPI app, dependencies, and dashboard endpoint

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/deps.py`
- Create: `app/api/dashboard.py`
- Create: `app/main.py`
- Test: `tests/test_api_dashboard.py`

**Interfaces:**
- Consumes: `get_db` (this task); `build_student_dashboard`, `StudentDashboardNotFound` (Task 6); `StudentDashboard` (Task 1).
- Produces:
  - `app.api.deps.get_db` — dependency returning the Mongo database handle.
  - `app.api.dashboard.router` — `APIRouter(prefix="/students")`.
  - `app.main.app` — FastAPI app with the router under `/api`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_api_dashboard.py`:

```python
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.api import deps
from app.db.repository import insert_attempts, save_run
from app.main import app
from tests.fixtures.fixture_data import COURSE, expected_attempt_records

FAKE_RUN = "run-fixture"


async def test_dashboard_endpoint_happy_path(test_db):
    await insert_attempts(test_db, expected_attempt_records)
    await save_run(
        test_db,
        {
            "run_id": FAKE_RUN,
            "course_code": COURSE,
            "exam_id": "exam-2023",
            "status": "ready",
            "created_at": datetime.now(timezone.utc),
        },
    )

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        client = TestClient(app)
        response = client.get(f"/api/students/stu-001/dashboard?run_id={FAKE_RUN}")
        assert response.status_code == 200
        body = response.json()
        assert body["student_key"] == "stu-001"
        assert len(body["exams"]) == 2
        assert body["recommendations"][0]["source"] == "deterministic"
    finally:
        app.dependency_overrides.clear()


async def test_dashboard_endpoint_unknown_student_404(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        client = TestClient(app)
        response = client.get("/api/students/nobody/dashboard?run_id=run-fixture")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_api_dashboard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api'` or `app.main`

- [ ] **Step 3: Write the app files**

Create `app/api/__init__.py` (empty file).

Create `app/api/deps.py`:

```python
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings

_client: AsyncIOMotorClient | None = None


def _get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db():
    return _get_client()[settings.mongodb_db]
```

Create `app/api/dashboard.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.schemas.student import StudentDashboard
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_key}/dashboard", response_model=StudentDashboard)
async def student_dashboard(
    student_key: str,
    run_id: str | None = None,
    include_llm: bool = False,
    db=Depends(get_db),
) -> StudentDashboard:
    try:
        return await build_student_dashboard(db, student_key, run_id, include_llm)
    except StudentDashboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

Create `app/main.py`:

```python
from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router

app = FastAPI(title="DBMS Analytics API", version="1.0.0")
app.include_router(dashboard_router, prefix="/api")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_api_dashboard.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full suite**

Run: `pytest -v`
Expected: all tests PASS (existing + new).

- [ ] **Step 6: Commit**

```bash
git add app/api/ app/main.py tests/test_api_dashboard.py
git commit -m "feat: add student dashboard REST endpoint"
```

---

### Task 8: Manual smoke test with sample data

**Files:**
- No code changes; run the existing sample-data pipeline and hit the endpoint.

- [ ] **Step 1: Run the sample pipeline**

Run: `python run_sample.py`
Expected: prints run status, catalog, snapshot, recommendations. Note the printed `run_id` and confirm attempts were written.

- [ ] **Step 2: Start the API**

Run: `uvicorn app.main:app --reload`
Expected: server starts on `http://127.0.0.1:8000`, docs at `/docs`.

- [ ] **Step 3: Call the endpoint**

Using the run_id printed in Step 1 (or the `RUN_ID` printed value), call:

```bash
curl "http://127.0.0.1:8000/api/students/IT2040-IT21001234/dashboard?run_id=<RUN_ID>"
```

Expected: JSON `StudentDashboard` with `exams`, `bloom_skills`, `topic_skills`, `weakest_topics`, `cohort_comparison`, `recommendations`. Confirm the student_key matches the sample submission (`IT2040-IT21001234`, see `app/sample_data/submission.json`).

- [ ] **Step 4: Verify 404 path**

```bash
curl "http://127.0.0.1:8000/api/students/does-not-exist/dashboard?run_id=<RUN_ID>"
```

Expected: HTTP 404 with detail message.

- [ ] **Step 5: Stop the server**

Stop uvicorn (Ctrl+C).
