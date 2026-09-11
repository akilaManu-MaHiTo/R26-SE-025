# Dashboard Architecture Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure the backend to the approved data architecture in `docs/superpowers/specs/2026-08-12-dashboard-architecture-restructure-design.md`: reshape the persisted student document, generate student analysis on first dashboard access (cached in MongoDB), replace the old cohort pipeline with spec-shaped exam analytics plus lecturer endpoints, and add on-request personalized question generation.

**Architecture:** Three sequential phases. Phase 1 reshapes the `student_analytics` document (spec `studentExamAnalysis`) and adds on-demand generation through `ensure_student_analytics`. Phase 2 reshapes `analytics_snapshots` into the spec `examAnalytics` shape via a new `compute_exam_analytics` generator, adds a lecturer API router, and removes the old `run_analytics` pipeline. Phase 3 adds a `generatedQuestions` collection, a practice-question generation service, and POST/GET endpoints.

**Tech Stack:** Python 3.13, FastAPI 0.141.1, Pydantic 2.13.4, Motor 3.7.1/PyMongo 4.17.0, pytest 9.1.1, Qwen through the existing Ollama JSON client.

## Global Constraints

- Collection names are kept as they are today: `courses`, `rubricCollection`, `submissions`, `student_analytics`, `analytics_snapshots`, plus a new `generatedQuestions`. No collection renames.
- `exam_id` is the stable string key `"{course_code}@{session_name}"` (e.g. `IT2040@Final Examination 2021`). It is used consistently in `student_analytics`, `analytics_snapshots`, and `generatedQuestions`.
- Status thresholds (configurable later): `80–100 Strong`, `60–79 Developing`, `40–59 Needs Improvement`, `0–39 Critical`.
- All totals, percentages, weighted averages, status labels, counts, rankings, class statistics, pass rates, attention areas, and insights are computed in Python; model output never supplies numeric performance fields.
- Qwen is responsible only for question Bloom/topic/subtopic semantics, personalized learning insights, and Level-3 practice-question generation.
- `student_analytics` identity is `student_id + course.code + exam_id`; writes are idempotent replacements.
- Frontend changes, real authentication, creating an `exams` collection, regrading, and renaming collections are out of scope.
- Required verification excludes `tests/test_ollama_live.py` and disables optional embedding-model loading.
- Do not modify the user's `.gitignore`.

## File Map

**Phase 1 — reshaped student document + on-demand generation**

- Replace: `app/schemas/student.py` — new canonical document shape.
- Modify: `app/analytics/student_document.py` — four-bucket thresholds, structured gaps, strategy.
- Modify: `app/services/student_pipeline.py` — extract reusable per-student builder; new assembly.
- Modify: `app/services/llm_service.py` — insight assembly unchanged call, no numeric fields.
- Modify: `app/db/repository.py` — `student_analytics` identity by `exam_id`; submission lookup helpers.
- Replace: `app/services/student_dashboard.py` — on-demand `ensure_student_analytics`.
- Modify: `app/api/dashboard.py` — on-demand dashboard endpoint.
- Modify: `run_sample.py` — identity-based cleanup and counts.
- Remove: `app/analytics/student.py` — obsolete computed-dashboard module importing removed models.
- Tests: replace `test_schemas_student.py`, `test_student_dashboard_service.py`, `test_api_dashboard.py`; update `test_student_document_analytics.py`, `test_student_pipeline.py`, `test_repository.py`, `test_run_sample.py`, `test_llm_student_analysis.py`.

**Phase 2 — lecturer exam analytics + student list**

- Create: `app/schemas/exam_analytics.py` — lecturer analytics schema.
- Create: `app/analytics/exam_analytics.py` — deterministic class-level math.
- Create: `app/services/exam_analytics.py` — `compute_exam_analytics` generator.
- Create: `app/api/lecturer.py` — lecturer router.
- Modify: `app/db/repository.py` — exam analytics save/find, exam submissions, student list.
- Modify: `app/main.py` — include lecturer router.
- Modify: `run_sample.py` — compute exam analytics after materialization.
- Remove: `app/services/analytics.py` (`run_analytics`), `app/analytics/mastery.py`, `app/analytics/evidence.py`, `app/analytics/coverage.py`, `app/analytics/recommender.py`, `app/analytics/student.py`, `app/ingestion/transformer.py`, `app/schemas/derived.py`; update `app/ingestion/__init__.py`.
- Tests: create `test_exam_analytics.py`, `test_exam_analytics_service.py`, `test_api_lecturer.py`; remove `test_analytics_service.py`, `test_mastery.py`, `test_evidence.py`, `test_coverage.py`, `test_recommender.py`, `test_schemas_derived.py`, `test_ingestion.py`.

**Phase 3 — personalized question generation**

- Create: `app/schemas/generated_questions.py`.
- Create: `app/llm/roles/generate_practice.py`.
- Create: `app/services/practice_questions.py`.
- Modify: `app/services/llm_service.py` — `generate_practice_questions`.
- Modify: `app/db/repository.py` — `generatedQuestions` upsert/find.
- Modify: `app/api/dashboard.py` — practice-question endpoints.
- Tests: create `test_llm_practice_questions.py`, `test_practice_questions.py`, `test_api_practice_questions.py`; extend `test_repository.py`.

---

## Phase 1 — Reshaped Student Document + On-Demand Generation

### Task 1: Canonical reshaped student schema

**Files:**
- Replace: `app/schemas/student.py`
- Replace: `tests/test_schemas_student.py`

**Interfaces:**
- Consumes: plain dictionaries assembled by the pipeline.
- Produces: `StudentAnalyticsDocument.model_validate(data)` and JSON-safe `model_dump(mode="json")`.

- [ ] **Step 1: Write the failing schema contract tests**

Replace `tests/test_schemas_student.py` with tests for the new top-level contract:

```python
import pytest
from pydantic import ValidationError

from app.schemas.student import StudentAnalyticsDocument


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "overall_performance": {"score": 65.0, "maximum": 100.0, "percentage": 65.0, "status": "Needs Improvement"},
        "question_performance": [
            {
                "question_id": "Q01",
                "question_no": "01",
                "question_text": "Explain conceptual design.",
                "topic": "DBMS Design",
                "subtopic": "Conceptual design",
                "bloom_analysis": {"level": "Understand", "confidence": 0.9, "reason": "It asks for an explanation."},
                "performance": {"score": 6.0, "max_score": 8.0, "percentage": 75.0},
                "criteria_performance": [
                    {"criterion": "Explains Conceptual Design", "max_marks": 4.0, "awarded_marks": 3.0, "achieved": True},
                ],
            }
        ],
        "topic_performance": [
            {"topic": "JDBC", "questions_attempted": 2, "score": 19.0, "max_score": 25.0, "percentage": 76.0, "status": "Strong"}
        ],
        "bloom_performance": [
            {"level": "Understand", "questions_attempted": 1, "average_score": 75.0, "status": "Developing"}
        ],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "strong_topics": ["JDBC"],
            "developing_topics": ["DBMS Design"],
            "weak_topics": ["Database Programming"],
            "critical_topics": ["SQL"],
            "learning_gaps": [
                {"topic": "SQL", "subtopic": "Authentication and Authorization", "priority": "Critical"}
            ],
        },
        "recommendations": [
            {"topic": "SQL", "priority": "Critical", "action": "Review SQL Server authentication."}
        ],
        "next_question_strategy": {
            "recommended_topics": ["SQL", "Database Programming"],
            "recommended_bloom_levels": ["Understand", "Apply"],
            "recommended_difficulty": "Medium",
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b", "bloom_model_type": "base",
            "grading_source": "colab", "rag_context_used": True,
        },
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


def test_student_analytics_serializes_exact_top_level_contract():
    document = StudentAnalyticsDocument(**valid_document())
    assert set(document.model_dump(mode="json")) == {
        "student_id", "exam_id", "course", "overall_performance",
        "question_performance", "topic_performance", "bloom_performance",
        "learning_analysis", "recommendations", "next_question_strategy",
        "model_metadata", "generated_at", "analysis_version",
    }
    assert document.overall_performance.percentage == 65.0
    assert document.question_performance[0].criteria_performance[0].achieved is True
    assert document.next_question_strategy.recommended_bloom_levels == ["Understand", "Apply"]


def test_student_analytics_rejects_invalid_percentage():
    data = valid_document()
    data["overall_performance"]["percentage"] = 101.0
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


def test_student_analytics_rejects_unknown_bloom_level():
    data = valid_document()
    data["question_performance"][0]["bloom_analysis"]["level"] = "Guess"
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("overall_performance", "score"), 101.0),
        (("question_performance", 0, "performance", "score"), 9.0),
        (("question_performance", 0, "criteria_performance", 0, "awarded_marks"), 5.0),
    ],
)
def test_student_analytics_rejects_scores_above_their_maximum(path, value):
    data = valid_document()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)
```

