from typing import Any, Optional
from pydantic import BaseModel, Field


class GradeRequest(BaseModel):
    model_answer: str = Field(..., description="The reference/correct answer")
    student_answer: str = Field(..., description="The student's answer text")
    max_marks: float = Field(1.0, gt=0, description="Maximum marks for this question")
    version: str = Field("v2", pattern="^(v1|v2)$", description="Grading version (v1=basic, v2=enhanced with feedback)")


class GradeBatchItem(BaseModel):
    model_answer: str
    student_answer: str
    max_marks: float = 1.0
    question_number: Optional[str] = None
    part: Optional[str] = None


class GradeBatchRequest(BaseModel):
    items: list[GradeBatchItem]
    version: str = Field("v2", pattern="^(v1|v2)$")


class AnalyzeExamRequest(BaseModel):
    year: int = Field(..., ge=2021, le=2025, description="Exam year")
    weak_threshold: float = Field(0.5, ge=0, le=1)
    weak_min_students: int = Field(2, ge=1)
    weak_min_below_share: float = Field(0.4, ge=0, le=1)


class PredictTopicsRequest(BaseModel):
    answer: str = Field(..., min_length=1, description="Student answer text")
    exam_data: Optional[Any] = Field(None, description="Exam JSON data (string path or dict)")
    top_n: int = Field(3, ge=1, le=20)


class AnalyzeTrendsRequest(BaseModel):
    reports: list[dict] = Field(..., description="List of student report records")
    by: str = Field("topic", pattern="^(topic|question|student_id)$")
    time_key: str = Field("year")
