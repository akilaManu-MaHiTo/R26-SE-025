# Student Analytics MongoDB Materialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current student dashboard contract with the approved canonical student analytics document, materialize one document per graded sample submission, and persist it idempotently in MongoDB.

**Architecture:** Normalize and join raw `courses`, `rubricCollection`, and `submissions` documents, classify each unique rubric question through a validated Qwen service with deterministic fallback, calculate every numeric field in pure Python, then validate and upsert the final document. The student GET endpoint becomes a read-only lookup over `student_analytics`.

**Tech Stack:** Python 3.13, FastAPI 0.141.1, Pydantic 2.13.4, Motor 3.7.1/PyMongo 4.17.0, pytest 9.1.1, Qwen through the existing Ollama JSON client.

## Global Constraints

- The public response must use the exact top-level fields approved in `docs/superpowers/specs/2026-08-11-student-analytics-mongodb-design.md`.
- All totals, percentages, weighted averages, status labels, counts, and rankings are calculated in Python; model output never supplies numeric performance fields.
- Qwen is responsible only for Bloom/topic/subtopic semantics, explanations, learning gaps, recommendations, and generation targeting.
- Model failure must not prevent a numerically valid student document from being saved.
- `student_analytics` identity is `student_id + course.code + assessment.session_name` and writes are idempotent replacements.
- Frontend changes, authentication, regrading, and generated question content are out of scope.
- Preserve the user's unrelated `.gitignore` modification.
- Required verification excludes `tests/test_ollama_live.py` and disables optional embedding-model loading.

## File Map

- Replace: `app/schemas/student.py` — canonical public document and nested response models.
- Create: `app/ingestion/student_data.py` — raw source normalization and rubric/result joins.
- Create: `app/analytics/student_document.py` — pure deterministic document calculations.
- Create: `app/llm/roles/student_analysis.py` — validated semantic model outputs.
- Modify: `app/services/llm_service.py` — question-semantic and student-insight calls.
- Modify: `app/db/repository.py` — raw readers, index, upsert, and persisted lookup.
- Create: `app/services/student_pipeline.py` — batch orchestration and fallback behavior.
- Replace: `app/services/student_dashboard.py` — persisted dashboard lookup compatibility service.
- Modify: `app/api/dashboard.py` — replacement endpoint contract and optional filters.
- Modify: `run_sample.py` — seed raw sample collections and materialize every submission.
- Replace: `tests/test_schemas_student.py` — canonical schema contract.
- Create: `tests/test_student_data_ingestion.py` — normalization and join rules.
- Create: `tests/test_student_document_analytics.py` — deterministic calculation rules.
- Create: `tests/test_llm_student_analysis.py` — validated model success/degradation.
- Extend: `tests/test_repository.py` — `student_analytics` persistence behavior.
- Create: `tests/test_student_pipeline.py` — orchestration, reuse, isolation, and fallbacks.
- Replace: `tests/test_student_dashboard_service.py` — persisted lookup service.
- Replace: `tests/test_api_dashboard.py` — persisted API response and filters.
- Create: `tests/test_run_sample.py` — sample seeding and one-document-per-submission behavior.
- Remove: `tests/test_student_analytics.py` — tests the replaced dashboard model and old calculations.

---

### Task 1: Canonical student analytics schema

**Files:**
- Replace: `app/schemas/student.py`
- Replace: `tests/test_schemas_student.py`

**Interfaces:**
- Consumes: plain dictionaries assembled by the pipeline.
- Produces: `StudentAnalyticsDocument.model_validate(data)` and JSON-safe `model_dump(mode="json")`.

- [ ] **Step 1: Write the failing schema contract tests**

Create a fixture helper in `tests/test_schemas_student.py` that constructs the complete approved example with `StudentAnalyticsDocument`, then assert:

```python
def test_student_analytics_serializes_exact_top_level_contract():
    document = StudentAnalyticsDocument(**valid_document())
    assert set(document.model_dump(mode="json")) == {
        "student_id", "course", "assessment", "question_analysis",
        "topic_performance", "bloom_performance", "learning_analysis",
        "recommendations", "next_question_generation", "model_metadata",
    }
    assert document.assessment.percentage == 60.0
    assert document.question_analysis[0].criteria_performance[1].achieved is True


def test_student_analytics_rejects_invalid_performance_percentage():
    data = valid_document()
    data["assessment"]["percentage"] = 101.0
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


def test_student_analytics_rejects_unknown_bloom_level():
    data = valid_document()
    data["question_analysis"][0]["bloom_analysis"]["level"] = "Guess"
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)
```

- [ ] **Step 2: Run the schema tests and verify the old model fails the new contract**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py -q
```

Expected: FAIL because `StudentAnalyticsDocument` and its nested models do not exist.

- [ ] **Step 3: Implement the canonical nested models**

Replace `app/schemas/student.py` with focused Pydantic models using `Field(default_factory=list)` and constrained fields:

```python
BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
PerformanceStatus = Literal["Strong", "Needs Improvement", "Critical"]


class CourseInfo(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class AssessmentInfo(BaseModel):
    session_name: str = Field(min_length=1)
    rubric_ref: str = Field(min_length=1)
    total_score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)


class BloomAnalysis(BaseModel):
    level: BloomLevel
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class Performance(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)


class CriterionPerformance(BaseModel):
    criterion: str = Field(min_length=1)
    max_marks: float = Field(gt=0)
    awarded_marks: float = Field(ge=0)
    achieved: bool


class QuestionAnalysis(BaseModel):
    question_no: str
    question: str
    topic: str
    subtopic: str
    bloom_analysis: BloomAnalysis
    performance: Performance
    criteria_performance: list[CriterionPerformance] = Field(default_factory=list)
```

Add `TopicPerformance`, `BloomPerformance`, `LearningAnalysis`, `Recommendation`, `NextQuestionGeneration`, `ModelMetadata`, and `StudentAnalyticsDocument` with field names and types matching the approved JSON. Add model validators that reject `total_score > max_score`, question `score > max_score`, and criterion `awarded_marks > max_marks`.

- [ ] **Step 4: Run the schema tests**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit the canonical schema**

```powershell
git add app/schemas/student.py tests/test_schemas_student.py
git commit -m "feat: define canonical student analytics schema"
```

---

### Task 2: Raw course, rubric, and submission normalization

**Files:**
- Create: `app/ingestion/student_data.py`
- Create: `tests/test_student_data_ingestion.py`

**Interfaces:**
- Consumes: raw `course: dict`, `rubric: dict`, and `submission: dict`.
- Produces: `normalize_student_submission(course, rubric, submission) -> NormalizedStudentInput`.
- Produces internal models: `NormalizedCriterion`, `NormalizedQuestionInput`, and `NormalizedStudentInput`.

- [ ] **Step 1: Write failing join and validation tests**

Use the checked-in sample JSON through `app.sample_data.loader._load` and assert:

```python
def test_normalize_submission_joins_questions_and_criteria():
    rubric = _load("rubricCollection.json")
    submission = _load("submission.json")
    normalized = normalize_student_submission(
        {"course_code": "IT2040", "course_name": "Database Management Systems"},
        rubric,
        submission,
    )
    assert normalized.student_id == "IT21001234"
    assert normalized.course_code == "IT2040"
    assert normalized.course_name == "Database Management Systems"
    assert len(normalized.questions) == 11
    assert normalized.questions[0].question_no == "01"
    assert normalized.questions[0].score == 6.0
    assert normalized.questions[0].max_score == 8.0
    assert normalized.questions[0].criteria[0].awarded_marks == 2.5


def test_normalize_submission_rejects_result_without_rubric_question():
    submission = minimal_submission(q_no="99", score=1, max_score=1)
    with pytest.raises(StudentDataError, match="question 99"):
        normalize_student_submission(minimal_course(), minimal_rubric(), submission)