- [ ] **Step 2: Run the schema tests and verify the old model fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py -q`
Expected: FAIL because the new models (`overall_performance`, `question_performance`, `exam_id`, ...) do not exist.

- [ ] **Step 3: Implement the canonical nested models**

Replace `app/schemas/student.py` with:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
PerformanceStatus = Literal["Strong", "Developing", "Needs Improvement", "Critical"]
RecommendationPriority = Literal["Critical", "High", "Medium", "Low"]
QuestionDifficulty = Literal["Easy", "Medium", "Hard"]


class CourseInfo(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class OverallPerformance(BaseModel):
    score: float = Field(ge=0)
    maximum: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus

    @model_validator(mode="after")
    def score_does_not_exceed_maximum(self):
        if self.score > self.maximum:
            raise ValueError("score cannot exceed maximum")
        return self


class BloomAnalysis(BaseModel):
    level: BloomLevel
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class Performance(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def score_does_not_exceed_max_score(self):
        if self.score > self.max_score:
            raise ValueError("score cannot exceed max_score")
        return self


class CriterionPerformance(BaseModel):
    criterion: str = Field(min_length=1)
    max_marks: float = Field(gt=0)
    awarded_marks: float = Field(ge=0)
    achieved: bool

    @model_validator(mode="after")
    def awarded_marks_do_not_exceed_max_marks(self):
        if self.awarded_marks > self.max_marks:
            raise ValueError("awarded_marks cannot exceed max_marks")
        return self


class QuestionPerformance(BaseModel):
    question_id: str = Field(min_length=1)
    question_no: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    bloom_analysis: BloomAnalysis
    performance: Performance
    criteria_performance: list[CriterionPerformance] = Field(default_factory=list)


class TopicPerformance(BaseModel):
    topic: str = Field(min_length=1)
    questions_attempted: int = Field(ge=0)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus

    @model_validator(mode="after")
    def score_does_not_exceed_max_score(self):
        if self.score > self.max_score:
            raise ValueError("score cannot exceed max_score")
        return self


class BloomPerformance(BaseModel):
    level: BloomLevel
    questions_attempted: int = Field(ge=0)
    average_score: float = Field(ge=0, le=100)
    status: PerformanceStatus


class LearningGap(BaseModel):
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    priority: RecommendationPriority


class LearningAnalysis(BaseModel):
    overall_performance: PerformanceStatus
    strong_topics: list[str] = Field(default_factory=list)
    developing_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    critical_topics: list[str] = Field(default_factory=list)
    learning_gaps: list[LearningGap] = Field(default_factory=list)


class Recommendation(BaseModel):
    topic: str = Field(min_length=1)
    priority: RecommendationPriority
    action: str = Field(min_length=1)


class NextQuestionStrategy(BaseModel):
    recommended_topics: list[str] = Field(default_factory=list)
    recommended_bloom_levels: list[BloomLevel] = Field(default_factory=list)
    recommended_difficulty: QuestionDifficulty
    number_of_questions: Literal[5]


class ModelMetadata(BaseModel):
    bloom_model: str = Field(min_length=1)
    bloom_model_type: str = Field(min_length=1)
    grading_source: str = Field(min_length=1)
    rag_context_used: bool


class StudentAnalyticsDocument(BaseModel):
    student_id: str = Field(min_length=1)
    exam_id: str = Field(min_length=1)
    course: CourseInfo
    overall_performance: OverallPerformance
    question_performance: list[QuestionPerformance] = Field(default_factory=list)
    topic_performance: list[TopicPerformance] = Field(default_factory=list)
    bloom_performance: list[BloomPerformance] = Field(default_factory=list)
    learning_analysis: LearningAnalysis
    recommendations: list[Recommendation] = Field(default_factory=list)
    next_question_strategy: NextQuestionStrategy
    model_metadata: ModelMetadata
    generated_at: datetime
    analysis_version: str = Field(min_length=1)
```

- [ ] **Step 4: Run the schema tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py -q`
Expected: PASS.

- [ ] **Step 5: Run compileall and fix the now-broken importer**

Run: `.\.venv\Scripts\python.exe -m compileall -q app`
Expected: `app/analytics/student.py` fails to compile because it imports removed models (`QuestionPerformance`, `StudentBloomSkill`, `StudentExamPerformance`, `StudentTopicSkill`, `StudentStudyAction`).

- [ ] **Step 6: Remove the obsolete computed-dashboard module**

Delete `app/analytics/student.py`.

- [ ] **Step 7: Commit**

```powershell
git add app/schemas/student.py app/analytics/student.py tests/test_schemas_student.py
git commit -m "feat: reshape canonical student analytics schema"
```

---

### Task 2: Deterministic four-bucket analytics with structured gaps

**Files:**
- Modify: `app/analytics/student_document.py`
- Update: `tests/test_student_document_analytics.py`

**Interfaces:**
- Consumes: `NormalizedStudentInput` and `semantics_by_question: dict[str, QuestionSemantics]`.
- Produces: `build_numeric_analysis(normalized, semantics_by_question) -> NumericStudentAnalysis` using the new schema models; `performance_status(value: float) -> PerformanceStatus`; fallback generators.

- [ ] **Step 1: Write failing threshold and gap tests**

Append to `tests/test_student_document_analytics.py`:

```python
import pytest

from app.analytics.student_document import performance_status


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [
        (39.99, "Critical"),
        (40.0, "Needs Improvement"),
        (59.99, "Needs Improvement"),
        (60.0, "Developing"),
        (79.99, "Developing"),
        (80.0, "Strong"),
    ],
)
def test_performance_status_four_bucket_boundaries(percentage, expected):
    assert performance_status(percentage) == expected
```

- [ ] **Step 2: Run the analytics tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_document_analytics.py -q`
Expected: FAIL because `performance_status` still uses 75/50 thresholds.

- [ ] **Step 3: Implement four-bucket thresholds**

Update the constants and `performance_status` in `app/analytics/student_document.py`:

```python
STRONG_THRESHOLD = 80.0
DEVELOPING_THRESHOLD = 60.0
IMPROVEMENT_THRESHOLD = 40.0


def performance_status(value: float) -> PerformanceStatus:
    if value >= STRONG_THRESHOLD:
        return "Strong"
    if value >= DEVELOPING_THRESHOLD:
        return "Developing"
    if value >= IMPROVEMENT_THRESHOLD:
        return "Needs Improvement"
    return "Critical"
```

- [ ] **Step 4: Write failing structured-gap and strategy tests**

Append to `tests/test_student_document_analytics.py`:

```python
def test_learning_analysis_has_four_topic_buckets():
    analysis = build_numeric_analysis(two_question_input(), semantics())
    buckets = analysis.learning_analysis
    assert isinstance(buckets.strong_topics, list)
    assert isinstance(buckets.developing_topics, list)
    assert isinstance(buckets.weak_topics, list)
    assert isinstance(buckets.critical_topics, list)


def test_learning_gaps_are_structured_objects():
    analysis = build_numeric_analysis(two_question_input(), semantics())
    assert analysis.learning_analysis.learning_gaps
    first = analysis.learning_analysis.learning_gaps[0]
    assert {"topic", "subtopic", "priority"} == set(first.model_dump())
    assert first.priority in {"Critical", "High", "Medium", "Low"}


def test_next_question_strategy_has_bloom_level_list():
    analysis = build_numeric_analysis(two_question_input(), semantics())
    strategy = analysis.next_question_strategy
    assert strategy.number_of_questions == 5
    assert isinstance(strategy.recommended_bloom_levels, list)
    assert all(level in {"Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"} for level in strategy.recommended_bloom_levels)
```

- [ ] **Step 5: Run the new tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_document_analytics.py -q`
Expected: FAIL because `NumericStudentAnalysis` still builds `LearningAnalysis` with the old single-bucket fields.

- [ ] **Step 6: Implement structured learning analysis and strategy**

Update `app/analytics/student_document.py`:

1. Rename the bucket derivation inside `build_numeric_analysis`:

```python
strong_topics = [topic.topic for topic in topics if topic.status == "Strong"]
developing_topics = [topic.topic for topic in topics if topic.status == "Developing"]
weak_topics = [topic.topic for topic in topics if topic.status == "Needs Improvement"]
critical_topics = [topic.topic for topic in topics if topic.status == "Critical"]
```

2. Replace `fallback_learning_gaps(questions)` so it returns `list[LearningGap]` with `priority` derived from the question status:

```python
_PRIORITY_BY_STATUS = {
    "Critical": "Critical",
    "Needs Improvement": "High",
    "Developing": "Medium",
    "Strong": "Low",
}


def fallback_learning_gaps(questions: list[QuestionAnalysis]) -> list[LearningGap]:
    seen: set[tuple[str, str]] = set()
    gaps: list[LearningGap] = []
    for question in questions:
        missed = [
            criterion
            for criterion in question.criteria_performance
            if criterion.awarded_marks < criterion.max_marks
        ]
        priority = _PRIORITY_BY_STATUS[performance_status(question.performance.percentage)]
        for criterion in missed:
            key = (question.topic, criterion.criterion)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                LearningGap(
                    topic=question.topic,
                    subtopic=criterion.criterion,
                    priority=priority,
                )
            )
        if not missed and priority != "Low":
            key = (question.topic, question.subtopic)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                LearningGap(
                    topic=question.topic,
                    subtopic=question.subtopic,
                    priority=priority,
                )
            )
    return gaps
