"""Research-grade label schema for Weakness-Aligned Question Usefulness (lecturer study).

Task: Given analytics snapshot A (weakness_vector, bloom_performance) + lecture signals L,
rate each candidate question q (retrieved from question_bank or LLM-generated) for
usefulness to the current cohort.

Use with app/evaluation/metrics.py::write_usefulness_labeling_template
and evaluation: NDCG@k / Precision@k on `would_use`, mean rating_overall, cohen_kappa.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS

Rating1to5 = Literal[1, 2, 3, 4, 5]


class UsefulnessLabel(BaseModel):
    """One judgment: lecturer rates one candidate question in one analytics context."""

    # linkage
    question_id: str = Field(min_length=1, description="question_bank question_id or generated id")
    question_text: str = Field(min_length=1)
    canonical_topic: str = Field(description=f"one of {TOPICS}")
    bloom_level: str = Field(description=f"one of {BLOOM_LEVELS}")
    analytics_snapshot_id: str = Field(
        min_length=1, description="e.g. IT2040@Final2023 or exam_analytics _id"
    )
    weakness_context: dict[str, float] = Field(
        default_factory=dict,
        description="{canonical_topic: weakness 0..1} snapshot from Phase 3 weakness_for_document",
    )

    # signals shown to rater (for audit, not scored)
    recommendation_score: float | None = Field(default=None, ge=0, le=1)
    priority: str | None = None
    lecture_coverage: float | None = Field(default=None, ge=0, le=1)
    tutorial_evidence: float | None = Field(default=None, ge=0, le=1)
    exam_relevance: float | None = Field(default=None, ge=0, le=1)
    bloom_gap: float | None = Field(default=None, ge=0, le=1)

    # ratings - core research labels
    rating_overall: Rating1to5 = Field(description="1=useless 5=highly useful for this cohort now")
    rating_weakness_fit: Rating1to5 = Field(description="targets current weak topic/bloom?")
    rating_curriculum_fit: Rating1to5 = Field(description="aligned to lecture coverage & learning outcome?")
    rating_difficulty_fit: Rating1to5 = Field(description="appropriate difficulty for cohort?")
    rating_clarity: Rating1to5 = Field(description="wording clear, assessable, no ambiguity?")

    # binary decision for Precision@k / NDCG
    would_use: bool = Field(description="would you use this question in next quiz/exam?")
    would_edit: bool = Field(default=False, description="would use after minor edit?")

    # rater meta
    annotator_id: str = Field(min_length=1)
    annotated_at: datetime | None = None
    time_spent_seconds: int | None = Field(default=None, ge=0)
    comments: str = Field(default="")

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "UsefulnessLabel":
        if self.canonical_topic not in TOPICS:
            raise ValueError(f"canonical_topic must be one of {TOPICS}")
        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level must be one of {BLOOM_LEVELS}")
        for t, w in self.weakness_context.items():
            if t not in TOPICS:
                raise ValueError(f"unknown topic in weakness_context: {t}")
            if not 0 <= w <= 1:
                raise ValueError(f"weakness for {t} must be 0..1, got {w}")
        return self


class UsefulnessLabelBatch(BaseModel):
    """Container for CSV/JSONL export - one rater, one snapshot, k candidates."""

    analytics_snapshot_id: str
    annotator_id: str
    created_at: datetime | None = None
    labels: list[UsefulnessLabel] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_ids(self) -> "UsefulnessLabelBatch":
        for lab in self.labels:
            if lab.analytics_snapshot_id != self.analytics_snapshot_id:
                raise ValueError("all labels must share analytics_snapshot_id")
            if lab.annotator_id != self.annotator_id:
                raise ValueError("all labels must share annotator_id")
        return self