def test_normalize_submission_rejects_awarded_marks_above_maximum():
    submission = minimal_submission(q_no="01", score=6, max_score=5)
    with pytest.raises(StudentDataError, match="exceeds"):
        normalize_student_submission(minimal_course(), minimal_rubric(), submission)
```

- [ ] **Step 2: Run the ingestion tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_data_ingestion.py -q
```

Expected: FAIL because `app.ingestion.student_data` is missing.

- [ ] **Step 3: Implement internal normalized models and joins**

Implement:

```python
class StudentDataError(ValueError):
    pass


def normalize_question_no(value: object) -> str:
    text = str(value).strip()
    return text.zfill(2) if text.isdigit() else text


def normalize_student_submission(
    course: dict, rubric: dict, submission: dict
) -> NormalizedStudentInput:
    # Resolve student/course/session/rubric identity.
    # Index rubric questions and result rows by normalize_question_no().
    # Recalculate question maximum marks from the rubric.
    # Match evaluated criteria by normalized point text, falling back to position.
    # Raise StudentDataError for missing identity, missing result joins, or invalid marks.
```

Use `str(rubric.get("_id") or submission.get("rubric_ref") or "unknown")` for the API-safe rubric reference. Course name resolution order is `course_name`, `name`, and the IT2040 fallback `Database Management Systems`; otherwise use the course code so the required field is never blank for a valid source.

For each rubric criterion, prefer the evaluation criterion with identical stripped/case-folded text; if no exact match exists, use the criterion at the same position. `achieved` is not computed in this layer.

- [ ] **Step 4: Run ingestion tests**

Run the Step 2 command. Expected: PASS.

- [ ] **Step 5: Commit normalization**

```powershell
git add app/ingestion/student_data.py tests/test_student_data_ingestion.py
git commit -m "feat: normalize student assessment sources"
```

---

### Task 3: Deterministic document analytics

**Files:**
- Create: `app/analytics/student_document.py`
- Create: `tests/test_student_document_analytics.py`
- Remove: `tests/test_student_analytics.py`

**Interfaces:**
- Consumes: `NormalizedStudentInput` and `semantics_by_question: dict[str, QuestionSemantics]`.
- Produces: `build_numeric_analysis(normalized, semantics_by_question) -> NumericStudentAnalysis`.
- Produces: `performance_status(percentage: float) -> PerformanceStatus`.
- Produces deterministic fallbacks: `fallback_learning_gaps`, `fallback_recommendations`, and `fallback_generation_target`.

- [ ] **Step 1: Write failing deterministic calculation tests**

Create two-question normalized input with unequal maximum marks to prove weighted aggregation:

```python
def test_numeric_analysis_recalculates_totals_and_weighted_groups():
    normalized = two_question_input(
        first=(3.0, 5.0), second=(1.0, 5.0)
    )
    analysis = build_numeric_analysis(normalized, semantics())
    assert analysis.assessment.total_score == 4.0
    assert analysis.assessment.max_score == 10.0
    assert analysis.assessment.percentage == 40.0
    assert analysis.topic_performance[0].score == 4.0
    assert analysis.topic_performance[0].percentage == 40.0
    assert analysis.bloom_performance[0].average_score == 40.0


@pytest.mark.parametrize(
    ("percentage", "expected"),
    [(49.99, "Critical"), (50.0, "Needs Improvement"),
     (74.99, "Needs Improvement"), (75.0, "Strong")],
)
def test_performance_status_boundaries(percentage, expected):
    assert performance_status(percentage) == expected


def test_partial_criterion_marks_count_as_achieved():
    analysis = build_numeric_analysis(two_question_input(), semantics())
    criterion = analysis.question_analysis[0].criteria_performance[0]
    assert criterion.awarded_marks == 1.0
    assert criterion.max_marks == 2.0
    assert criterion.achieved is True
```

Also assert question ordering, non-Strong weak lists, Strong topic lists, missed-criterion fallback gaps, high-priority fallback recommendations, and five-question fallback target.