```

3. Replace `fallback_recommendations` so `Recommendation` no longer carries `bloom_level`:

```python
def fallback_recommendations(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> list[Recommendation]:
    weak_topics = [topic for topic in topics if topic.status != "Strong"]
    if not weak_topics:
        return []
    return [
        Recommendation(
            topic=topic.topic,
            priority=_PRIORITY_BY_STATUS[topic.status],
            action=f"Review {topic.topic} and practice {weakest_bloom(topic, blooms)} questions.",
        )
        for topic in weak_topics
    ]


def weakest_bloom(_topic: TopicPerformance, blooms: list[BloomPerformance]) -> str:
    return min(blooms, key=lambda bloom: bloom.average_score).level
```

4. Replace `fallback_generation_target` so `NextQuestionStrategy` carries a bloom-level list:

```python
def fallback_generation_target(
    topics: list[TopicPerformance], blooms: list[BloomPerformance]
) -> NextQuestionStrategy:
    if not topics or not blooms:
        raise ValueError("topic and Bloom performance are required")
    weakest = min(blooms, key=lambda bloom: bloom.average_score)
    weak_topics = [topic.topic for topic in topics if topic.status != "Strong"]
    recommended_topics = weak_topics or [min(topics, key=lambda topic: topic.percentage).topic]
    recommended_bloom_levels = [weakest.level] + [
        bloom.level for bloom in blooms if bloom.level != weakest.level and bloom.status != "Strong"
    ]
    difficulty = {
        "Critical": "Easy",
        "Needs Improvement": "Medium",
        "Developing": "Medium",
        "Strong": "Hard",
    }[weakest.status]
    return NextQuestionStrategy(
        recommended_topics=recommended_topics,
        recommended_bloom_levels=recommended_bloom_levels,
        recommended_difficulty=difficulty,
        number_of_questions=5,
    )
```

5. Update `NumericStudentAnalysis` field types and `LearningAnalysis` construction in `build_numeric_analysis` to use `strong_topics`, `developing_topics`, `weak_topics`, `critical_topics`, and structured `learning_gaps`. Remove `weak_bloom_levels` and `weak_subtopics` from `LearningAnalysis`.

- [ ] **Step 7: Run the analytics tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_document_analytics.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add app/analytics/student_document.py tests/test_student_document_analytics.py
git commit -m "feat: four-bucket statuses and structured learning gaps"
```

---

### Task 3: Pipeline assembly for the new document shape

**Files:**
- Modify: `app/services/student_pipeline.py`
- Modify: `app/services/llm_service.py` (insight assembly only)
- Update: `tests/test_student_pipeline.py`
- Update: `tests/test_llm_student_analysis.py`

**Interfaces:**
- Consumes: `NumericStudentAnalysis`, `StudentInsightResponse` (unchanged), `NormalizedStudentInput`.
- Produces: `_assemble_document(normalized, numeric, insights, submission) -> dict` producing the new shape, and a reusable per-student builder.

- [ ] **Step 1: Write failing assembly tests**

Update the pipeline tests' expected top-level keys. Add to `tests/test_student_pipeline.py`:

```python
def test_assemble_document_produces_new_top_level_shape():
    from app.services.student_pipeline import _assemble_document

    document = _assemble_document(
        _normalized_input(), _numeric_analysis(), {"status": "degraded", "reason": "offline_test"}, _submission()
    )
    assert set(document) == {
        "student_id", "exam_id", "course", "overall_performance",
        "question_performance", "topic_performance", "bloom_performance",
        "learning_analysis", "recommendations", "next_question_strategy",
        "model_metadata", "generated_at", "analysis_version",
    }
    assert document["exam_id"] == "IT2040@Final Examination 2021"
```

- [ ] **Step 2: Run the pipeline tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_pipeline.py -q`
Expected: FAIL because `_assemble_document` emits the old shape.

- [ ] **Step 3: Update `_assemble_document`**

In `app/services/student_pipeline.py`:

1. Compute `exam_id`:

```python
exam_id = f"{normalized.course_code}@{normalized.session_name}"
```

2. `document = numeric.model_dump(mode="json")` already produces the new section keys because `NumericStudentAnalysis` uses the new schema. After the numeric dump, override:

```python
document.update(
    student_id=normalized.student_id,
    exam_id=exam_id,
    course={"code": normalized.course_code, "name": normalized.course_name},
    generated_at=datetime.now(timezone.utc).isoformat(),
    analysis_version="1.0",
)
```

3. When validated insights exist, map them into the new fields only:

```python
document["learning_analysis"]["learning_gaps"] = [
    _gap_from_insight_text(text, document["learning_analysis"])
    for text in validated_insights.learning_gaps
]
document["recommendations"] = [
    recommendation.model_dump(mode="json") for recommendation in validated_insights.recommendations
]
target = validated_insights.generation_target
document["next_question_strategy"]["recommended_bloom_levels"] = _bloom_levels_with_target(
    target.recommended_bloom_level, document["next_question_strategy"]
)
```

Where `_gap_from_insight_text` builds a `LearningGap`-shaped dict with the text as the `subtopic` and a `priority` from the overall status, and `_bloom_levels_with_target` prepends the Qwen-recommended level to the deterministic list, de-duplicating.

4. Keep `number_of_questions=5` forced in backend code and keep `model_metadata` assembly unchanged.

- [ ] **Step 4: Update `test_llm_student_analysis.py`**

`StudentInsightResponse` still returns a single `recommended_bloom_level`; its contract is unchanged. Update only assertions that referenced the old insight-prompt schema string if any; otherwise leave the file as-is.

- [ ] **Step 5: Run pipeline and LLM student-analysis tests**

Run:
```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_pipeline.py tests/test_llm_student_analysis.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/student_pipeline.py app/services/llm_service.py tests/test_student_pipeline.py tests/test_llm_student_analysis.py
git commit -m "feat: assemble reshaped student analytics documents"
```

---

### Task 4: Repository identity by `exam_id` and submission lookup

**Files:**
- Modify: `app/db/repository.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces:
  - `upsert_student_analytics(db, document: dict) -> None` keyed on `student_id + course.code + exam_id`.
  - `find_student_analytics(db, student_id, course_code=None, session_name=None) -> dict | None`.
  - `find_graded_submission(db, student_id, course_code, session_name) -> dict | None`.
  - `find_graded_submissions_for_exam(db, course_code, session_name) -> list[dict]`.
  - `find_course_for_submission`, `find_rubric_for_submission` (unchanged).

- [ ] **Step 1: Write failing repository tests**

Replace the `student_analytics` persistence tests in `tests/test_repository.py`:

```python
async def test_upsert_student_analytics_is_idempotent_by_exam_id(test_db):
    doc = valid_document(student_id="IT22145976", course_code="IT2040", session_name="Final Examination 2021")
    await upsert_student_analytics(test_db, doc)
    doc["overall_performance"]["score"] = 70.0
    doc["overall_performance"]["percentage"] = 70.0
    await upsert_student_analytics(test_db, doc)
    saved = await test_db["student_analytics"].find({"student_id": "IT22145976"}).to_list(length=None)
    assert len(saved) == 1
    assert saved[0]["overall_performance"]["score"] == 70.0


async def test_find_student_analytics_matches_course_and_session(test_db):
    await upsert_student_analytics(
        test_db, valid_document(student_id="IT22145976", course_code="IT2040", session_name="Final Examination 2021")
    )
    found = await find_student_analytics(test_db, "IT22145976", "IT2040", "Final Examination 2021")
    assert found["exam_id"] == "IT2040@Final Examination 2021"
```

- [ ] **Step 2: Run repository tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`
Expected: FAIL because the upsert identity uses `assessment.session_name` and the new documents have no `assessment` field.

- [ ] **Step 3: Implement the repository changes**

In `app/db/repository.py`:

1. Update the `student_analytics` index:

```python
"student_analytics": [("student_id", 1), ("course.code", 1), ("exam_id", 1)],
```

2. Update the upsert identity:

```python
async def upsert_student_analytics(db, document: dict) -> None:
    identity = {
        "student_id": document["student_id"],
        "course.code": document["course"]["code"],
        "exam_id": document["exam_id"],
    }
    await db["student_analytics"].replace_one(identity, deepcopy(document), upsert=True)
```

3. Update `find_student_analytics` to build an `exam_id` filter from `course_code` + `session_name` when both are supplied:

```python
async def find_student_analytics(db, student_id, course_code=None, session_name=None) -> dict | None:
    filters: dict[str, object] = {"student_id": student_id}
    if course_code is not None and session_name is not None:
        filters["course.code"] = course_code
        filters["exam_id"] = f"{course_code}@{session_name}"
    elif course_code is not None:
        filters["course.code"] = course_code
    document = await db["student_analytics"].find_one(filters, sort=[("_id", -1)])
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result
```

4. Add the two submission helpers:

```python
async def find_graded_submission(db, student_id, course_code, session_name) -> dict | None:
    return await db["submissions"].find_one(
        {
            "student_id": student_id,
            "subject_code": course_code,
            "session_name": session_name,
            "status": "graded",
        }
    )


async def find_graded_submissions_for_exam(db, course_code, session_name) -> list[dict]:
    cursor = db["submissions"].find(
        {"subject_code": course_code, "session_name": session_name, "status": "graded"}
    )
    return await cursor.to_list(length=None)
```

- [ ] **Step 4: Run repository tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/db/repository.py tests/test_repository.py
git commit -m "feat: key student analytics by exam_id"
```

---

### Task 5: On-demand generation service

**Files:**
- Replace: `app/services/student_dashboard.py`
- Modify: `app/services/student_pipeline.py`
- Replace: `tests/test_student_dashboard_service.py`

**Interfaces:**
- Produces:
  - `class StudentNotFound(Exception)`.
  - `async ensure_student_analytics(db, student_id, course_code, session_name) -> StudentAnalyticsDocument`.
  - `async build_student_analytics(db, submission) -> StudentAnalyticsDocument` (single-student builder reused by the batch pipeline).

- [ ] **Step 1: Extract the single-student builder in the pipeline**

In `app/services/student_pipeline.py`, refactor the per-submission body of `materialize_student_analytics` into a reusable async function:

```python
async def build_student_analytics(db, submission: dict) -> StudentAnalyticsDocument:
    course = await find_course_for_submission(db, submission)
    rubric = await find_rubric_for_submission(db, submission)
    normalized = normalize_student_submission(course or {}, rubric or {}, submission)
    semantics = await _classify_questions(normalized, {})
    numeric = build_numeric_analysis(normalized, semantics)
    try:
        insights = await generate_student_insights(normalized.student_id, numeric.evidence())
    except OllamaUnavailable:
        insights = {"status": "degraded", "reason": "ollama_unavailable"}
    document = _assemble_document(normalized, numeric, insights, submission)
    return StudentAnalyticsDocument.model_validate(document)
```

Update `materialize_student_analytics` to call this builder inside its existing try/except loop while still sharing the batch-level `classification_cache` (pass the cache through a small internal variant that accepts a prebuilt cache). The batch must keep its per-student failure isolation and progress reporting.

- [ ] **Step 2: Write failing on-demand service tests**

Replace `tests/test_student_dashboard_service.py`:

```python
import pytest
from unittest.mock import AsyncMock

from app.schemas.student import StudentAnalyticsDocument
from app.services import student_dashboard


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "overall_performance": {"score": 65.0, "maximum": 100.0, "percentage": 65.0, "status": "Needs Improvement"},
        "question_performance": [],
        "topic_performance": [{"topic": "JDBC", "questions_attempted": 1, "score": 19.0, "max_score": 25.0, "percentage": 76.0, "status": "Strong"}],
        "bloom_performance": [],
        "learning_analysis": {"overall_performance": "Needs Improvement", "strong_topics": [], "developing_topics": [], "weak_topics": [], "critical_topics": [], "learning_gaps": []},
        "recommendations": [],
        "next_question_strategy": {"recommended_topics": [], "recommended_bloom_levels": [], "recommended_difficulty": "Medium", "number_of_questions": 5},
        "model_metadata": {"bloom_model": "qwen3:8b", "bloom_model_type": "base", "grading_source": "colab", "rag_context_used": True},
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


async def test_ensure_loads_cached_analysis_without_generating(monkeypatch):
    find = AsyncMock(return_value=valid_document())
    build = AsyncMock()
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)

    result = await student_dashboard.ensure_student_analytics(object(), "IT22145976", "IT2040", "Final Examination 2021")

    assert isinstance(result, StudentAnalyticsDocument)
    build.assert_not_awaited()
    find.assert_awaited_once()


async def test_ensure_generates_and_saves_when_missing(monkeypatch):
    find = AsyncMock(return_value=None)
    built = StudentAnalyticsDocument.model_validate(valid_document())
    build = AsyncMock(return_value=built)
    save = AsyncMock()
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)
    monkeypatch.setattr(student_dashboard, "upsert_student_analytics", save)

    result = await student_dashboard.ensure_student_analytics(object(), "IT22145976", "IT2040", "Final Examination 2021")

    build.assert_awaited_once()
    save.assert_awaited_once()
    assert result == built


async def test_ensure_raises_when_no_submission_exists(monkeypatch):
    find = AsyncMock(return_value=None)
    build = AsyncMock(side_effect=student_dashboard.StudentNotFound("no graded submission"))
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)

    with pytest.raises(student_dashboard.StudentNotFound, match="no graded submission"):
        await student_dashboard.ensure_student_analytics(object(), "IT22145976", "IT2040", "Final Examination 2021")
```

- [ ] **Step 3: Run the service tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_dashboard_service.py -q`
Expected: FAIL because `ensure_student_analytics` and `StudentNotFound` do not exist.

- [ ] **Step 4: Implement the service**

Replace `app/services/student_dashboard.py`:

```python
from app.db.repository import find_graded_submission, find_student_analytics, upsert_student_analytics
from app.schemas.student import StudentAnalyticsDocument
from app.services.student_pipeline import build_student_analytics


class StudentNotFound(Exception):
    pass


async def ensure_student_analytics(
    db,
    student_id: str,
    course_code: str,
    session_name: str,
) -> StudentAnalyticsDocument:
    cached = await find_student_analytics(db, student_id, course_code, session_name)
    if cached is not None:
        return StudentAnalyticsDocument.model_validate(cached)

    submission = await find_graded_submission(db, student_id, course_code, session_name)
    if submission is None:
        raise StudentNotFound("no graded submission found for student")

    document = await build_student_analytics(db, submission)
    await upsert_student_analytics(db, document.model_dump(mode="json"))
    return document
```

- [ ] **Step 5: Run the service tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_student_dashboard_service.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add app/services/student_dashboard.py app/services/student_pipeline.py tests/test_student_dashboard_service.py
git commit -m "feat: on-demand student analytics generation"
```

---

### Task 6: On-demand dashboard API and sample runner

**Files:**
- Modify: `app/api/dashboard.py`
- Modify: `run_sample.py`
- Replace: `tests/test_api_dashboard.py`
- Update: `tests/test_run_sample.py`

**Interfaces:**
- HTTP: `GET /api/students/{student_id}/dashboard?course_code=...&session_name=...` -> 200 with the (possibly newly generated) document; 404 when the student has no graded submission.

- [ ] **Step 1: Write failing API tests**

Replace `tests/test_api_dashboard.py` `TOP_LEVEL_KEYS` with the new set:

```python
TOP_LEVEL_KEYS = {
    "student_id", "exam_id", "course", "overall_performance",
    "question_performance", "topic_performance", "bloom_performance",
    "learning_analysis", "recommendations", "next_question_strategy",
    "model_metadata", "generated_at", "analysis_version",
}
```

Add a test that seeds a submission and verifies the endpoint generates on first access and returns the new shape; keep filter-forwarding and 404 tests, updating their expected shapes and the 404 detail message to `"no graded submission found for student"`.

- [ ] **Step 2: Run API tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_dashboard.py -q`
Expected: FAIL because the endpoint returns the old 404/`get_student_dashboard` contract.

- [ ] **Step 3: Update the dashboard route**

Replace `app/api/dashboard.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.schemas.student import StudentAnalyticsDocument
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}/dashboard", response_model=StudentAnalyticsDocument)
async def student_dashboard(
    student_id: str,
    course_code: str,
    session_name: str,
    db=Depends(get_db),
) -> StudentAnalyticsDocument:
    try:
        return await ensure_student_analytics(db, student_id, course_code, session_name)
    except StudentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

