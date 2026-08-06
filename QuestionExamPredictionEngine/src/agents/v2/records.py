from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class RubricCriterion(BaseModel):
    point: str
    marks: float = Field(default=0.0, ge=0)


class CourseRecord(BaseModel):
    course_id: str
    subject_code: str
    name: str = ""
    description: str = ""
    source_collection: str = "courses"
    source_document_id: str = ""


class AssessmentRecord(BaseModel):
    assessment_id: str
    course_id: str = ""
    subject_code: str
    session_name: str = ""
    rubric_id: str = ""
    rubric_filename: str | None = None
    parsed_at: datetime | None = None
    assessment_order: int | None = None


class QuestionRecord(BaseModel):
    question_id: str
    assessment_id: str
    question_no_raw: str
    question_no_normalized: str
    question_text: str
    max_marks: float = Field(default=0.0, ge=0)
    topic_id: str | None = None
    model_answer: str | None = None
    rubric_criteria: list[RubricCriterion] = Field(default_factory=list)