- [ ] **Step 2: Run analytics tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_document_analytics.py -q
```

Expected: FAIL because the new analytics module is missing.

- [ ] **Step 3: Implement pure calculations**

Implement with `Decimal`-safe source floats or regular floats plus a single output rounding boundary:

```python
STRONG_THRESHOLD = 75.0
IMPROVEMENT_THRESHOLD = 50.0


def percentage(score: float, max_score: float) -> float:
    if max_score <= 0:
        raise ValueError("max_score must be positive")
    return round(score / max_score * 100.0, 2)


def performance_status(value: float) -> str:
    if value >= STRONG_THRESHOLD:
        return "Strong"
    if value >= IMPROVEMENT_THRESHOLD:
        return "Needs Improvement"
    return "Critical"
```

Build `QuestionAnalysis` records first, then aggregate topic and Bloom groups by summing `score` and `max_score`. Never average already-rounded question percentages. `NumericStudentAnalysis` is an internal Pydantic model containing assessment, question/topic/Bloom sections, deterministic weak/strong lists, and fallback semantic content.

Generate weak subtopics only from questions whose performance status is not Strong, preserving first appearance and removing duplicates. Generate fallback gaps from zero-mark or partial criteria and use the subtopic when no missed criteria exist.

- [ ] **Step 4: Run analytics tests and remove obsolete tests**

Run Step 2, then delete `tests/test_student_analytics.py` because it asserts the replaced public contract. Expected: new analytics tests PASS.

- [ ] **Step 5: Commit deterministic analytics**

```powershell
git add app/analytics/student_document.py tests/test_student_document_analytics.py tests/test_student_analytics.py
git commit -m "feat: calculate canonical student analytics"
```

---

### Task 4: Validated Qwen semantics and insight calls

**Files:**
- Create: `app/llm/roles/student_analysis.py`
- Modify: `app/services/llm_service.py`
- Create: `tests/test_llm_student_analysis.py`

**Interfaces:**
- Produces: `QuestionSemantics` with `level`, `topic`, `subtopic`, `confidence`, and `reason`.
- Produces: `StudentInsightResponse` with learning gaps, recommendations, and generation target.
- Produces service functions:
  - `async classify_question_semantics(course: dict, question: str, criteria: list[str]) -> dict`
  - `async generate_student_insights(student_id: str, evidence: dict) -> dict`

- [ ] **Step 1: Write failing service tests**

Patch `validate_with_retry` to return real Pydantic outputs and assert prompt/input separation:

```python
async def test_classify_question_semantics_returns_validated_fields(monkeypatch):
    async def fake_validate(model, prompt, temperature):
        return model(
            level="Understand", topic="Concurrency Control",
            subtopic="Two-Phase Locking", confidence=0.94,
            reason="The question asks for an explanation.",
        ), {}, False
    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = await llm_service.classify_question_semantics(
        {"code": "SE3040", "name": "Software Architecture"},
        "Explain two-phase locking.", ["Mentions growing phase"],
    )
    assert result["status"] == "ok"
    assert result["semantics"]["subtopic"] == "Two-Phase Locking"