Note: `course_code` and `session_name` become required query parameters so the endpoint can resolve and generate on demand. Update the OpenAPI test to assert these two required params.

- [ ] **Step 4: Update the sample runner identity logic**

In `run_sample.py`, change the final `sample_analytics_filter` identity from `assessment.session_name` to `exam_id`:

```python
sample_analytics_filter = {
    "$or": [
        {
            "student_id": submission["student_id"],
            "course.code": submission.get("course_code") or submission["subject_code"],
            "exam_id": f"{submission.get('course_code') or submission['subject_code']}@{submission['session_name']}",
        }
        for submission in sample_submissions
    ]
}
```

- [ ] **Step 5: Update `tests/test_run_sample.py`**

Update `_clean_sample_documents` and `_CountCollection` identity filters to use `exam_id` instead of `assessment.session_name`, and update `valid_document`-style fixtures to the new shape wherever referenced.

- [ ] **Step 6: Run API and run-sample tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_dashboard.py tests/test_run_sample.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/api/dashboard.py run_sample.py tests/test_api_dashboard.py tests/test_run_sample.py
git commit -m "feat: on-demand student dashboard endpoint"
```

---

### Task 7: Phase 1 regression verification

**Files:**
- None unless a test exposes an inconsistency.

- [ ] **Step 1: Run static checks**

```powershell
git diff --check
.\.venv\Scripts\python.exe -m compileall -q app run_sample.py
```
Expected: exit 0.

- [ ] **Step 2: Run all Phase 1 tests**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py tests/test_student_document_analytics.py tests/test_llm_student_analysis.py tests/test_repository.py tests/test_student_pipeline.py tests/test_student_dashboard_service.py tests/test_api_dashboard.py tests/test_run_sample.py -q
```
Expected: PASS.

- [ ] **Step 3: Run the complete offline suite**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```
Expected: PASS. Any Phase-2 files still on disk are untouched at this point, so the old cohort tests still pass.

- [ ] **Step 4: Commit any corrections**

If corrections were needed: `git add app tests run_sample.py && git commit -m "test: verify phase 1 restructure"`. Otherwise do not create an empty commit.

---

## Phase 2 — Lecturer Exam Analytics + Student List

### Task 8: Exam analytics schema and deterministic math

**Files:**
- Create: `app/schemas/exam_analytics.py`
- Create: `app/analytics/exam_analytics.py`
- Create: `tests/test_exam_analytics.py`

**Interfaces:**
- Produces:
  - `ExamAnalyticsDocument` schema (fields match the spec `examAnalytics` example).
  - `compute_exam_analytics_stats(normalized_students: list[dict], pass_threshold: float) -> dict` producing `statistics`, `topic_performance`, `bloom_performance`, `question_performance`, `attention_areas`, `insights`.

- [ ] **Step 1: Write the schema contract tests**

Create `tests/test_exam_analytics.py`:

```python
from app.schemas.exam_analytics import ExamAnalyticsDocument


