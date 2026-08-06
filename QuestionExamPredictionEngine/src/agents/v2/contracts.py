from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from src.agents.contracts import AgentWarning, SourceCitation
from src.agents.v2.records import RubricCriterion


class V2AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    REVIEW_REQUIRED = "review_required"


class TopicMapping(BaseModel):
    topic_id: str
    score: float = Field(default=0.0, ge=0, le=1)


class QuestionKnowledgeResult(BaseModel):
    question_id: str
    assessment_id: str
    canonical_topic_ids: list[TopicMapping] = Field(default_factory=list)
    concept_ids: list[str] = Field(default_factory=list)
    rubric_criteria: list[RubricCriterion] = Field(default_factory=list)
    required_bloom_level: str | None = None
    question_type: str | None = None
    difficulty: float = Field(default=3.0, ge=1, le=5)
    source_citations: list[SourceCitation] = Field(default_factory=list)
    mapping_confidence: float = Field(default=0.0, ge=0, le=1)
    status: V2AgentStatus = V2AgentStatus.SUCCESS
    warnings: list[AgentWarning] = Field(default_factory=list)