async def test_classify_question_semantics_degrades_when_qwen_is_unavailable(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise OllamaUnavailable("offline")
    monkeypatch.setattr(llm_service, "validate_with_retry", unavailable)
    result = await llm_service.classify_question_semantics(
        {"code": "IT2040", "name": "Database Management Systems"},
        "Explain two-phase locking.", [],
    )
    assert result == {"status": "degraded", "reason": "ollama_unavailable"}
```

For insights, assert that `StudentInsightResponse` accepts semantic strings and recommendation priorities but has no score, percentage, marks, or average fields. Assert schema failure returns `status="degraded"`.

- [ ] **Step 2: Run the new LLM tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_llm_student_analysis.py -q
```

Expected: FAIL because the role models and service functions are missing.

- [ ] **Step 3: Add role schemas**

Implement:

```python
class QuestionSemantics(BaseModel):
    level: BloomLevel
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class InsightRecommendation(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    topic: str
    bloom_level: BloomLevel
    action: str


class GenerationTarget(BaseModel):
    recommended_bloom_level: BloomLevel
    recommended_difficulty: Literal["Easy", "Medium", "Hard"]
    recommended_topics: list[str]


class StudentInsightResponse(BaseModel):
    learning_gaps: list[str]
    recommendations: list[InsightRecommendation]
    generation_target: GenerationTarget
```

- [ ] **Step 4: Add the two async Qwen service calls**

Prompts must explicitly state that the response schema contains no numeric performance calculations and that supplied backend evidence is authoritative. Call `validate_with_retry` with the new models. Return `{"status": "ok", ...}` on validated output and stable degraded reasons `ollama_unavailable` or `schema_failure` otherwise.

- [ ] **Step 5: Run LLM tests**

Run Step 2. Expected: PASS.

- [ ] **Step 6: Commit semantic services**

```powershell
git add app/llm/roles/student_analysis.py app/services/llm_service.py tests/test_llm_student_analysis.py
git commit -m "feat: add Qwen student semantic analysis"
```

---

### Task 5: MongoDB materialized-document repository

**Files:**
- Modify: `app/db/repository.py`
- Modify: `tests/test_repository.py`

**Interfaces:**
- Produces:
  - `find_graded_submissions(db) -> list[dict]`
  - `find_course_for_submission(db, submission) -> dict | None`
  - `find_rubric_for_submission(db, submission) -> dict | None`
  - `upsert_student_analytics(db, document: dict) -> None`
  - `find_student_analytics(db, student_id, course_code=None, session_name=None) -> dict | None`

- [ ] **Step 1: Write failing persistence tests**

Using the existing `test_db` fixture, clean only the test documents created by each test and assert:

```python
async def test_upsert_student_analytics_is_idempotent(test_db):
    doc = valid_document(student_id="IT22145976")
    await upsert_student_analytics(test_db, doc)
    doc["assessment"]["total_score"] = 7.0
    doc["assessment"]["percentage"] = 70.0
    await upsert_student_analytics(test_db, doc)
    saved = await test_db["student_analytics"].find(
        {"student_id": "IT22145976"}
    ).to_list(length=None)
    assert len(saved) == 1
    assert saved[0]["assessment"]["total_score"] == 7.0


async def test_find_student_analytics_filters_course_and_session(test_db):
    await upsert_student_analytics(test_db, valid_document(
        student_id="IT22145976", course_code="SE3040",
        session_name="Semester 1 Final Exam",
    ))
    found = await find_student_analytics(
        test_db, "IT22145976", "SE3040", "Semester 1 Final Exam"
    )
    assert found["course"]["code"] == "SE3040"
```

Add a test that `create_indexes` creates a unique named index for the compound identity and tests source lookup by `rubric_ref`, with subject/session fallback when sample IDs are placeholder strings.

- [ ] **Step 2: Run repository tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_repository.py -q
```

Expected: FAIL because repository functions are missing.

- [ ] **Step 3: Implement repository operations**

Add raw and materialized names to `COLLECTIONS`. Add the unique index:

```python
"student_analytics": [
    ("student_id", 1),
    ("course.code", 1),
    ("assessment.session_name", 1),
]
```

Implement upsert with the exact identity filter. Implement lookup with optional nested-field filters and `sort=[("_id", -1)]`; remove `_id` from a copied result before returning it. Raw source resolution first attempts exact references/codes and then the approved `subject_code + session_name` sample fallback.

- [ ] **Step 4: Run repository tests**

Run Step 2. Expected: PASS with local MongoDB available.

- [ ] **Step 5: Commit repository changes**

```powershell
git add app/db/repository.py tests/test_repository.py
git commit -m "feat: persist student analytics documents"
```

---

### Task 6: Batch materialization pipeline with fallbacks

**Files:**
- Create: `app/services/student_pipeline.py`
- Create: `tests/test_student_pipeline.py`

**Interfaces:**
- Produces `MaterializationFailure(student_id: str, reason: str)`.
- Produces `MaterializationResult(saved: list[str], failures: list[MaterializationFailure])`.
- Produces `async materialize_student_analytics(db, submissions: list[dict] | None = None) -> MaterializationResult`.

- [ ] **Step 1: Write failing orchestration tests**

Patch repository and LLM boundaries while using real normalization, analytics, and Pydantic models:

```python
async def test_pipeline_reuses_question_classification_across_students(monkeypatch):
    calls = 0
    async def classify(*args, **kwargs):
        nonlocal calls
        calls += 1
        return ok_semantics()
    monkeypatch.setattr(student_pipeline, "classify_question_semantics", classify)
    result = await materialize_student_analytics(
        fake_db_with_two_students_same_rubric()
    )
    assert len(result.saved) == 2
    assert calls == 2  # two unique rubric questions, not four student attempts


async def test_pipeline_uses_deterministic_fallback_when_qwen_is_down(monkeypatch):
    monkeypatch.setattr(
        student_pipeline, "classify_question_semantics",
        AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"}),
    )
    result = await materialize_student_analytics(fake_db_one_student())
    assert result.saved == ["IT22145976"]
    saved = captured_upsert_document()
    assert saved["assessment"]["percentage"] == 60.0
    assert saved["question_analysis"][0]["bloom_analysis"]["reason"]


async def test_pipeline_isolates_invalid_submission(monkeypatch):
    result = await materialize_student_analytics(
        fake_db_with_one_valid_and_one_invalid_submission()
    )
    assert result.saved == ["valid-student"]
    assert result.failures[0].student_id == "invalid-student"
```

Also assert Qwen insights replace only semantic fallback fields, `number_of_questions` remains backend-fixed at 5, model metadata reflects configured model/source metadata, and every saved dictionary validates as `StudentAnalyticsDocument`.

- [ ] **Step 2: Run pipeline tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_pipeline.py -q
```

Expected: FAIL because the pipeline module is missing.

- [ ] **Step 3: Implement orchestration and classification caching**

Implement this sequence per batch:

```python
submissions = submissions or await find_graded_submissions(db)
classification_cache: dict[tuple[str, str], QuestionSemantics] = {}
for submission in submissions:
    try:
        course = await find_course_for_submission(db, submission)
        rubric = await find_rubric_for_submission(db, submission)
        normalized = normalize_student_submission(course or {}, rubric or {}, submission)
        semantics = await _classify_questions(normalized, classification_cache)
        numeric = build_numeric_analysis(normalized, semantics)
        insights = await generate_student_insights(normalized.student_id, numeric.evidence())
        document = _assemble_document(normalized, numeric, insights)
        validated = StudentAnalyticsDocument.model_validate(document)
        await upsert_student_analytics(db, validated.model_dump(mode="json"))
        saved.append(normalized.student_id)
    except Exception as exc:
        failures.append(MaterializationFailure(
            student_id=str(submission.get("student_id", "unknown")),
            reason=str(exc),
        ))
```

The classification cache key is `(rubric_ref, question_no)`. For degraded classification, call the existing `classify_by_rules`, derive subtopic from the first key concept or dominant topic, map `high/medium/low` rule confidence to `0.85/0.65/0.4`, and include a fallback reason. For degraded insight generation, use Task 3 fallback content.

Assemble `learning_analysis.overall_performance` and all weak/strong lists only from `numeric`; allow Qwen to supply only `learning_gaps`, `recommendations`, recommended Bloom level, difficulty, and topics. Always force `number_of_questions=5` in backend code.

- [ ] **Step 4: Run pipeline tests**

Run Step 2. Expected: PASS.

- [ ] **Step 5: Commit pipeline**

```powershell
git add app/services/student_pipeline.py tests/test_student_pipeline.py
git commit -m "feat: materialize student analytics pipeline"
```

---

### Task 7: Replace dashboard service and API contract

**Files:**
- Replace: `app/services/student_dashboard.py`
- Modify: `app/api/dashboard.py`
- Replace: `tests/test_student_dashboard_service.py`
- Replace: `tests/test_api_dashboard.py`

**Interfaces:**
- Produces `async get_student_dashboard(db, student_id, course_code=None, session_name=None) -> StudentAnalyticsDocument`.
- HTTP: `GET /api/students/{student_id}/dashboard` with optional `course_code` and `session_name`.

- [ ] **Step 1: Write failing persisted-service and endpoint tests**

Service test:

```python
async def test_get_student_dashboard_returns_persisted_contract(monkeypatch):
    monkeypatch.setattr(
        student_dashboard, "find_student_analytics",
        AsyncMock(return_value=valid_document()),
    )
    result = await get_student_dashboard(object(), "IT22145976", "SE3040", None)
    assert isinstance(result, StudentAnalyticsDocument)
    assert result.student_id == "IT22145976"
```

API test overrides `get_db`, inserts/upserts the canonical document, requests the endpoint, and asserts the exact top-level key set from Task 1. Add filter-forwarding and 404 tests. Assert `_id` is absent.

- [ ] **Step 2: Run dashboard tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_student_dashboard_service.py tests/test_api_dashboard.py -q
```

Expected: FAIL because the old service computes the former dashboard model.

- [ ] **Step 3: Replace the service with persisted lookup**

Implement:

```python
class StudentDashboardNotFound(Exception):
    pass


async def get_student_dashboard(
    db, student_id: str, course_code: str | None = None,
    session_name: str | None = None,
) -> StudentAnalyticsDocument:
    document = await find_student_analytics(
        db, student_id, course_code, session_name
    )
    if document is None:
        raise StudentDashboardNotFound("no saved analytics found for student")
    return StudentAnalyticsDocument.model_validate(document)
```

- [ ] **Step 4: Replace the route response model**

Remove `run_id` and `include_llm`. Accept optional `course_code` and `session_name`, call `get_student_dashboard`, and retain the 404 mapping.

- [ ] **Step 5: Run dashboard tests**

Run Step 2. Expected: PASS.

- [ ] **Step 6: Commit the replacement API**

```powershell
git add app/services/student_dashboard.py app/api/dashboard.py tests/test_student_dashboard_service.py tests/test_api_dashboard.py
git commit -m "feat: serve persisted student analytics"
```

---

### Task 8: Sample-data seeding and end-to-end materialization

**Files:**
- Modify: `run_sample.py`
- Create: `tests/test_run_sample.py`

**Interfaces:**
- Produces `load_raw_sample_documents() -> tuple[list[dict], list[dict], list[dict]]`.
- Produces `async seed_raw_samples(db) -> dict[str, int]`.
- CLI remains `python run_sample.py [database_name]`.

- [ ] **Step 1: Write failing sample runner tests**

```python
def test_load_raw_sample_documents_loads_every_submission():
    courses, rubrics, submissions = load_raw_sample_documents()
    assert len(courses) == 1
    assert len(rubrics) == 1
    assert len(submissions) == 5
    assert all(s["status"] == "graded" for s in submissions)


async def test_seed_and_materialize_samples_saves_one_document_per_submission(test_db, monkeypatch):
    await seed_raw_samples(test_db)
    monkeypatch.setattr(student_pipeline, "classify_question_semantics", fake_semantics)
    monkeypatch.setattr(student_pipeline, "generate_student_insights", fake_insights)
    result = await materialize_student_analytics(test_db)
    saved = await test_db["student_analytics"].find({}).to_list(length=None)
    assert result.failures == []
    assert len(saved) == 5
    assert {d["student_id"] for d in saved} == {
        s["student_id"] for s in load_raw_sample_documents()[2]
    }
```

- [ ] **Step 2: Run sample tests and verify RED**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_run_sample.py -q
```

Expected: FAIL because the sample seed functions do not exist.

- [ ] **Step 3: Rewrite the sample runner**

Load `courses.json`, `rubricCollection.json`, and sorted `submission*.json`. Seed with stable replacement keys:

```python
await db["courses"].replace_one(
    {"subject_code": course.get("subject_code", "IT2040")}, course, upsert=True
)
await db["rubricCollection"].replace_one(
    {"subject_code": rubric["subject_code"], "session_name": rubric["session_name"]},
    rubric, upsert=True,
)
for submission in submissions:
    await db["submissions"].replace_one(
        {"student_id": submission["student_id"],
         "subject_code": submission["subject_code"],
         "session_name": submission["session_name"]},
        submission, upsert=True,
    )
```

Call `create_indexes`, `seed_raw_samples`, and `materialize_student_analytics`. Print saved student IDs, per-student failures, and final collection count. Return a non-zero process exit only when at least one sample submission fails.

- [ ] **Step 4: Run sample tests**

Run Step 2. Expected: PASS.

- [ ] **Step 5: Commit the sample workflow**

```powershell
git add run_sample.py tests/test_run_sample.py
git commit -m "feat: materialize sample student analytics"
```

---

### Task 9: Offline regression verification and documentation alignment

**Files:**
- Modify only if failures reveal an inconsistency: files already listed in Tasks 1–8.

**Interfaces:**
- Validates the complete backend without a live Qwen dependency.

- [ ] **Step 1: Run formatting/static sanity checks**

```powershell
git diff --check
.\.venv\Scripts\python.exe -m compileall -q app run_sample.py
```

Expected: both commands exit 0.

- [ ] **Step 2: Run all focused feature tests together**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py tests/test_student_data_ingestion.py tests/test_student_document_analytics.py tests/test_llm_student_analysis.py tests/test_repository.py tests/test_student_pipeline.py tests/test_student_dashboard_service.py tests/test_api_dashboard.py tests/test_run_sample.py -q
```

Expected: PASS with no live-model calls.

- [ ] **Step 3: Run the complete offline test suite**

```powershell
$env:EMBEDDING_AVAILABLE='false'
.\.venv\Scripts\python.exe -m pytest --ignore=tests/test_ollama_live.py -q
```

Expected: PASS. If a test asserts the deliberately replaced dashboard contract, update or remove that test within the already approved scope and rerun until green.

- [ ] **Step 4: Run the real sample materializer against the configured local MongoDB**

```powershell
.\.venv\Scripts\python.exe run_sample.py dbms_analytics_test
```

Expected: five saved student IDs, zero failures, and `student_analytics count=5`. Qwen may use deterministic fallbacks when the configured service is unavailable.

- [ ] **Step 5: Inspect one saved document through the API service boundary**

```powershell
.\.venv\Scripts\python.exe -c "import asyncio; from motor.motor_asyncio import AsyncIOMotorClient; from app.config import settings; from app.services.student_dashboard import get_student_dashboard; async def main(): client=AsyncIOMotorClient(settings.mongodb_uri); doc=await get_student_dashboard(client['dbms_analytics_test'], 'IT21001234'); print(doc.model_dump_json(indent=2)); client.close(); asyncio.run(main())"
```

If PowerShell rejects the one-line async definition, use the already-tested API endpoint or an interactive Python session to perform the same read-only inspection. Expected: exact canonical top-level fields and backend-calculated values.

- [ ] **Step 6: Commit any verification-only corrections**

If Steps 1–5 required scoped corrections:

```powershell
git add app tests run_sample.py
git commit -m "test: verify student analytics materialization"
```

If no corrections were needed, do not create an empty commit.

## Plan Self-Review

- Spec coverage: every approved component, calculation, fallback, persistence rule, sample workflow, and endpoint behavior is assigned to Tasks 1–9.
- Type consistency: `StudentAnalyticsDocument`, `NormalizedStudentInput`, `QuestionSemantics`, `NumericStudentAnalysis`, and repository/service function names are defined before downstream use.
- Scope: frontend work, auth, regrading, cohort redesign, and generated question content remain excluded.
- Test discipline: every production task begins with a failing focused test and an observed RED run before implementation.
