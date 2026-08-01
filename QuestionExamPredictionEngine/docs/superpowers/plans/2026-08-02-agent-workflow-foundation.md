# Agent Workflow Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap the repository's current question mapping, answer analysis, and cohort analytics behind three typed agent interfaces coordinated by one auditable workflow endpoint.

**Architecture:** Add internal Pydantic contracts, a lazy model registry, three side-effect-free agent classes, and a linear orchestrator. Preserve all current scoring and analytics functions as domain services, expose the workflow through a new FastAPI router, and return explicit partial-result warnings for ChromaDB retrieval, misconception extraction, and forecasting capabilities that are outside this phase.

**Tech Stack:** Python 3.14.4, Pydantic 2.13.4, FastAPI >=0.115.0, scikit-learn >=1.5.0, sentence-transformers >=5.4.1, standard-library `unittest` and `unittest.mock`.

## Global Constraints

- Preserve existing endpoint behavior and current grading semantics.
- Agents exchange Pydantic models rather than arbitrary prose or unvalidated dictionaries.
- Existing student marks remain authoritative in the analysis workflow.
- Agents perform no filesystem, database, or ChromaDB writes.
- Historical trend slopes must never be returned as future-topic probabilities.
- Optional capability failures return `partial` results with typed warnings.
- Do not log full student answers or personally identifying student data.
- Phase 1 adds no runtime dependency and performs no ChromaDB ingestion, LLM call, or forecasting-model training.

## Scope decomposition

This plan implements Phase 1 of the approved design and produces working software by itself. The remaining independent subsystems require separate implementation plans:

1. Lecture and rubric ingestion plus ChromaDB retrieval.
2. Structured misconception extraction and lecturer-labelled evaluation.
3. Temporally validated future-topic forecasting and calibration.
4. Persistent operational storage, asynchronous execution, and lecturer review.

## File structure

Files created in this plan:

- `src/agents/__init__.py`: public agent exports.
- `src/agents/contracts.py`: workflow inputs, outputs, statuses, warnings, and result conversion.
- `src/agents/model_registry.py`: lazy model registration, version reporting, and load-error isolation.
- `src/agents/question_knowledge_agent.py`: current topic and Bloom mapping wrapper.
- `src/agents/answer_misconception_agent.py`: current per-answer report wrapper and misconception capability boundary.
- `src/agents/cohort_prediction_agent.py`: current cohort analytics wrapper and forecasting capability boundary.
- `src/agents/orchestrator.py`: execution order, stable input hash, run metadata, and result aggregation.
- `src/api/routers/agent_workflows.py`: workflow HTTP adapter.
- `tests/agents/__init__.py`: agent test package.
- `tests/agents/test_contracts.py`: contract validation and record-conversion tests.
- `tests/agents/test_model_registry.py`: registry loading and failure-isolation tests.
- `tests/agents/test_question_knowledge_agent.py`: Agent 1 behavior tests.
- `tests/agents/test_answer_misconception_agent.py`: Agent 2 behavior tests.
- `tests/agents/test_cohort_prediction_agent.py`: Agent 3 behavior tests.
- `tests/agents/test_orchestrator.py`: workflow sequencing, reuse, and hashing tests.
- `tests/api/test_agent_workflows.py`: HTTP adapter tests.

Files modified in this plan:

- `src/api/dependencies.py`: cached registry and orchestrator construction.
- `src/api/schemas/requests.py`: workflow request schema.
- `src/api/schemas/responses.py`: workflow response schema.
- `src/api/app.py`: router registration and API description.
- `IMPLEMENTATION.md`: endpoint and architecture documentation.

---

### Task 1: Define stable agent contracts

**Files:**
- Create: `src/agents/__init__.py`
- Create: `src/agents/contracts.py`
- Create: `tests/agents/__init__.py`
- Create: `tests/agents/test_contracts.py`

**Interfaces:**
- Consumes: Pydantic `BaseModel`, `Field`, standard `datetime`, and `Enum`.
- Produces: `AgentStatus`, `AgentWarning`, `SourceCitation`, `AgentRunContext`, `QuestionMappingResult`, `Misconception`, `AnswerAnalysisResult`, `FutureTopicProbability`, `CohortPredictionResult`, and `AgentWorkflowResult`.

- [ ] **Step 1: Write failing contract validation tests**

```python
# tests/agents/test_contracts.py
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from src.agents.contracts import (
    AgentRunContext,
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    QuestionMappingResult,
)


class AgentContractTests(unittest.TestCase):
    def test_question_mapping_rejects_confidence_outside_unit_interval(self):
        with self.assertRaises(ValidationError):
            QuestionMappingResult(
                exam_id="dbms-2025",
                question_id="1",
                part_id="a",
                question_text="Explain normalization",
                max_marks=10,
                topic_ids=["Normalization"],
                mapping_confidence=1.1,
            )

    def test_answer_result_converts_to_existing_analytics_record(self):
        result = AnswerAnalysisResult(
            student_id="student-1",
            exam="DBMS",
            year="2025",
            question_id="1",
            part_id="a",
            topic="Normalization",
            marks_obtained=8,
            max_marks=10,
            performance_score=0.8,
            concept_score=0.7,
            cognitive_score=0.6,
            learning_score=0.735,
            concept_reference_source="model_answer",
            student_level="understand",
            required_level="apply",
        )

        record = result.to_analytics_record()

        self.assertEqual(record["question"], "1")
        self.assertEqual(record["part"], "a")
        self.assertEqual(record["score"], 8.0)
        self.assertNotIn("misconceptions", record)

    def test_run_context_requires_timezone_aware_timestamp(self):
        with self.assertRaises(ValidationError):
            AgentRunContext(
                run_id="run-1",
                input_hash="abc",
                exam_id="dbms-2025",
                started_at=datetime(2025, 1, 1),
            )

    def test_partial_result_can_carry_typed_warning(self):
        warning = AgentWarning(
            code="knowledge_retrieval_unavailable",
            message="No knowledge retriever is configured",
            capability="knowledge_retrieval",
        )
        self.assertEqual(AgentStatus.PARTIAL.value, "partial")
        self.assertEqual(warning.capability, "knowledge_retrieval")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the contract test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_contracts -v
```

Expected: `ModuleNotFoundError: No module named 'src.agents'`.

- [ ] **Step 3: Implement the contracts and analytics-record conversion**

