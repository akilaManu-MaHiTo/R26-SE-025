from typing import Any, Optional
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: str = "ok"
    api_version: str = "1.0.0"
    models_loaded: dict[str, bool]
    python_version: str


class ModelInfo(BaseModel):
    name: str
    type: str
    path: str
    loaded: bool
    description: str


class ModelsListResponse(BaseModel):
    models: list[ModelInfo]


class GradeResponse(BaseModel):
    similarity: float
    concept_score: float
    marks_obtained: float
    max_marks: float
    percentage: float
    feedback: Optional[str] = None


class GradeBatchResponse(BaseModel):
    results: list[GradeResponse]


class GradeWithFeedbackResponse(GradeResponse):
    feedback: str = ""


class ScoreBreakdown(BaseModel):
    performance_score: float
    concept_score: float
    cognitive_score: float
    student_level: str
    required_level: str
    learning_score: float


class StudentReportRecord(BaseModel):
    student_id: str
    exam: str
    year: str
    question: str
    part: str
    score: float
    max_marks: float
    concept_reference_source: str
    performance_score: float
    concept_score: float
    cognitive_score: float
    student_level: str
    required_level: str
    topic: str
    learning_score: float


class AnalyzeExamResponse(BaseModel):
    exam: str
    year: int
    student_reports: list[StudentReportRecord]
    question_summaries: list[dict]
    student_summaries: list[dict]
    misunderstood_questions: list[dict]
    cognitive_gaps: list[dict]
    weak_topics: list[dict]
    output_dir: str


class TopicPrediction(BaseModel):
    topic: str
    score: float
    matched_terms: list[str]


class PredictTopicsResponse(BaseModel):
    predictions: list[TopicPrediction]


class TrendSummary(BaseModel):
    years: dict[str, dict]
    slope: float
    earliest_year: Optional[str]
    latest_year: Optional[str]
    earliest_avg: Optional[float]
    latest_avg: Optional[float]
    change: float


class AnalyzeTrendsResponse(BaseModel):
    trends: dict[str, TrendSummary]