def exam_document() -> dict:
    return {
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "exam": {"session_name": "Final Examination 2021", "total_marks": 100.0, "question_count": 11},
        "statistics": {"total_students": 5, "attempted_students": 5, "average_score": 67.4,
                       "average_percentage": 67.4, "pass_rate": 80.0, "highest_score": 94.0, "lowest_score": 31.0},
        "topic_performance": [{"topic": "JDBC", "average_percentage": 76.0, "status": "Strong"}],
        "bloom_performance": [{"level": "Remember", "average_percentage": 83.0}],
        "question_performance": [{"question_id": "Q01", "question_no": "01", "topic": "DBMS Design",
                                  "bloom_level": "Understand", "average_percentage": 75.0}],
        "attention_areas": [{"type": "topic", "name": "SQL", "average_percentage": 33.0, "priority": "Critical"}],
        "insights": ["SQL is the weakest topic across the class."],
        "generated_at": "2026-08-12T00:00:00Z",
        "analytics_version": "1.0",
    }


def test_exam_analytics_serializes_exact_top_level_contract():
    document = ExamAnalyticsDocument(**exam_document())
    assert set(document.model_dump(mode="json")) == {
        "exam_id", "course", "exam", "statistics", "topic_performance",
        "bloom_performance", "question_performance", "attention_areas",
        "insights", "generated_at", "analytics_version",
    }
```

- [ ] **Step 2: Run the schema test and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_exam_analytics.py -q`
Expected: FAIL because `app.schemas.exam_analytics` does not exist.

- [ ] **Step 3: Implement the schema**

Create `app/schemas/exam_analytics.py` mirroring the field structure shown in Step 1 (Pydantic `BaseModel`, constrained floats `ge=0 le=100`, `Field(min_length=1)` on strings, `default_factory=list` on lists).

- [ ] **Step 4: Run the schema test**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_exam_analytics.py -q`
Expected: PASS.

- [ ] **Step 5: Write failing class-statistics math tests**

Append to `tests/test_exam_analytics.py`:

```python
from app.analytics.exam_analytics import compute_exam_analytics_stats


def _student_docs():
    return [
        {
            "overall": {"score": 80.0, "maximum": 100.0, "percentage": 80.0},
            "topic_performance": [{"topic": "JDBC", "score": 20.0, "max_score": 25.0}],
            "bloom_performance": [{"level": "Remember", "average_score": 80.0}],
            "question_performance": [{"question_no": "01", "topic": "JDBC", "bloom_level": "Remember", "score": 8.0, "max_score": 10.0}],
        },
        {
            "overall": {"score": 40.0, "maximum": 100.0, "percentage": 40.0},
            "topic_performance": [{"topic": "JDBC", "score": 5.0, "max_score": 25.0}],
            "bloom_performance": [{"level": "Remember", "average_score": 40.0}],
            "question_performance": [{"question_no": "01", "topic": "JDBC", "bloom_level": "Remember", "score": 4.0, "max_score": 10.0}],
        },
    ]


def test_class_statistics_are_computed_from_all_students():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert stats["statistics"]["total_students"] == 2
    assert stats["statistics"]["average_percentage"] == 60.0
    assert stats["statistics"]["pass_rate"] == 50.0
    assert stats["statistics"]["highest_score"] == 80.0
    assert stats["statistics"]["lowest_score"] == 40.0
    assert stats["topic_performance"][0]["average_percentage"] == 50.0  # 25/50
    assert stats["topic_performance"][0]["status"] == "Needs Improvement"


def test_attention_areas_derive_from_bottom_topics():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert stats["attention_areas"][0]["name"] == "JDBC"
    assert stats["attention_areas"][0]["priority"] == "Critical"


def test_insights_are_deterministic():
    stats = compute_exam_analytics_stats(_student_docs(), pass_threshold=0.5)
    assert any("weakest topic" in insight for insight in stats["insights"])
```

- [ ] **Step 6: Run the math tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_exam_analytics.py -q`
Expected: FAIL because `compute_exam_analytics_stats` does not exist.

- [ ] **Step 7: Implement the deterministic math**

Create `app/analytics/exam_analytics.py`. The function aggregates `normalized_students` (each produced by reusing `build_numeric_analysis` per student, without insights):

```python
def compute_exam_analytics_stats(normalized_students: list[dict], pass_threshold: float) -> dict:
    totals = [student["overall"] for student in normalized_students]
    percentages = [total["percentage"] for total in totals]
    average_percentage = sum(percentages) / len(percentages) if percentages else 0.0
    pass_rate = (
        sum(1 for p in percentages if p >= pass_threshold * 100.0) / len(percentages) * 100.0
        if percentages else 0.0
    )
    statistics = {
        "total_students": len(totals),
        "attempted_students": len([t for t in totals if t["maximum"] > 0]),
        "average_score": round(sum(t["score"] for t in totals) / len(totals), 2) if totals else 0.0,
        "average_percentage": round(average_percentage, 2),
        "pass_rate": round(pass_rate, 2),
        "highest_score": max(t["score"] for t in totals) if totals else 0.0,
        "lowest_score": min(t["score"] for t in totals) if totals else 0.0,
    }

    # Marks-weighted topic aggregation across all students
    topic_score: dict[str, float] = {}
    topic_max: dict[str, float] = {}
    for student in normalized_students:
        for topic in student["topic_performance"]:
            topic_score[topic["topic"]] = topic_score.get(topic["topic"], 0.0) + topic["score"]
            topic_max[topic["topic"]] = topic_max.get(topic["topic"], 0.0) + topic["max_score"]
    topic_performance = [
        {
            "topic": name,
            "average_percentage": round(score / topic_max[name] * 100.0, 2),
            "status": performance_status(score / topic_max[name] * 100.0),
        }
        for name, score in sorted(
            topic_score.items(), key=lambda item: item[1] / topic_max[item[0]]
        )
    ]

    bloom_score: dict[str, float] = {}
    bloom_count: dict[str, int] = {}
    for student in normalized_students:
        for bloom in student["bloom_performance"]:
            bloom_score[bloom["level"]] = bloom_score.get(bloom["level"], 0.0) + bloom["average_score"]
            bloom_count[bloom["level"]] = bloom_count.get(bloom["level"], 0) + 1
    bloom_performance = [
        {"level": level, "average_percentage": round(total / bloom_count[level], 2)}
        for level, total in sorted(bloom_score.items())
    ]

    question_score: dict[str, dict] = {}
    for student in normalized_students:
        for question in student["question_performance"]:
            entry = question_score.setdefault(
                question["question_no"],
                {"question_id": f"Q{question['question_no']}", "question_no": question["question_no"],
                 "topic": question["topic"], "bloom_level": question["bloom_level"],
                 "score": 0.0, "max_score": 0.0},
            )
            entry["score"] += question["score"]
            entry["max_score"] += question["max_score"]
    question_performance = [
        {
            "question_id": entry["question_id"],
            "question_no": entry["question_no"],
            "topic": entry["topic"],
            "bloom_level": entry["bloom_level"],
            "average_percentage": round(entry["score"] / entry["max_score"] * 100.0, 2),
        }
        for entry in sorted(question_score.values(), key=lambda item: item["question_no"])
    ]

    attention_areas = [
        {"type": "topic", "name": topic["topic"], "average_percentage": topic["average_percentage"],
         "priority": _ATTENTION_PRIORITY[topic["status"]]}
        for topic in topic_performance
        if topic["status"] in _ATTENTION_PRIORITY
    ]
    insights = build_insights(statistics, topic_performance, question_performance)
    return {
        "statistics": statistics,
        "topic_performance": topic_performance,
        "bloom_performance": bloom_performance,
        "question_performance": question_performance,
        "attention_areas": attention_areas,
        "insights": insights,
    }
```

Where `_ATTENTION_PRIORITY = {"Critical": "Critical", "Needs Improvement": "High", "Developing": "Medium"}`, `performance_status` is imported from `app.analytics.student_document`, and `build_insights` returns deterministic template strings (weakest topic, strongest topic, lowest-performing question).

- [ ] **Step 8: Run the math tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_exam_analytics.py -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add app/schemas/exam_analytics.py app/analytics/exam_analytics.py tests/test_exam_analytics.py
git commit -m "feat: exam analytics schema and class math"
```

---

### Task 9: `compute_exam_analytics` generator and repository

**Files:**
- Create: `app/services/exam_analytics.py`
- Modify: `app/db/repository.py`
- Create: `tests/test_exam_analytics_service.py`

**Interfaces:**
- Produces:
  - `async compute_exam_analytics(db, course_code, session_name) -> dict` — reads graded submissions, builds per-student numeric analysis (reusing the pipeline classifier), computes stats, and upserts into `analytics_snapshots`.
  - `upsert_exam_analytics(db, document: dict) -> None` keyed on `exam_id + analytics_version`.
  - `find_exam_analytics(db, course_code, session_name) -> dict | None`.

- [ ] **Step 1: Write failing repository tests**

Append to `tests/test_repository.py`:

```python
async def test_upsert_and_find_exam_analytics_round_trip(test_db):
    from app.schemas.exam_analytics import ExamAnalyticsDocument

    doc = ExamAnalyticsDocument.model_validate(exam_document()).model_dump(mode="json")
    await upsert_exam_analytics(test_db, doc)
    found = await find_exam_analytics(test_db, "IT2040", "Final Examination 2021")
    assert found["exam_id"] == "IT2040@Final Examination 2021"