```python
# src/agents/contracts.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class AgentWarning(BaseModel):
    code: str
    message: str
    capability: str | None = None


class SourceCitation(BaseModel):
    source_id: str
    source_path: str
    page: int | None = None
    chunk_id: str | None = None
    excerpt: str = ""
    retrieval_distance: float | None = None


class AgentRunContext(BaseModel):
    run_id: str
    input_hash: str
    exam_id: str
    started_at: datetime
    model_versions: dict[str, str] = Field(default_factory=dict)
    warnings: list[AgentWarning] = Field(default_factory=list)

    @field_validator("started_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware")
        return value


class QuestionMappingResult(BaseModel):
    exam_id: str
    question_id: str
    part_id: str
    question_text: str
    max_marks: float = Field(ge=0)
    topic_ids: list[str] = Field(default_factory=list)
    rubric_criteria: list[str] = Field(default_factory=list)
    required_bloom_level: str | None = None
    source_citations: list[SourceCitation] = Field(default_factory=list)
    mapping_confidence: float = Field(default=0.0, ge=0, le=1)
    status: AgentStatus = AgentStatus.SUCCESS
    warnings: list[AgentWarning] = Field(default_factory=list)


class Misconception(BaseModel):
    concept_id: str
    misconception_type: str
    answer_evidence: str
    expected_understanding: str
    source_citations: list[SourceCitation] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class AnswerAnalysisResult(BaseModel):
    student_id: str
    exam: str
    year: str
    question_id: str
    part_id: str
    topic: str
    marks_obtained: float = Field(ge=0)
    max_marks: float = Field(gt=0)
    performance_score: float = Field(ge=0, le=1)
    similarity_score: float | None = Field(default=None, ge=-1, le=1)
    concept_score: float = Field(ge=0, le=1)
    cognitive_score: float = Field(ge=0, le=1)
    learning_score: float = Field(ge=0, le=1)
    concept_reference_source: str
    student_level: str
    required_level: str
    misconceptions: list[Misconception] = Field(default_factory=list)
    weak_concepts: list[str] = Field(default_factory=list)
    feedback: str | None = None
    analysis_confidence: float = Field(default=1.0, ge=0, le=1)
    status: AgentStatus = AgentStatus.SUCCESS
    warnings: list[AgentWarning] = Field(default_factory=list)

    def to_analytics_record(self) -> dict[str, Any]:
        return {
            "student_id": self.student_id,
            "exam": self.exam,
            "year": self.year,
            "question": self.question_id,
            "part": self.part_id,
            "score": self.marks_obtained,
            "max_marks": self.max_marks,
            "performance_score": self.performance_score,
            "concept_score": self.concept_score,
            "concept_reference_source": self.concept_reference_source,
            "cognitive_score": self.cognitive_score,
            "student_level": self.student_level,
            "required_level": self.required_level,
            "topic": self.topic,
            "learning_score": self.learning_score,
        }


class FutureTopicProbability(BaseModel):
    topic: str
    probability: float = Field(ge=0, le=1)
    forecast_year: int
    supporting_features: dict[str, float] = Field(default_factory=dict)
    training_years: list[int] = Field(default_factory=list)
    model_version: str
    calibration_status: str


class CohortPredictionResult(BaseModel):
    exam_id: str
    question_summaries: list[dict[str, Any]] = Field(default_factory=list)
    student_summaries: list[dict[str, Any]] = Field(default_factory=list)
    weak_topics: list[dict[str, Any]] = Field(default_factory=list)
    misunderstood_questions: list[dict[str, Any]] = Field(default_factory=list)
    cognitive_gaps: list[dict[str, Any]] = Field(default_factory=list)
    historical_trends: dict[str, Any] = Field(default_factory=dict)
    future_topic_probabilities: list[FutureTopicProbability] = Field(default_factory=list)
    forecast_model_version: str | None = None
    status: AgentStatus = AgentStatus.SUCCESS
    warnings: list[AgentWarning] = Field(default_factory=list)


class AgentWorkflowResult(BaseModel):
    context: AgentRunContext
    question_mappings: list[QuestionMappingResult]
    answer_analyses: list[AnswerAnalysisResult]
    cohort_result: CohortPredictionResult
    status: AgentStatus
    warnings: list[AgentWarning] = Field(default_factory=list)
```

Export these names explicitly from `src/agents/__init__.py`. Keep `tests/agents/__init__.py` empty.

- [ ] **Step 4: Run the contract tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_contracts -v
```

Expected: four tests pass.

- [ ] **Step 5: Commit the contracts**

```powershell
git add src/agents/__init__.py src/agents/contracts.py tests/agents/__init__.py tests/agents/test_contracts.py
git commit -m "feat: define agent workflow contracts"
```

---

### Task 2: Add a lazy model registry

**Files:**
- Create: `src/agents/model_registry.py`
- Create: `tests/agents/test_model_registry.py`

**Interfaces:**
- Consumes: zero-argument model loader callables.
- Produces: `ModelRegistry.register(name: str, version: str, loader: Callable[[], Any], optional: bool = True)`, `get(name: str) -> Any`, `try_get(name: str) -> tuple[Any | None, AgentWarning | None]`, `versions() -> dict[str, str]`, and `statuses() -> list[ModelCapabilityStatus]`.

- [ ] **Step 1: Write failing registry tests**

```python
# tests/agents/test_model_registry.py
import unittest

from src.agents.model_registry import ModelRegistry, ModelUnavailableError


class ModelRegistryTests(unittest.TestCase):
    def test_loader_runs_once_and_version_is_reported(self):
        calls = []
        registry = ModelRegistry()
        registry.register("similarity", "minilm-local-v1", lambda: calls.append(1) or object())

        first = registry.get("similarity")
        second = registry.get("similarity")

        self.assertIs(first, second)
        self.assertEqual(calls, [1])
        self.assertEqual(registry.versions(), {"similarity": "minilm-local-v1"})

    def test_optional_failure_is_isolated_as_warning(self):
        registry = ModelRegistry()
        registry.register(
            "forecaster",
            "unavailable",
            lambda: (_ for _ in ()).throw(RuntimeError("artifact missing")),
            optional=True,
        )

        model, warning = registry.try_get("forecaster")

        self.assertIsNone(model)
        self.assertEqual(warning.code, "model_unavailable")
        self.assertEqual(warning.capability, "forecaster")

    def test_required_failure_raises_model_unavailable_error(self):
        registry = ModelRegistry()
        registry.register("required", "v1", lambda: 1 / 0, optional=False)
        with self.assertRaises(ModelUnavailableError):
            registry.get("required")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the registry tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_model_registry -v
```

Expected: import failure for `src.agents.model_registry`.

- [ ] **Step 3: Implement lazy loading and isolated failures**

```python
# src/agents/model_registry.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from src.agents.contracts import AgentWarning


class ModelUnavailableError(RuntimeError):
    pass


class ModelCapabilityStatus(BaseModel):
    name: str
    version: str
    optional: bool
    loaded: bool
    error: str | None = None


@dataclass(frozen=True)
class _Registration:
    version: str
    loader: Callable[[], Any]
    optional: bool


