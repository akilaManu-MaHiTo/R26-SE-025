"""Validated, backwards-compatible exam drafts and creator requests."""
from math import isclose, isfinite
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS

BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]


class Blueprint(BaseModel):
    total_marks: float = Field(default=100, gt=0, le=1000, allow_inf_nan=False)
    duration_minutes: int = Field(default=180, gt=0, le=1440)
    purpose: Literal["final", "revision"] = "final"
    learning_outcomes: str = Field(default="", max_length=5000)
    lecture_notes: str = Field(default="", max_length=20000)
    topic_marks: dict[str, float] = Field(default_factory=dict)
    bloom_percentages: dict[str, float] = Field(default_factory=lambda: {
        "Remember": 10, "Understand": 20, "Apply": 40, "Analyze": 25, "Evaluate": 5, "Create": 0})

    @model_validator(mode="after")
    def validate_targets(self):
        if any(not t.strip() or not isfinite(v) or v < 0 for t, v in self.topic_marks.items()):
            raise ValueError("Topic marks must be finite and non-negative with named topics")
        if sum(self.topic_marks.values()) > self.total_marks + 0.001:
            raise ValueError("Topic targets exceed total marks")
        if any(k not in BLOOM_LEVELS or not isfinite(v) or not 0 <= v <= 100
               for k, v in self.bloom_percentages.items()):
            raise ValueError("Invalid Bloom percentage")
        if not isclose(sum(self.bloom_percentages.values()), 100, abs_tol=0.01):
            raise ValueError("Bloom percentages must total 100")
        return self


class SourceExam(BaseModel):
    session_name: str = Field(min_length=1, max_length=200)
    year: int
    month: int = Field(ge=1, le=12)
    semester: int = Field(ge=1, le=12)


class Feedback(BaseModel):
    question_id: str = Field(min_length=1, max_length=300)
    reason: str = Field(default="", max_length=1000)


class DraftCriterion(BaseModel):
    criterion: str = Field(max_length=2000)
    marks: float = Field(ge=0, le=1000, allow_inf_nan=False)


class DraftSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=300)
    kind: str = Field(max_length=100)
    text: str = Field(max_length=20000)


class DraftPart(BaseModel):
    # Drafts can be incomplete, but malformed metadata must not break paper checks.
    model_config = ConfigDict(extra="allow")
    question: str = Field(default="", max_length=20000)
    part: str = Field(default="", max_length=10)
    question_id: str | None = Field(default=None, max_length=300)
    max_marks: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    bloom_level: str = Field(default="", max_length=50)
    model_answer: str = Field(default="", max_length=20000)
    estimated_minutes: float | None = Field(default=None, ge=0, le=1440, allow_inf_nan=False)
    review_status: Literal["needs_review", "approved"] = "needs_review"
    marking_scheme: list[DraftCriterion] = Field(default_factory=list, max_length=30)
    sources: list[DraftSource] = Field(default_factory=list, max_length=10)


class CreatorPaper(BaseModel):
    exam: str = Field(min_length=1, max_length=300)
    year: int = Field(ge=1900, le=2200)
    # Preserve optional metadata on legacy question parts and lecturer edits.
    questions: list[dict] = Field(default_factory=list, max_length=100)
    blueprint: Blueprint = Field(default_factory=Blueprint)
    source_exam: SourceExam | None = None
    rejected_questions: list[Feedback] = Field(default_factory=list, max_length=1000)

    @model_validator(mode="after")
    def validate_parts(self):
        for question in self.questions:
            if not isinstance(question.get("topic", ""), str):
                raise ValueError("Question topic must be text")
            parts = question.get("parts", [])
            if not isinstance(parts, list) or len(parts) > 26:
                raise ValueError("A question may have at most 26 parts")
            for part in parts:
                if not isinstance(part, dict) or not isinstance(part.get("question", ""), str):
                    raise ValueError("Question part must contain text")
                marks = part.get("max_marks", 0)
                if isinstance(marks, bool) or not isinstance(marks, (int, float)) or not isfinite(marks) or not 0 <= marks <= 1000:
                    raise ValueError("Part marks must be finite and between 0 and 1000")
                DraftPart.model_validate(part)
        return self


class CreatorRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    course_code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    paper: CreatorPaper


class GenerateRequest(CreatorRequest):
    topic: str = Field(min_length=1, max_length=200)
    bloom_level: BloomLevel
    marks: float = Field(gt=0, le=1000, allow_inf_nan=False)
    count: int = Field(default=2, ge=1, le=3)


class MarkCriterion(BaseModel):
    criterion: str = Field(min_length=1, max_length=2000)
    marks: float = Field(gt=0, allow_inf_nan=False)


class GroundedCandidate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=10000)
    topic: str = Field(min_length=1, max_length=200)
    bloom_level: BloomLevel
    marks: float = Field(gt=0, allow_inf_nan=False)
    rationale: str = Field(default="", max_length=2000)
    model_answer: str = Field(min_length=1, max_length=15000)
    marking_scheme: list[MarkCriterion] = Field(min_length=1, max_length=30)
    estimated_minutes: float = Field(gt=0, le=1440, allow_inf_nan=False)
    source_ids: list[str] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def rubric_total(self):
        if not isclose(sum(c.marks for c in self.marking_scheme), self.marks, abs_tol=0.01):
            raise ValueError("Marking scheme must add up to question marks")
        return self


class GroundedCandidates(BaseModel):
    candidates: list[GroundedCandidate] = Field(min_length=1, max_length=3)