```

(Use the `exam_document()` helper defined in `tests/test_exam_analytics.py` from Task 8; import it at the top of `tests/test_repository.py`.)

- [ ] **Step 2: Run repository tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`
Expected: FAIL because `upsert_exam_analytics` and `find_exam_analytics` do not exist.

- [ ] **Step 3: Implement repository operations**

In `app/db/repository.py`:

```python
async def upsert_exam_analytics(db, document: dict) -> None:
    identity = {"exam_id": document["exam_id"], "analytics_version": document["analytics_version"]}
    await db["analytics_snapshots"].replace_one(identity, deepcopy(document), upsert=True)


async def find_exam_analytics(db, course_code, session_name) -> dict | None:
    document = await db["analytics_snapshots"].find_one(
        {"exam_id": f"{course_code}@{session_name}"}, sort=[("_id", -1)]
    )
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result
```

- [ ] **Step 4: Write failing service tests**

Create `tests/test_exam_analytics_service.py`:

```python
from app.services import exam_analytics as exam_service


async def test_compute_exam_analytics_persists_and_returns_document(test_db, monkeypatch):
    from run_sample import load_raw_sample_documents, seed_raw_samples
    from tests.test_run_sample import fake_semantics
    from app.services import student_pipeline

    monkeypatch.setattr(student_pipeline, "classify_question_semantics", fake_semantics)
    monkeypatch.setattr(student_pipeline, "generate_student_insights", lambda *a, **k: {"status": "degraded", "reason": "offline_test"})
    await seed_raw_samples(test_db)

    result = await exam_service.compute_exam_analytics(test_db, "IT2040", "Final Examination 2021")

    assert result["exam_id"] == "IT2040@Final Examination 2021"
    assert result["statistics"]["total_students"] == 5
    saved = await test_db["analytics_snapshots"].find_one({"exam_id": "IT2040@Final Examination 2021"})
    assert saved is not None
```

- [ ] **Step 5: Implement the generator**

Create `app/services/exam_analytics.py`:

```python
from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.db.repository import (
    find_course_for_submission,
    find_graded_submissions_for_exam,
    find_rubric_for_submission,
    upsert_exam_analytics,
)
from app.ingestion.student_data import normalize_student_submission
from app.services.student_pipeline import _classify_questions
from app.analytics.student_document import build_numeric_analysis


async def compute_exam_analytics(db, course_code: str, session_name: str) -> dict:
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name)
    if not submissions:
        raise ExamNotFound(f"no graded submissions for {course_code} {session_name}")

    course = None
    rubric = None
    students: list[dict] = []
    for submission in submissions:
        course = await find_course_for_submission(db, submission)
        rubric = await find_rubric_for_submission(db, submission)
        normalized = normalize_student_submission(course or {}, rubric or {}, submission)
        semantics = await _classify_questions(normalized, {})
        numeric = build_numeric_analysis(normalized, semantics)
        students.append(
            {
                "overall": numeric.overall_performance.model_dump(),
                "topic_performance": [topic.model_dump() for topic in numeric.topic_performance],
                "bloom_performance": [bloom.model_dump() for bloom in numeric.bloom_performance],
                "question_performance": [q.model_dump() for q in numeric.question_performance],
            }
        )

    stats = compute_exam_analytics_stats(students, pass_threshold=0.5)
    total_marks = sum(float(q["max_marks"]) for q in (rubric or {}).get("questions", []))
    question_count = len((rubric or {}).get("questions", []))
    course_name = str(course.get("name") or course.get("course_name") or "").strip()
    if not course_name:
        course_name = "Database Management Systems" if course_code == "IT2040" else course_code
    document = {
        "exam_id": f"{course_code}@{session_name}",
        "course": {"code": course_code, "name": course_name},
        "exam": {"session_name": session_name, "total_marks": total_marks, "question_count": question_count},
        **stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_version": "1.0",
    }
    await upsert_exam_analytics(db, document)
    return document
```

Note: `exam.total_marks` and `question_count` come from the rubric (`sum of rubric question max marks` and the number of rubric questions). `_course_name` resolves `course.get("name") or course.get("course_name")` with the IT2040 fallback. `ExamNotFound` is defined in this module.

- [ ] **Step 6: Run service and repository tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_exam_analytics_service.py tests/test_repository.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add app/services/exam_analytics.py app/db/repository.py tests/test_exam_analytics_service.py tests/test_repository.py
git commit -m "feat: compute and persist exam analytics"
```

---

### Task 10: Lecturer API router

**Files:**
- Create: `app/api/lecturer.py`
- Modify: `app/main.py`
- Create: `tests/test_api_lecturer.py`

**Interfaces:**
- HTTP:
  - `GET /api/lecturers/exams/{course_code}/{session_name}/analytics` -> 200 with `ExamAnalyticsDocument`; 404 when no submissions.
  - `GET /api/lecturers/exams/{course_code}/{session_name}/students` -> 200 with a list of student rows; 404 when no submissions.

- [ ] **Step 1: Write failing lecturer API tests**

Create `tests/test_api_lecturer.py`:

```python
import httpx

from app.api import deps
from app.main import app
from app.db.repository import upsert_exam_analytics, upsert_student_analytics


async def test_lecturer_analytics_endpoint_returns_document(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        from tests.test_exam_analytics import exam_document

        await upsert_exam_analytics(test_db, exam_document())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/lecturers/exams/IT2040/Final%20Examination%202021/analytics"
            )
        assert response.status_code == 200
        assert response.json()["exam_id"] == "IT2040@Final Examination 2021"
    finally:
        app.dependency_overrides.clear()
        await test_db["analytics_snapshots"].delete_many({})


async def test_lecturer_students_endpoint_reports_analysis_status(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        from run_sample import load_raw_sample_documents

        _, _, submissions = load_raw_sample_documents()
        for submission in submissions:
            await test_db["submissions"].replace_one(
                {"student_id": submission["student_id"], "subject_code": "IT2040", "session_name": "Final Examination 2021"},
                submission, upsert=True,
            )
        await upsert_student_analytics(test_db, valid_student_document())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/lecturers/exams/IT2040/Final%20Examination%202021/students"
            )
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 5
        statuses = {row["student_id"]: row["analysis_status"] for row in rows}
        assert statuses["IT21001234"] == "generated"
```

- [ ] **Step 2: Run lecturer tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_lecturer.py -q`
Expected: FAIL because `app/api/lecturer.py` does not exist.

- [ ] **Step 3: Implement the router**

Create `app/api/lecturer.py`:

```python
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.db.repository import find_exam_analytics, find_graded_submissions_for_exam, find_student_analytics
from app.schemas.exam_analytics import ExamAnalyticsDocument
from app.services.exam_analytics import ExamNotFound, compute_exam_analytics

router = APIRouter(prefix="/lecturers", tags=["lecturers"])


@router.get("/exams/{course_code}/{session_name}/analytics", response_model=ExamAnalyticsDocument)
async def lecturer_exam_analytics(course_code: str, session_name: str, db=Depends(get_db)):
    document = await find_exam_analytics(db, course_code, session_name)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExamAnalyticsDocument.model_validate(document)


@router.get("/exams/{course_code}/{session_name}/students")
async def lecturer_student_list(course_code: str, session_name: str, db=Depends(get_db)):
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name)
    if not submissions:
        raise HTTPException(status_code=404, detail="no graded submissions for exam")
    rows = []
    for submission in submissions:
        student_id = submission["student_id"]
        evaluation = submission.get("evaluation") or {}
        obtained = float(evaluation.get("total_score") or submission.get("max_marks_paper_total") or 0)
        maximum = float(evaluation.get("max_score") or submission.get("max_marks_paper_total") or 0)
        percentage = (obtained / maximum * 100.0) if maximum else 0.0
        cached = await find_student_analytics(db, student_id, course_code, session_name)
        rows.append(
            {
                "student_id": student_id,
                "score": {"obtained": obtained, "maximum": maximum, "percentage": round(percentage, 2)},
                "status": performance_status(percentage),
                "analysis_status": "generated" if cached else "pending",
                "submitted_at": submission.get("processed_at"),
            }
        )
    return rows
```

`ExamNotFound` is defined in `app/services/exam_analytics.py`:

```python
class ExamNotFound(Exception):
    pass
```

Register the router in `app/main.py`:

```python
from app.api.dashboard import router as dashboard_router
from app.api.lecturer import router as lecturer_router

app.include_router(dashboard_router, prefix="/api")
app.include_router(lecturer_router, prefix="/api")
```