class ModelRegistry:
    def __init__(self):
        self._registrations: dict[str, _Registration] = {}
        self._instances: dict[str, Any] = {}
        self._errors: dict[str, str] = {}

    def register(self, name: str, version: str, loader: Callable[[], Any], optional: bool = True) -> None:
        if name in self._registrations:
            raise ValueError(f"Model capability already registered: {name}")
        self._registrations[name] = _Registration(version, loader, optional)

    def get(self, name: str) -> Any:
        if name not in self._registrations:
            raise KeyError(name)
        if name in self._instances:
            return self._instances[name]
        registration = self._registrations[name]
        try:
            instance = registration.loader()
        except Exception as exc:
            self._errors[name] = str(exc)
            raise ModelUnavailableError(f"{name}: {exc}") from exc
        self._instances[name] = instance
        return instance

    def try_get(self, name: str) -> tuple[Any | None, AgentWarning | None]:
        try:
            return self.get(name), None
        except ModelUnavailableError as exc:
            registration = self._registrations[name]
            if not registration.optional:
                raise
            return None, AgentWarning(
                code="model_unavailable",
                message=str(exc),
                capability=name,
            )

    def versions(self) -> dict[str, str]:
        return {name: item.version for name, item in self._registrations.items()}

    def statuses(self) -> list[ModelCapabilityStatus]:
        return [
            ModelCapabilityStatus(
                name=name,
                version=item.version,
                optional=item.optional,
                loaded=name in self._instances,
                error=self._errors.get(name),
            )
            for name, item in self._registrations.items()
        ]
```

- [ ] **Step 4: Run the registry and contract tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_model_registry tests.agents.test_contracts -v
```

Expected: seven tests pass.

- [ ] **Step 5: Commit the registry**

```powershell
git add src/agents/model_registry.py tests/agents/test_model_registry.py
git commit -m "feat: add lazy agent model registry"
```

---

### Task 3: Implement the Question Knowledge Agent

**Files:**
- Create: `src/agents/question_knowledge_agent.py`
- Create: `tests/agents/test_question_knowledge_agent.py`
- Modify: `src/agents/__init__.py`

**Interfaces:**
- Consumes: `run(exam_id: str, exam_data: dict, question: dict, part: dict, rubric_criteria: list[str] | None = None) -> QuestionMappingResult`.
- Produces: one normalized question mapping with current topic and Bloom classification plus an explicit retrieval-capability warning.

- [ ] **Step 1: Write failing Agent 1 tests**

```python
# tests/agents/test_question_knowledge_agent.py
import unittest

from src.agents.contracts import AgentStatus
from src.agents.question_knowledge_agent import QuestionKnowledgeAgent


class QuestionKnowledgeAgentTests(unittest.TestCase):
    def setUp(self):
        self.exam = {
            "exam": "DBMS",
            "year": 2025,
            "questions": [{
                "question_number": 1,
                "topic": "Normalization",
                "parts": [{
                    "part": "a",
                    "question": "Analyze normalization anomalies",
                    "max_marks": 10,
                }],
            }],
        }

    def test_maps_current_topic_bloom_and_rubric(self):
        question = self.exam["questions"][0]
        part = question["parts"][0]

        result = QuestionKnowledgeAgent().run(
            "dbms-2025",
            self.exam,
            question,
            part,
            rubric_criteria=["Identify update anomalies"],
        )

        self.assertEqual(result.topic_ids, ["Normalization"])
        self.assertEqual(result.required_bloom_level, "analyze")
        self.assertEqual(result.rubric_criteria, ["Identify update anomalies"])
        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertEqual(result.warnings[0].code, "knowledge_retrieval_unavailable")

    def test_uses_question_part_fallback_topic(self):
        question = {"question_number": 3, "parts": []}
        part = {"part": "b", "question": "State one property", "max_marks": 2}
        result = QuestionKnowledgeAgent().run("dbms-2025", {"questions": []}, question, part)
        self.assertEqual(result.topic_ids, ["Q3b"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run Agent 1 tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_question_knowledge_agent -v
```

Expected: import failure for `question_knowledge_agent`.

- [ ] **Step 3: Implement current topic and Bloom mapping**

```python
# src/agents/question_knowledge_agent.py
from src.agents.contracts import AgentStatus, AgentWarning, QuestionMappingResult
from src.analysis.scoring.cognitive import detect_level
from src.analytics.topic_utils import resolve_topic


class QuestionKnowledgeAgent:
    def run(
        self,
        exam_id: str,
        exam_data: dict,
        question: dict,
        part: dict,
        rubric_criteria: list[str] | None = None,
    ) -> QuestionMappingResult:
        question_id = str(question.get("question_number", ""))
        part_id = str(part.get("part", ""))
        question_text = str(part.get("question", ""))
        topic = resolve_topic(
            exam_data,
            question_id,
            part_id,
            default=f"Q{question_id}{part_id}",
        )
        bloom_level, bloom_confidence = detect_level(question_text, "question")
        warning = AgentWarning(
            code="knowledge_retrieval_unavailable",
            message="Phase 1 uses exam metadata; no knowledge retriever is configured",
            capability="knowledge_retrieval",
        )
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=question_id,
            part_id=part_id,
            question_text=question_text,
            max_marks=float(part.get("max_marks", 0) or 0),
            topic_ids=[str(topic)],
            rubric_criteria=list(rubric_criteria or []),
            required_bloom_level=bloom_level,
            mapping_confidence=bloom_confidence,
            status=AgentStatus.PARTIAL,
            warnings=[warning],
        )
```

Export `QuestionKnowledgeAgent` from `src/agents/__init__.py`.

- [ ] **Step 4: Run Agent 1 and contract tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_question_knowledge_agent tests.agents.test_contracts -v
```

Expected: six tests pass.

- [ ] **Step 5: Commit Agent 1**

```powershell
git add src/agents/__init__.py src/agents/question_knowledge_agent.py tests/agents/test_question_knowledge_agent.py
git commit -m "feat: add question knowledge agent"
```

---

### Task 4: Implement the Answer and Misconception Agent

**Files:**
- Create: `src/agents/answer_misconception_agent.py`
- Create: `tests/agents/test_answer_misconception_agent.py`
- Modify: `src/agents/__init__.py`

**Interfaces:**
- Consumes: `run(exam_data: dict, student: dict, model_answers: dict | None, mappings: dict[tuple[str, str], QuestionMappingResult], **weights: float) -> list[AnswerAnalysisResult]`.
- Produces: one typed result for every answer part while preserving current `build_student_reports()` output and authoritative existing marks.

- [ ] **Step 1: Write failing Agent 2 tests**

```python
# tests/agents/test_answer_misconception_agent.py
import unittest
from unittest.mock import patch

from src.agents.answer_misconception_agent import AnswerMisconceptionAgent
from src.agents.contracts import AgentStatus, QuestionMappingResult


