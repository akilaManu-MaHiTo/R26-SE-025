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