- [ ] **Step 4: Run lecturer tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_lecturer.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/api/lecturer.py app/main.py tests/test_api_lecturer.py
git commit -m "feat: lecturer exam analytics and student list endpoints"
```

---

### Task 11: Wire exam analytics into the sample runner

**Files:**
- Modify: `run_sample.py`
- Modify: `tests/test_run_sample.py`

**Interfaces:**
- CLI stays `python run_sample.py [database_name]`; after materializing student analytics it also computes exam analytics.

- [ ] **Step 1: Write failing sample-runner test**

Append to `tests/test_run_sample.py`:

```python
async def test_main_computes_exam_analytics_after_materialization(monkeypatch, capsys, test_db):
    events = []

    async def compute_exam(candidate_db, course_code, session_name):
        assert candidate_db is test_db
        events.append("exam_analytics")
        return {"exam_id": "IT2040@Final Examination 2021"}

    async def _healthy():
        return True, "ok"

    async def _runner_main(*args):
        events.append("runner_main")
        return 0

    monkeypatch.setattr(run_sample, "check_llm_health", _healthy)
    monkeypatch.setattr(run_sample, "compute_exam_analytics", compute_exam, raising=False)
    # Patch the heavy helpers so the runner reaches the new call without a live LLM/Mongo.
    monkeypatch.setattr(run_sample, "create_indexes", lambda db: events.append("indexes"))
    monkeypatch.setattr(run_sample, "seed_raw_samples", lambda db: {"courses": 1, "rubrics": 1, "submissions": 5})
    monkeypatch.setattr(run_sample, "materialize_student_analytics", _runner_main, raising=False)
    monkeypatch.setattr(run_sample, "AsyncIOMotorClient", lambda _uri: _RunnerClient(test_db))

    exit_code = await run_sample.main("dbms_analytics_test")

    assert exit_code == 0
    assert "exam_analytics" in events
```

- [ ] **Step 2: Run the sample tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_sample.py -q`
Expected: FAIL because `run_sample.main` does not call `compute_exam_analytics`.

- [ ] **Step 3: Update the runner**

In `run_sample.py`, after the `materialize_student_analytics` block, compute exam analytics for the sample course and session and print a line like `exam_analytics count=1`:

```python
from app.services.exam_analytics import compute_exam_analytics

sample_course_code = (courses[0].get("code") or courses[0].get("subject_code") or "IT2040")
sample_session = rubrics[0]["session_name"]
await compute_exam_analytics(db, sample_course_code, sample_session)
```

- [ ] **Step 4: Run the sample tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_run_sample.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add run_sample.py tests/test_run_sample.py
git commit -m "feat: compute exam analytics in sample run"
```

---

### Task 12: Remove the old cohort pipeline

**Files:**
- Remove: `app/services/analytics.py`, `app/analytics/mastery.py`, `app/analytics/evidence.py`, `app/analytics/coverage.py`, `app/analytics/recommender.py`, `app/analytics/student.py`, `app/ingestion/transformer.py`, `app/schemas/derived.py`
- Modify: `app/ingestion/__init__.py` (stop exporting `ingest`)
- Remove: `tests/test_analytics_service.py`, `tests/test_mastery.py`, `tests/test_evidence.py`, `tests/test_coverage.py`, `tests/test_recommender.py`, `tests/test_schemas_derived.py`, `tests/test_ingestion.py`

- [ ] **Step 1: Remove the production files**

```powershell
Remove-Item app/services/analytics.py, app/analytics/mastery.py, app/analytics/evidence.py, app/analytics/coverage.py, app/analytics/recommender.py, app/analytics/student.py, app/ingestion/transformer.py, app/schemas/derived.py
```

- [ ] **Step 2: Update `app/ingestion/__init__.py`**

Remove the `from app.ingestion.transformer import ingest` line so the package no longer references the deleted module.

- [ ] **Step 3: Remove the obsolete tests**

```powershell
Remove-Item tests/test_analytics_service.py, tests/test_mastery.py, tests/test_evidence.py, tests/test_coverage.py, tests/test_recommender.py, tests/test_schemas_derived.py, tests/test_ingestion.py
```

- [ ] **Step 4: Run static checks**

```powershell
git diff --check
.\.venv\Scripts\python.exe -m compileall -q app run_sample.py
```
Expected: exit 0.

- [ ] **Step 5: Run the complete offline suite**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```
Expected: PASS. If a remaining test imports a removed module, remove or update that test within scope and rerun until green.

- [ ] **Step 6: Commit**

```powershell
git add -A
git commit -m "refactor: remove replaced cohort pipeline"
```

---

### Task 13: Phase 2 regression verification

**Files:**
- None unless a test exposes an inconsistency.