class AnswerMisconceptionAgentTests(unittest.TestCase):
    @patch("src.agents.answer_misconception_agent.build_student_reports")
    def test_preserves_existing_report_values_and_marks_partial(self, build_mock):
        build_mock.return_value = [{
            "student_id": "student-1", "exam": "DBMS", "year": "2025",
            "question": "1", "part": "a", "score": 8.0, "max_marks": 10.0,
            "performance_score": 0.8, "concept_score": 0.7,
            "concept_reference_source": "model_answer", "cognitive_score": 0.6,
            "student_level": "understand", "required_level": "apply",
            "topic": "Normalization", "learning_score": 0.735,
        }]
        mapping = QuestionMappingResult(
            exam_id="dbms-2025", question_id="1", part_id="a",
            question_text="Explain normalization", max_marks=10,
            topic_ids=["Normalization"], mapping_confidence=0.8,
        )

        results = AnswerMisconceptionAgent().run(
            {"questions": []},
            {"student_id": "student-1", "answers": []},
            {},
            {("1", "a"): mapping},
        )

        self.assertEqual(results[0].marks_obtained, 8.0)
        self.assertEqual(results[0].learning_score, 0.735)
        self.assertEqual(results[0].status, AgentStatus.PARTIAL)
        self.assertEqual(results[0].misconceptions, [])
        self.assertEqual(results[0].warnings[0].code, "misconception_extractor_unavailable")

    @patch("src.agents.answer_misconception_agent.build_student_reports", return_value=[])
    def test_empty_student_report_returns_empty_result(self, _build_mock):
        self.assertEqual(AnswerMisconceptionAgent().run({}, {}, {}, {}), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run Agent 2 tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_answer_misconception_agent -v
```

Expected: import failure for `answer_misconception_agent`.

- [ ] **Step 3: Implement the current report adapter and explicit capability warning**

```python
# src/agents/answer_misconception_agent.py
from src.agents.contracts import (
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    QuestionMappingResult,
)
from src.analysis.exam_analysis import build_student_reports


class AnswerMisconceptionAgent:
    def run(
        self,
        exam_data: dict,
        student: dict,
        model_answers: dict | None,
        mappings: dict[tuple[str, str], QuestionMappingResult],
        *,
        performance_weight: float = 0.6,
        concept_weight: float = 0.25,
        cognitive_weight: float = 0.15,
    ) -> list[AnswerAnalysisResult]:
        reports = build_student_reports(
            exam_data,
            [student],
            model_answers,
            performance_weight=performance_weight,
            concept_weight=concept_weight,
            cognitive_weight=cognitive_weight,
        )
        warning = AgentWarning(
            code="misconception_extractor_unavailable",
            message="Phase 1 preserves analytical scores without structured misconception extraction",
            capability="misconception_extraction",
        )
        results = []
        for report in reports:
            question_id = str(report["question"])
            part_id = str(report["part"])
            mapping = mappings.get((question_id, part_id))
            topic = mapping.topic_ids[0] if mapping and mapping.topic_ids else str(report["topic"])
            weak_concepts = [topic] if float(report["concept_score"]) < 0.5 else []
            results.append(AnswerAnalysisResult(
                student_id=str(report["student_id"]),
                exam=str(report["exam"]),
                year=str(report["year"]),
                question_id=question_id,
                part_id=part_id,
                topic=topic,
                marks_obtained=float(report["score"]),
                max_marks=float(report["max_marks"]),
                performance_score=float(report["performance_score"]),
                concept_score=float(report["concept_score"]),
                cognitive_score=float(report["cognitive_score"]),
                learning_score=float(report["learning_score"]),
                concept_reference_source=str(report["concept_reference_source"]),
                student_level=str(report["student_level"]),
                required_level=str(report["required_level"]),
                weak_concepts=weak_concepts,
                status=AgentStatus.PARTIAL,
                warnings=[warning],
            ))
        return results
```

Export `AnswerMisconceptionAgent` from `src/agents/__init__.py`.

- [ ] **Step 4: Run Agent 2 tests and current exam-analysis tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_answer_misconception_agent tests.test_cleanup.ExamAnalysisTests -v
```

Expected: all tests pass and current report calculations remain unchanged.

- [ ] **Step 5: Commit Agent 2**

```powershell
git add src/agents/__init__.py src/agents/answer_misconception_agent.py tests/agents/test_answer_misconception_agent.py
git commit -m "feat: add answer misconception agent boundary"
```

---

### Task 5: Implement the Cohort Analytics and Prediction Agent

**Files:**
- Create: `src/agents/cohort_prediction_agent.py`
- Create: `tests/agents/test_cohort_prediction_agent.py`
- Modify: `src/agents/__init__.py`

**Interfaces:**
- Consumes: `run(exam_id: str, exam_data: dict, analyses: list[AnswerAnalysisResult], weak_threshold: float = 0.5, weak_min_students: int = 2, weak_min_below_share: float = 0.4) -> CohortPredictionResult`.
- Produces: current cohort analytics and historical trends, an empty future-probability list, and a forecasting capability warning.

- [ ] **Step 1: Write failing Agent 3 tests**

```python
# tests/agents/test_cohort_prediction_agent.py
import unittest

from src.agents.cohort_prediction_agent import CohortPredictionAgent
from src.agents.contracts import AgentStatus, AnswerAnalysisResult


def answer(student_id: str, learning_score: float) -> AnswerAnalysisResult:
    return AnswerAnalysisResult(
        student_id=student_id, exam="DBMS", year="2025",
        question_id="1", part_id="a", topic="Normalization",
        marks_obtained=learning_score * 10, max_marks=10,
        performance_score=learning_score, concept_score=learning_score,
        cognitive_score=learning_score, learning_score=learning_score,
        concept_reference_source="model_answer", student_level="understand",
        required_level="apply",
    )


class CohortPredictionAgentTests(unittest.TestCase):
    def test_returns_current_analytics_without_fake_forecast(self):
        result = CohortPredictionAgent().run(
            "dbms-2025",
            {"questions": []},
            [answer("s1", 0.2), answer("s2", 0.3)],
        )

        self.assertEqual(result.status, AgentStatus.PARTIAL)
        self.assertTrue(result.question_summaries)
        self.assertTrue(result.misunderstood_questions)
        self.assertTrue(result.weak_topics)
        self.assertIn("Normalization", result.historical_trends)
        self.assertEqual(result.future_topic_probabilities, [])
        self.assertEqual(result.warnings[0].code, "forecaster_unavailable")

    def test_empty_cohort_is_valid_partial_result(self):
        result = CohortPredictionAgent().run("dbms-2025", {}, [])
        self.assertEqual(result.question_summaries, [])
        self.assertEqual(result.future_topic_probabilities, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run Agent 3 tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_cohort_prediction_agent -v
```

Expected: import failure for `cohort_prediction_agent`.

- [ ] **Step 3: Implement cohort aggregation using existing analyzers**

```python
# src/agents/cohort_prediction_agent.py
from src.agents.contracts import (
    AgentStatus,
    AgentWarning,
    AnswerAnalysisResult,
    CohortPredictionResult,
)
from src.analytics.cognitive_gap_analysis import CognitiveGapAnalyzer
from src.analytics.misunderstood_questions import MisunderstoodQuestionsAnalyzer
from src.analytics.question_analysis import analyze_questions
from src.analytics.student_analysis import analyze_student_performance
from src.analytics.weak_topic_analysis import WeakTopicAnalyzer
from src.prediction.trend_analysis import analyze_trends


class CohortPredictionAgent:
    def run(
        self,
        exam_id: str,
        exam_data: dict,
        analyses: list[AnswerAnalysisResult],
        *,
        weak_threshold: float = 0.5,
        weak_min_students: int = 2,
        weak_min_below_share: float = 0.4,
    ) -> CohortPredictionResult:
        records = [analysis.to_analytics_record() for analysis in analyses]
        warning = AgentWarning(
            code="forecaster_unavailable",
            message="Historical trends are descriptive; no validated topic forecaster is configured",
            capability="future_topic_forecasting",
        )
        return CohortPredictionResult(
            exam_id=exam_id,
            question_summaries=analyze_questions(records, weak_threshold=weak_threshold),
            student_summaries=analyze_student_performance(records, weak_threshold=weak_threshold),
            misunderstood_questions=MisunderstoodQuestionsAnalyzer(
                threshold=weak_threshold,
                minimum_students=weak_min_students,
                minimum_below_share=weak_min_below_share,
            ).analyze(records),
            cognitive_gaps=CognitiveGapAnalyzer().analyze(records),
            weak_topics=WeakTopicAnalyzer(
                exam_data=exam_data,
                threshold=weak_threshold,
            ).analyze(records),
            historical_trends=analyze_trends(records, by="topic", time_key="year"),
            future_topic_probabilities=[],
            forecast_model_version=None,
            status=AgentStatus.PARTIAL,
            warnings=[warning],
        )
```

Export `CohortPredictionAgent` from `src/agents/__init__.py`.

- [ ] **Step 4: Run Agent 3 tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_cohort_prediction_agent -v
```

Expected: two tests pass and no future probability is emitted.

- [ ] **Step 5: Commit Agent 3**

```powershell
git add src/agents/__init__.py src/agents/cohort_prediction_agent.py tests/agents/test_cohort_prediction_agent.py
git commit -m "feat: add cohort prediction agent boundary"
```

---

### Task 6: Implement the linear orchestrator

**Files:**
- Create: `src/agents/orchestrator.py`
- Create: `tests/agents/test_orchestrator.py`
- Modify: `src/agents/__init__.py`

**Interfaces:**
- Consumes: `run(exam_data: dict, students: list[dict], model_answers: dict | None = None, rubric: dict[str, list[str]] | None = None, thresholds and weights as keyword arguments) -> AgentWorkflowResult`.
- Produces: one run context, one mapping per question part, one analysis per answer part, one cohort result, and stable SHA-256 input hash.

- [ ] **Step 1: Write failing orchestration tests**

```python
# tests/agents/test_orchestrator.py
import unittest
from unittest.mock import Mock

from src.agents.contracts import (
    AgentStatus,
    AnswerAnalysisResult,
    CohortPredictionResult,
    QuestionMappingResult,
)
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.exam = {
            "exam": "DBMS", "year": 2025,
            "questions": [{
                "question_number": 1,
                "parts": [{"part": "a", "question": "Explain normalization", "max_marks": 10}],
            }],
        }
        self.students = [{
            "student_id": "s1",
            "answers": [{"question_number": 1, "parts": [{"part": "a", "answer": "text", "score": 8, "max_marks": 10}]}],
        }]

    def test_maps_question_once_before_answer_and_cohort_agents(self):
        question_agent = Mock()
        answer_agent = Mock()
        cohort_agent = Mock()
        mapping = QuestionMappingResult(
            exam_id="DBMS-2025", question_id="1", part_id="a",
            question_text="Explain normalization", max_marks=10,
            topic_ids=["Normalization"], mapping_confidence=0.8,
            status=AgentStatus.PARTIAL,
        )
        question_agent.run.return_value = mapping
        answer_agent.run.return_value = []
        cohort_agent.run.return_value = CohortPredictionResult(
            exam_id="DBMS-2025", status=AgentStatus.PARTIAL,
        )
        registry = ModelRegistry()
        registry.register("similarity", "v1", lambda: object())

        result = ExamAnalysisOrchestrator(
            registry, question_agent, answer_agent, cohort_agent,
        ).run(self.exam, self.students)

        question_agent.run.assert_called_once()
        answer_agent.run.assert_called_once()
        cohort_agent.run.assert_called_once()
        self.assertEqual(result.context.model_versions, {"similarity": "v1"})
        self.assertEqual(result.status, AgentStatus.PARTIAL)

    def test_input_hash_is_stable_across_equivalent_runs(self):
        orchestrator = ExamAnalysisOrchestrator.with_defaults(ModelRegistry())
        first = orchestrator._input_hash(self.exam, self.students, {}, {})
        second = orchestrator._input_hash(dict(self.exam), list(self.students), {}, {})
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run orchestrator tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_orchestrator -v
```

Expected: import failure for `src.agents.orchestrator`.

- [ ] **Step 3: Implement deterministic sequencing and hashing**

```python
# src/agents/orchestrator.py
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import uuid4

from src.agents.answer_misconception_agent import AnswerMisconceptionAgent
from src.agents.cohort_prediction_agent import CohortPredictionAgent
from src.agents.contracts import AgentRunContext, AgentStatus, AgentWorkflowResult
from src.agents.model_registry import ModelRegistry
from src.agents.question_knowledge_agent import QuestionKnowledgeAgent


class ExamAnalysisOrchestrator:
    def __init__(self, registry, question_agent, answer_agent, cohort_agent):
        self.registry = registry
        self.question_agent = question_agent
        self.answer_agent = answer_agent
        self.cohort_agent = cohort_agent

    @classmethod
    def with_defaults(cls, registry: ModelRegistry):
        return cls(
            registry,
            QuestionKnowledgeAgent(),
            AnswerMisconceptionAgent(),
            CohortPredictionAgent(),
        )

    @staticmethod
    def _input_hash(exam_data, students, model_answers, rubric) -> str:
        payload = json.dumps(
            {
                "exam_data": exam_data,
                "students": students,
                "model_answers": model_answers,
                "rubric": rubric,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def run(
        self,
        exam_data: dict,
        students: list[dict],
        model_answers: dict | None = None,
        rubric: dict[str, list[str]] | None = None,
        **options,
    ) -> AgentWorkflowResult:
        model_answers = model_answers or {}
        rubric = rubric or {}
        exam_id = f"{exam_data.get('exam', 'EXAM')}-{exam_data.get('year', 'UNKNOWN')}"
        mappings = []
        mapping_index = {}
        for question in exam_data.get("questions", []):
            question_id = str(question.get("question_number", ""))
            for part in question.get("parts", []):
                part_id = str(part.get("part", ""))
                criteria = rubric.get(f"{question_id}:{part_id}", [])
                mapping = self.question_agent.run(
                    exam_id, exam_data, question, part, criteria,
                )
                mappings.append(mapping)
                mapping_index[(question_id, part_id)] = mapping

        analyses = []
        weight_options = {
            name: options[name]
            for name in ("performance_weight", "concept_weight", "cognitive_weight")
            if name in options
        }
        for student in students:
            analyses.extend(self.answer_agent.run(
                exam_data, student, model_answers, mapping_index, **weight_options,
            ))

        threshold_options = {
            name: options[name]
            for name in ("weak_threshold", "weak_min_students", "weak_min_below_share")
            if name in options
        }
        cohort = self.cohort_agent.run(
            exam_id, exam_data, analyses, **threshold_options,
        )
        statuses = [item.status for item in mappings]
        statuses.extend(item.status for item in analyses)
        statuses.append(cohort.status)
        status = AgentStatus.FAILED if AgentStatus.FAILED in statuses else (
            AgentStatus.PARTIAL if AgentStatus.PARTIAL in statuses else AgentStatus.SUCCESS
        )
        context = AgentRunContext(
            run_id=str(uuid4()),
            input_hash=self._input_hash(exam_data, students, model_answers, rubric),
            exam_id=exam_id,
            started_at=datetime.now(timezone.utc),
            model_versions=self.registry.versions(),
        )
        warnings = [warning for item in mappings for warning in item.warnings]
        warnings.extend(warning for item in analyses for warning in item.warnings)
        warnings.extend(cohort.warnings)
        return AgentWorkflowResult(
            context=context,
            question_mappings=mappings,
            answer_analyses=analyses,
            cohort_result=cohort,
            status=status,
            warnings=warnings,
        )
```

Export `ExamAnalysisOrchestrator` from `src/agents/__init__.py`.

- [ ] **Step 4: Run orchestrator and agent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/agents -v
```

Expected: all agent tests pass.

- [ ] **Step 5: Commit the orchestrator**

```powershell
git add src/agents/__init__.py src/agents/orchestrator.py tests/agents/test_orchestrator.py
git commit -m "feat: orchestrate current analysis agents"
```

---

### Task 7: Isolate item-level agent failures

**Files:**
- Modify: `src/agents/orchestrator.py`
- Modify: `tests/agents/test_orchestrator.py`

**Interfaces:**
- Consumes: exceptions raised for one question mapping, one student's answer analysis, or cohort aggregation.
- Produces: failed typed results with `question_mapping_failed`, `answer_analysis_failed`, or `cohort_analysis_failed` warnings while unrelated items continue.

- [ ] **Step 1: Write failing isolation tests**

Add these methods to `OrchestratorTests`:

```python
    def test_question_failure_does_not_stop_other_question_parts(self):
        question_agent = Mock()
        answer_agent = Mock()
        cohort_agent = Mock()
        exam = dict(self.exam)
        exam["questions"] = [{
            "question_number": 1,
            "parts": [
                {"part": "a", "question": "First", "max_marks": 5},
                {"part": "b", "question": "Second", "max_marks": 5},
            ],
        }]
        successful = QuestionMappingResult(
            exam_id="DBMS-2025", question_id="1", part_id="b",
            question_text="Second", max_marks=5, topic_ids=["Q1b"],
            mapping_confidence=0.5, status=AgentStatus.PARTIAL,
        )
        question_agent.run.side_effect = [RuntimeError("mapping failed"), successful]
        answer_agent.run.return_value = []
        cohort_agent.run.return_value = CohortPredictionResult(
            exam_id="DBMS-2025", status=AgentStatus.PARTIAL,
        )

        result = ExamAnalysisOrchestrator(
            ModelRegistry(), question_agent, answer_agent, cohort_agent,
        ).run(exam, [])

        self.assertEqual(question_agent.run.call_count, 2)
        self.assertEqual(result.question_mappings[0].status, AgentStatus.FAILED)
        self.assertEqual(result.question_mappings[0].warnings[0].code, "question_mapping_failed")
        self.assertEqual(result.question_mappings[1].part_id, "b")

    def test_student_failure_produces_failed_answer_and_continues(self):
        question_agent = Mock()
        answer_agent = Mock()
        cohort_agent = Mock()
        question_agent.run.return_value = QuestionMappingResult(
            exam_id="DBMS-2025", question_id="1", part_id="a",
            question_text="Explain normalization", max_marks=10,
            topic_ids=["Normalization"], mapping_confidence=0.8,
        )
        answer_agent.run.side_effect = [RuntimeError("analysis failed"), []]
        cohort_agent.run.return_value = CohortPredictionResult(
            exam_id="DBMS-2025", status=AgentStatus.PARTIAL,
        )

        result = ExamAnalysisOrchestrator(
            ModelRegistry(), question_agent, answer_agent, cohort_agent,
        ).run(self.exam, [self.students[0], dict(self.students[0])])

        self.assertEqual(answer_agent.run.call_count, 2)
        self.assertEqual(result.answer_analyses[0].status, AgentStatus.FAILED)
        self.assertEqual(result.answer_analyses[0].student_id, "s1")
        self.assertEqual(result.answer_analyses[0].warnings[0].code, "answer_analysis_failed")
```

- [ ] **Step 2: Run the isolation tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_orchestrator -v
```

Expected: the first raised exception aborts the workflow, so the new tests fail.

- [ ] **Step 3: Add failed-result factories**

Add `AgentWarning`, `AnswerAnalysisResult`, `CohortPredictionResult`, and `QuestionMappingResult` to the imports from `src.agents.contracts`, then add these methods to `ExamAnalysisOrchestrator`:

```python
    @staticmethod
    def _failed_mapping(exam_id, question, part, exc):
        question_id = str(question.get("question_number", ""))
        part_id = str(part.get("part", ""))
        return QuestionMappingResult(
            exam_id=exam_id,
            question_id=question_id,
            part_id=part_id,
            question_text=str(part.get("question", "")),
            max_marks=float(part.get("max_marks", 0) or 0),
            topic_ids=[f"Q{question_id}{part_id}"],
            mapping_confidence=0.0,
            status=AgentStatus.FAILED,
            warnings=[AgentWarning(
                code="question_mapping_failed",
                message=str(exc),
                capability="question_mapping",
            )],
        )

    @staticmethod
    def _failed_answers(exam_data, student, mapping_index, exc):
        warning = AgentWarning(
            code="answer_analysis_failed",
            message=str(exc),
            capability="answer_analysis",
        )
        results = []
        for question in student.get("answers", []):
            question_id = str(question.get("question_number", ""))
            for part in question.get("parts", []):
                part_id = str(part.get("part", ""))
                mapping = mapping_index.get((question_id, part_id))
                max_marks = float(part.get("max_marks", 1) or 1)
                marks = max(0.0, float(part.get("score", 0) or 0))
                topic = (
                    mapping.topic_ids[0]
                    if mapping and mapping.topic_ids
                    else f"Q{question_id}{part_id}"
                )
                results.append(AnswerAnalysisResult(
                    student_id=str(student.get("student_id", "UNKNOWN")),
                    exam=str(exam_data.get("exam", "EXAM")).replace(" ", "_"),
                    year=str(student.get("year", exam_data.get("year", "UNKNOWN"))),
                    question_id=question_id,
                    part_id=part_id,
                    topic=topic,
                    marks_obtained=marks,
                    max_marks=max_marks,
                    performance_score=min(marks / max_marks, 1.0),
                    concept_score=0.0,
                    cognitive_score=0.0,
                    learning_score=0.0,
                    concept_reference_source="unavailable",
                    student_level="unknown",
                    required_level="unknown",
                    analysis_confidence=0.0,
                    status=AgentStatus.FAILED,
                    warnings=[warning],
                ))
        return results
```

- [ ] **Step 4: Isolate each agent call**

Use these exact exception boundaries inside `run()`:

```python
                try:
                    mapping = self.question_agent.run(
                        exam_id, exam_data, question, part, criteria,
                    )
                except Exception as exc:
                    mapping = self._failed_mapping(exam_id, question, part, exc)
```

```python
        for student in students:
            try:
                analyses.extend(self.answer_agent.run(
                    exam_data, student, model_answers, mapping_index, **weight_options,
                ))
            except Exception as exc:
                analyses.extend(self._failed_answers(
                    exam_data, student, mapping_index, exc,
                ))
```

```python
        try:
            cohort = self.cohort_agent.run(
                exam_id, exam_data, analyses, **threshold_options,
            )
        except Exception as exc:
            cohort = CohortPredictionResult(
                exam_id=exam_id,
                status=AgentStatus.FAILED,
                warnings=[AgentWarning(
                    code="cohort_analysis_failed",
                    message=str(exc),
                    capability="cohort_analysis",
                )],
            )
```

- [ ] **Step 5: Run all orchestrator tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_orchestrator -v
```

Expected: all orchestrator tests pass, including both isolation cases.

- [ ] **Step 6: Commit failure isolation**

```powershell
git add src/agents/orchestrator.py tests/agents/test_orchestrator.py
git commit -m "feat: isolate agent workflow item failures"
```

---

### Task 8: Expose the workflow through FastAPI

**Files:**
- Create: `src/api/routers/agent_workflows.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/test_agent_workflows.py`
- Modify: `src/api/dependencies.py`
- Modify: `src/api/schemas/requests.py`
- Modify: `src/api/schemas/responses.py`
- Modify: `src/api/app.py`

**Interfaces:**
- Consumes: `POST /agent-workflows/analyze-exam` with `year`, optional rubric criteria, weak thresholds, and learning-score weights.
- Produces: `AgentWorkflowAnalyzeExamResponse(result: AgentWorkflowResult)`.

- [ ] **Step 1: Write failing HTTP-adapter tests**

```python
# tests/api/test_agent_workflows.py
import unittest
from unittest.mock import Mock, patch

from src.agents.contracts import (
    AgentRunContext,
    AgentStatus,
    AgentWorkflowResult,
    CohortPredictionResult,
)
from src.api.routers.agent_workflows import analyze_exam_agent_workflow
from src.api.schemas.requests import AgentWorkflowAnalyzeExamRequest


class AgentWorkflowRouterTests(unittest.TestCase):
    @patch("src.api.routers.agent_workflows.get_model_answer", return_value={})
    @patch("src.api.routers.agent_workflows.get_student_answers", return_value=[])
    @patch("src.api.routers.agent_workflows.get_exam_data", return_value={"exam": "DBMS", "year": 2025, "questions": []})
    @patch("src.api.routers.agent_workflows.get_agent_orchestrator")
    def test_route_loads_year_data_and_returns_workflow_result(
        self, orchestrator_dependency, exam_dependency,
        answers_dependency, model_answer_dependency,
    ):
        expected = AgentWorkflowResult(
            context=AgentRunContext(
                run_id="run-1", input_hash="abc", exam_id="DBMS-2025",
                started_at="2025-01-01T00:00:00Z",
            ),
            question_mappings=[], answer_analyses=[],
            cohort_result=CohortPredictionResult(
                exam_id="DBMS-2025", status=AgentStatus.PARTIAL,
            ),
            status=AgentStatus.PARTIAL,
        )
        orchestrator = Mock()
        orchestrator.run.return_value = expected
        orchestrator_dependency.return_value = orchestrator

        response = analyze_exam_agent_workflow(
            AgentWorkflowAnalyzeExamRequest(year=2025)
        )

        self.assertEqual(response.result.context.run_id, "run-1")
        exam_dependency.assert_called_once_with(2025)
        answers_dependency.assert_called_once_with(2025)
        model_answer_dependency.assert_called_once_with(2025)
        orchestrator.run.assert_called_once()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the API test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.api.test_agent_workflows -v
```

Expected: import failure for `src.api.routers.agent_workflows`.

- [ ] **Step 3: Add request and response schemas**

```python
# append to src/api/schemas/requests.py
from pydantic import model_validator


class AgentWorkflowAnalyzeExamRequest(BaseModel):
    year: int = Field(ge=2021, le=2025)
    rubric: dict[str, list[str]] = Field(default_factory=dict)
    weak_threshold: float = Field(0.5, ge=0, le=1)
    weak_min_students: int = Field(2, ge=1)
    weak_min_below_share: float = Field(0.4, ge=0, le=1)
    performance_weight: float = Field(0.6, ge=0, le=1)
    concept_weight: float = Field(0.25, ge=0, le=1)
    cognitive_weight: float = Field(0.15, ge=0, le=1)

    @model_validator(mode="after")
    def validate_learning_score_weights(self):
        total = (
            self.performance_weight
            + self.concept_weight
            + self.cognitive_weight
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("learning-score weights must sum to 1.0")
        return self
```

```python
# append to src/api/schemas/responses.py
from src.agents.contracts import AgentWorkflowResult


class AgentWorkflowAnalyzeExamResponse(BaseModel):
    result: AgentWorkflowResult
```

- [ ] **Step 4: Add cached registry and orchestrator dependencies**

```python
# append to src/api/dependencies.py
@lru_cache(maxsize=1)
def get_cognitive_bloom_model():
    from src.analysis.scoring.cognitive_bloom_model import CognitiveBloomModel
    return CognitiveBloomModel(model_path=settings.cognitive_bloom_model_path)


@lru_cache(maxsize=1)
def get_model_registry():
    from src.agents.model_registry import ModelRegistry

    registry = ModelRegistry()
    registry.register("similarity", "exam-similarity-local-v1", get_similarity_model)
    registry.register("weak_topic", "weak-topic-local-v1", get_weak_topic_model)
    registry.register("cognitive_bloom", "cognitive-bloom-local-v1", get_cognitive_bloom_model)
    return registry


@lru_cache(maxsize=1)
def get_agent_orchestrator():
    from src.agents.orchestrator import ExamAnalysisOrchestrator
    return ExamAnalysisOrchestrator.with_defaults(get_model_registry())
```

- [ ] **Step 5: Implement and register the workflow router**

```python
# src/api/routers/agent_workflows.py
import logging

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import (
    get_agent_orchestrator,
    get_exam_data,
    get_model_answer,
    get_student_answers,
)
from src.api.schemas.requests import AgentWorkflowAnalyzeExamRequest
from src.api.schemas.responses import AgentWorkflowAnalyzeExamResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent-workflows", tags=["Agent Workflows"])


@router.post("/analyze-exam", response_model=AgentWorkflowAnalyzeExamResponse)
def analyze_exam_agent_workflow(req: AgentWorkflowAnalyzeExamRequest):
    try:
        exam_data = get_exam_data(req.year)
        students = get_student_answers(req.year)
        model_answers = get_model_answer(req.year)
        result = get_agent_orchestrator().run(
            exam_data,
            students,
            model_answers,
            req.rubric,
            weak_threshold=req.weak_threshold,
            weak_min_students=req.weak_min_students,
            weak_min_below_share=req.weak_min_below_share,
            performance_weight=req.performance_weight,
            concept_weight=req.concept_weight,
            cognitive_weight=req.cognitive_weight,
        )
        return AgentWorkflowAnalyzeExamResponse(result=result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent workflow failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
```

Import `agent_workflows` in `src/api/app.py`, call `app.include_router(agent_workflows.router)` after the existing routers, and add “Orchestrate typed question, answer, and cohort agents” to the API description.

- [ ] **Step 6: Run API and full agent tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.api.test_agent_workflows -v
.\.venv\Scripts\python.exe -m unittest discover -s tests/agents -v
```

Expected: all API and agent tests pass.

- [ ] **Step 7: Commit the API integration**

```powershell
git add src/api/app.py src/api/dependencies.py src/api/routers/agent_workflows.py src/api/schemas/requests.py src/api/schemas/responses.py tests/api/__init__.py tests/api/test_agent_workflows.py
git commit -m "feat: expose agent exam workflow API"
```

---

### Task 9: Add end-to-end regression coverage and documentation

**Files:**
- Create: `tests/agents/test_workflow_integration.py`
- Modify: `IMPLEMENTATION.md`

**Interfaces:**
- Consumes: the real Phase 1 agents with the existing scoring functions patched only at the heavyweight cognitive-model boundary.
- Produces: regression evidence that one exam flows through all three agents, mappings are reused, existing marks are preserved, and forecast probabilities remain absent.

- [ ] **Step 1: Write the end-to-end integration test**

```python
# tests/agents/test_workflow_integration.py
import unittest
from unittest.mock import patch

from src.agents.contracts import AgentStatus
from src.agents.model_registry import ModelRegistry
from src.agents.orchestrator import ExamAnalysisOrchestrator


class AgentWorkflowIntegrationTests(unittest.TestCase):
    @patch("src.analysis.exam_analysis.cognitive_score")
    def test_current_exam_flows_through_all_agents(self, cognitive_mock):
        cognitive_mock.return_value = {
            "cognitive_score": 0.8,
            "student_level": "understand",
            "required_level": "understand",
        }
        exam = {
            "exam": "DBMS", "year": 2025,
            "questions": [{
                "question_number": 1, "topic": "Normalization",
                "parts": [{
                    "part": "a", "question": "Explain normalization",
                    "max_marks": 10,
                }],
            }],
        }
        students = [
            {"student_id": "s1", "year": 2025, "answers": [{
                "question_number": 1,
                "parts": [{"part": "a", "answer": "reduces redundancy", "score": 8, "max_marks": 10}],
            }]},
            {"student_id": "s2", "year": 2025, "answers": [{
                "question_number": 1,
                "parts": [{"part": "a", "answer": "unrelated", "score": 2, "max_marks": 10}],
            }]},
        ]
        model_answers = {"1": {"a": "Normalization reduces redundancy"}}
        registry = ModelRegistry()
        registry.register("similarity", "v1", lambda: object())

        result = ExamAnalysisOrchestrator.with_defaults(registry).run(
            exam, students, model_answers,
        )

        self.assertEqual(len(result.question_mappings), 1)
        self.assertEqual(len(result.answer_analyses), 2)
        self.assertEqual(result.answer_analyses[0].marks_obtained, 8.0)
        self.assertEqual(result.answer_analyses[1].marks_obtained, 2.0)
        self.assertTrue(result.cohort_result.question_summaries)
        self.assertEqual(result.cohort_result.future_topic_probabilities, [])
        self.assertEqual(result.status, AgentStatus.PARTIAL)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the integration test**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.agents.test_workflow_integration -v
```

Expected: one integration test passes.

- [ ] **Step 3: Document the Phase 1 architecture and endpoint**

Add these facts to `IMPLEMENTATION.md`:

- The three agent classes wrap existing deterministic services.
- The orchestrator executes question mapping, per-student answer analysis, and cohort analysis in order.
- `POST /agent-workflows/analyze-exam` is the new workflow endpoint.
- `partial` is the expected Phase 1 status because retrieval, misconception extraction, and forecasting are explicit capability gaps.
- `historical_trends` is descriptive and `future_topic_probabilities` remains empty.
- The original `/grade`, `/analyze/exam`, and `/predict/*` endpoints remain supported.

- [ ] **Step 4: Run all regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: every test passes with no failures or errors.

- [ ] **Step 5: Run the existing demonstration scripts**

Run:

```powershell
.\.venv\Scripts\python.exe examples\test_predictions_trends.py
.\.venv\Scripts\python.exe examples\test_all_years.py
```

Expected: both scripts exit with code 0 and retain their current topic-matching and descriptive-trend behavior.

- [ ] **Step 6: Verify the API imports without loading heavy models**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from src.api.app import app; print(sorted(route.path for route in app.routes if 'agent-workflows' in route.path))"
```

Expected:

```text
['/agent-workflows/analyze-exam']
```

- [ ] **Step 7: Commit integration coverage and documentation**

```powershell
git add tests/agents/test_workflow_integration.py IMPLEMENTATION.md
git commit -m "test: verify agent workflow integration"
```

## Completion checklist

- [ ] All Phase 1 commits are present and limited to the files named in their tasks.
- [ ] `git status --short` is clean.
- [ ] The full `unittest` suite passes.
- [ ] Both existing demonstration scripts exit successfully.
- [ ] The application exposes `/agent-workflows/analyze-exam`.
- [ ] No test or response contains a non-empty `future_topic_probabilities` list.
- [ ] No agent writes to the filesystem or loads a registered model merely to report its version.
- [ ] The implementation is reviewed against `docs/superpowers/specs/2026-08-02-agent-workflow-architecture-design.md`.

