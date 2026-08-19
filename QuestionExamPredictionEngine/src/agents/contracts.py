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
    bloom_confidence: float | None = Field(default=None, ge=0, le=1)
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