- [ ] **Step 1: Run the complete offline suite**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```
Expected: PASS.

- [ ] **Step 2: Run the real sample runner against local MongoDB**

```powershell
.\.venv\Scripts\python.exe run_sample.py dbms_analytics_test
```
Expected: five saved student IDs, zero failures, `student_analytics count=5`, and `exam_analytics count=1`.

- [ ] **Step 3: Inspect a lecturer analytics document**

```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from motor.motor_asyncio import AsyncIOMotorClient; from app.config import settings; from app.db.repository import find_exam_analytics; async def main(): client=AsyncIOMotorClient(settings.mongodb_uri); print(await find_exam_analytics(client['dbms_analytics_test'], 'IT2040', 'Final Examination 2021')); client.close(); asyncio.run(main())"
```
Expected: the spec-shaped `examAnalytics` document.

- [ ] **Step 4: Commit any corrections**

If needed: `git add app tests run_sample.py && git commit -m "test: verify phase 2 restructure"`. Otherwise do not create an empty commit.

---

## Phase 3 — Personalized Question Generation

### Task 14: `generatedQuestions` schema and repository

**Files:**
- Create: `app/schemas/generated_questions.py`
- Modify: `app/db/repository.py`
- Extend: `tests/test_repository.py`

**Interfaces:**
- Produces:
  - `GeneratedQuestionsDocument` schema (fields per the spec Level-3 example).
  - `upsert_generated_questions(db, document: dict) -> None` keyed on `student_id + exam_id + generation_version`.
  - `find_generated_questions(db, student_id, exam_id) -> dict | None`.

- [ ] **Step 1: Write failing repository tests**

Append to `tests/test_repository.py`:

```python
async def test_generated_questions_round_trip(test_db):
    document = {
        "student_id": "IT22145976",
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "request": {"recommended_topics": ["SQL"], "recommended_bloom_levels": ["Understand"], "recommended_difficulty": "Medium", "number_of_questions": 5},
        "questions": [{"prompt": "Write an authentication query.", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": ["Use CREATE LOGIN"]}],
        "generated_at": "2026-08-12T00:00:00Z",
        "generation_version": "1.0",
    }
    await upsert_generated_questions(test_db, document)
    found = await find_generated_questions(test_db, "IT22145976", "IT2040@Final Examination 2021")
    assert found["student_id"] == "IT22145976"
    assert found["questions"][0]["prompt"].startswith("Write")
```

- [ ] **Step 2: Run repository tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`
Expected: FAIL because the functions do not exist.

- [ ] **Step 3: Implement the schema and repository**

Create `app/schemas/generated_questions.py` with Pydantic models `GeneratedQuestion`, `QuestionGenerationRequest`, and `GeneratedQuestionsDocument` matching the Step 1 shape. Add `"generatedQuestions"` to `COLLECTIONS` and implement:

```python
async def upsert_generated_questions(db, document: dict) -> None:
    identity = {
        "student_id": document["student_id"],
        "exam_id": document["exam_id"],
        "generation_version": document["generation_version"],
    }
    await db["generatedQuestions"].replace_one(identity, deepcopy(document), upsert=True)


async def find_generated_questions(db, student_id, exam_id) -> dict | None:
    document = await db["generatedQuestions"].find_one(
        {"student_id": student_id, "exam_id": exam_id}, sort=[("_id", -1)]
    )
    if document is None:
        return None
    result = deepcopy(document)
    result.pop("_id", None)
    return result
```

- [ ] **Step 4: Run repository tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/schemas/generated_questions.py app/db/repository.py tests/test_repository.py
git commit -m "feat: generated questions storage"
```

---

### Task 15: Practice-question generation service

**Files:**
- Create: `app/llm/roles/generate_practice.py`
- Create: `app/services/practice_questions.py`
- Modify: `app/services/llm_service.py`
- Create: `tests/test_llm_practice_questions.py`
- Create: `tests/test_practice_questions.py`

**Interfaces:**
- Produces:
  - `PracticeQuestions` Pydantic role model (`{requested_count, questions: [{prompt, bloom_level, topic, difficulty, hints}]}`).
  - `async generate_practice_questions(db, student_id, course_code, session_name, strategy: dict) -> dict` — calls Qwen, validates, caches, returns `{"status": "ok", "document": {...}}` or `{"status": "degraded", "reason": ...}`.

- [ ] **Step 1: Write failing LLM role tests**

Create `tests/test_llm_practice_questions.py`:

```python
import pytest
from pydantic import ValidationError

from app.llm.roles.generate_practice import PracticeQuestions


def test_practice_questions_accepts_valid_batch():
    questions = PracticeQuestions(
        requested_count=5,
        questions=[
            {"prompt": "Explain authentication.", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": ["CREATE LOGIN"]}
        ],
    )
    assert questions.requested_count == 5


def test_practice_questions_rejects_unknown_difficulty():
    with pytest.raises(ValidationError):
        PracticeQuestions(
            requested_count=1,
            questions=[{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Insane", "hints": []}],
        )
```

- [ ] **Step 2: Run the LLM role tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_practice_questions.py -q`
Expected: FAIL because `app.llm.roles.generate_practice` does not exist.

- [ ] **Step 3: Implement the role model and service call**

Create `app/llm/roles/generate_practice.py` with `PracticeQuestions` (use `BloomLevel` and `QuestionDifficulty` literals from `app.schemas.student`). Add to `app/services/llm_service.py`:

```python
async def generate_practice_questions(target: dict) -> dict:
    prompt = (
        "Generate practice DBMS questions for a student using only the supplied targeting. "
        "The target is authoritative; do not perform any numeric calculations.\n"
        "Respond ONLY with JSON matching this schema:\n"
        '{"requested_count": int, "questions": [{"prompt": str, "bloom_level": '
        '"Remember|Understand|Apply|Analyze|Evaluate|Create", "topic": str, '
        '"difficulty": "Easy|Medium|Hard", "hints": [str]}]}\n'
        f"TARGET: {json.dumps(target, ensure_ascii=False)}"
    )
    try:
        parsed, _raw, _review = await validate_with_retry(
            PracticeQuestions, prompt, temperature=settings.ollama_generate_temperature
        )
    except OllamaUnavailable:
        return {"status": "degraded", "reason": "ollama_unavailable"}
    if parsed is None:
        return {"status": "degraded", "reason": "schema_failure"}
    return {"status": "ok", "questions": [q.model_dump() for q in parsed.questions]}
```

- [ ] **Step 4: Write failing service tests**

Create `tests/test_practice_questions.py`:

```python
from unittest.mock import AsyncMock

from app.services import practice_questions


async def test_generate_practice_questions_caches_document(monkeypatch):
    from app.schemas.student import NextQuestionStrategy

    strategy = NextQuestionStrategy(recommended_topics=["SQL"], recommended_bloom_levels=["Understand"], recommended_difficulty="Medium", number_of_questions=5)
    gen = AsyncMock(return_value={"status": "ok", "questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}]})
    save = AsyncMock()
    monkeypatch.setattr(practice_questions, "generate_practice_questions_call", gen)
    monkeypatch.setattr(practice_questions, "upsert_generated_questions", save)

    result = await practice_questions.generate_practice_questions(object(), "IT22145976", "IT2040", "Final Examination 2021", strategy)

    assert result["status"] == "ok"
    save.assert_awaited_once()


async def test_generate_practice_questions_degrades_when_qwen_down(monkeypatch):
    from app.schemas.student import NextQuestionStrategy

    strategy = NextQuestionStrategy(recommended_topics=["SQL"], recommended_bloom_levels=["Understand"], recommended_difficulty="Medium", number_of_questions=5)
    gen = AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"})
    monkeypatch.setattr(practice_questions, "generate_practice_questions_call", gen)

    result = await practice_questions.generate_practice_questions(object(), "IT22145976", "IT2040", "Final Examination 2021", strategy)

    assert result == {"status": "degraded", "reason": "ollama_unavailable"}
```

(Use the same `strategy` construction from the previous test; the `...` placeholder above is removed.)

- [ ] **Step 5: Run the service tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_practice_questions.py -q`
Expected: FAIL because `app.services.practice_questions` does not exist.

- [ ] **Step 6: Implement the service**

Create `app/services/practice_questions.py`:

```python
from app.db.repository import upsert_generated_questions
from app.schemas.student import NextQuestionStrategy
from app.services.llm_service import generate_practice_questions as generate_practice_questions_call


async def generate_practice_questions(db, student_id, course_code, session_name, strategy: NextQuestionStrategy) -> dict:
    target = strategy.model_dump()
    response = await generate_practice_questions_call(target)
    if response["status"] != "ok":
        return response
    document = {
        "student_id": student_id,
        "exam_id": f"{course_code}@{session_name}",
        "course": {"code": course_code, "name": course_name},
        "request": target,
        "questions": response["questions"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_version": "1.0",
    }
    await upsert_generated_questions(db, document)
    return {"status": "ok", "document": document}
```

(Resolve `course_name` from the course document via the repository; fall back to the code.)

- [ ] **Step 7: Run LLM and service tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_llm_practice_questions.py tests/test_practice_questions.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add app/llm/roles/generate_practice.py app/services/practice_questions.py app/services/llm_service.py tests/test_llm_practice_questions.py tests/test_practice_questions.py
git commit -m "feat: personalized practice question generation"
```

---

### Task 16: Practice-question API endpoints

**Files:**
- Modify: `app/api/dashboard.py`
- Create: `tests/test_api_practice_questions.py`

**Interfaces:**
- HTTP:
  - `POST /api/students/{student_id}/practice-questions?course_code=...&session_name=...` -> 200 with questions; 503 with target echoed when Qwen is unavailable.
  - `GET /api/students/{student_id}/practice-questions?course_code=...&session_name=...&fresh=false` -> 200 with cached batch; regenerates when `fresh=true` or no cache.

- [ ] **Step 1: Write failing practice API tests**

Create `tests/test_api_practice_questions.py`:

```python
import httpx

from app.api import deps
from app.main import app


async def test_practice_post_returns_generated_questions(test_db, monkeypatch):
    from app.schemas.student import StudentAnalyticsDocument

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        async def fake_ensure(db, student_id, course_code, session_name):
            return StudentAnalyticsDocument.model_validate(valid_document())

        async def fake_generate(db, student_id, course_code, session_name, strategy):
            return {"status": "ok", "document": {"questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}]}}

        from app.api import dashboard as dashboard_api
        from tests.test_api_dashboard import valid_document

        monkeypatch.setattr(dashboard_api, "ensure_student_analytics", fake_ensure)
        monkeypatch.setattr(dashboard_api, "generate_practice_questions", fake_generate)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/students/IT22145976/practice-questions?course_code=IT2040&session_name=Final%20Examination%202021"
            )
        assert response.status_code == 200
        assert response.json()["questions"][0]["topic"] == "SQL"
    finally:
        app.dependency_overrides.clear()
```

(`valid_document()` is the reshaped fixture defined in `tests/test_api_dashboard.py` from Task 6.)
```

- [ ] **Step 2: Run the practice API tests and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_practice_questions.py -q`
Expected: FAIL because the routes do not exist.

- [ ] **Step 3: Implement the endpoints**

In `app/api/dashboard.py`, add:

```python
@router.post("/{student_id}/practice-questions")
async def create_practice_questions(
    student_id: str, course_code: str, session_name: str, db=Depends(get_db)
):
    analysis = await ensure_student_analytics(db, student_id, course_code, session_name)
    result = await generate_practice_questions(db, student_id, course_code, session_name, analysis.next_question_strategy)
    if result["status"] != "ok":
        raise HTTPException(
            status_code=503,
            detail={"reason": result.get("reason", "generation_failed"),
                    "target": analysis.next_question_strategy.model_dump()},
        )
    return result["document"]


@router.get("/{student_id}/practice-questions")
async def get_practice_questions(
    student_id: str, course_code: str, session_name: str, fresh: bool = False, db=Depends(get_db)
):
    exam_id = f"{course_code}@{session_name}"
    cached = await find_generated_questions(db, student_id, exam_id)
    if cached is not None and not fresh:
        return cached
    return await create_practice_questions(student_id, course_code, session_name, db)
```

Add the missing imports to `app/api/dashboard.py`: `generate_practice_questions` from `app.services.practice_questions`, `find_generated_questions` from `app.db.repository`.

- [ ] **Step 4: Run the practice API tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_api_practice_questions.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add app/api/dashboard.py tests/test_api_practice_questions.py
git commit -m "feat: practice question generation endpoints"
```

---

### Task 17: Phase 3 and full-suite verification

**Files:**
- None unless a test exposes an inconsistency.

- [ ] **Step 1: Run static checks**

```powershell
git diff --check
.\.venv\Scripts\python.exe -m compileall -q app run_sample.py
```
Expected: exit 0.

- [ ] **Step 2: Run all new feature tests**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py tests/test_student_document_analytics.py tests/test_llm_student_analysis.py tests/test_repository.py tests/test_student_pipeline.py tests/test_student_dashboard_service.py tests/test_api_dashboard.py tests/test_run_sample.py tests/test_exam_analytics.py tests/test_exam_analytics_service.py tests/test_api_lecturer.py tests/test_llm_practice_questions.py tests/test_practice_questions.py tests/test_api_practice_questions.py -q
```
Expected: PASS.

- [ ] **Step 3: Run the complete offline suite**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```
Expected: PASS.

- [ ] **Step 4: Run the real sample runner**

```powershell
.\.venv\Scripts\python.exe run_sample.py dbms_analytics_test
```
Expected: five saved student IDs, zero failures, `student_analytics count=5`, `exam_analytics count=1`.

- [ ] **Step 5: Commit any corrections**

If needed: `git add app tests run_sample.py && git commit -m "test: verify phase 3 restructure"`. Otherwise do not create an empty commit.

## Plan Self-Review

- **Spec coverage:** every spec section is assigned. Slice 1: reshaped student document (Task 1), four-bucket thresholds (Task 2), pipeline assembly (Task 3), `exam_id` identity (Task 4), on-demand generation (Tasks 5-6). Slice 2: `examAnalytics` shape + math (Task 8), generator (Task 9), lecturer endpoints (Task 10), pipeline-run timing (Task 11), old-pipeline removal (Task 12). Slice 3: `generatedQuestions` (Task 14), generation service (Task 15), endpoints (Task 16). Error handling and offline tests are covered per task and in verification tasks.
- **Placeholder scan:** no TBD/TODO/ellipsis placeholders remain; every test fixture and implementation block contains concrete code, and cross-task helpers are referenced by their exact names (e.g. `exam_document()` from `tests/test_exam_analytics.py`, `valid_document()` from `tests/test_api_dashboard.py`, `fake_semantics` from `tests/test_run_sample.py`).
- **Type consistency:** `build_numeric_analysis`/`NumericStudentAnalysis`, `ensure_student_analytics`, `compute_exam_analytics`, `generate_practice_questions`, and repository function names are defined before downstream use.
