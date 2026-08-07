from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.schemas.catalog import CriteriaEvidence


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CellMetrics(BaseModel):
    topic: str
    bloom_level: str
    mastery: float | None = None
    mean: float | None = None
    median: float | None = None
    pass_rate: float | None = None
    failure_rate: float | None = None
    student_count: int = 0
    attempt_count: int = 0
    std_dev: float | None = None
    missed_criterion_rate: float | None = None
    evidence_status: str = "insufficient_evidence"


class TopicMetrics(BaseModel):
    topic: str
    mastery: float | None = None
    mean: float | None = None
    student_count: int = 0
    attempt_count: int = 0
    evidence_status: str = "insufficient_evidence"


class AnalyticsSnapshot(BaseModel):
    snapshot_id: str
    run_id: str
    course_code: str
    exam_id: str
    algorithm_version: str
    cohort_metrics: dict[str, float | int | dict]
    topic_metrics: list[TopicMetrics]
    topic_bloom_matrix: list[CellMetrics]
    evidence_statuses: dict[str, str]
    grade_distribution: dict[str, int]
    record_counts: dict[str, int]
    pass_threshold: float
    min_students: int
    min_attempts: int
    published_at: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)


class CandidateQuestion(BaseModel):
    candidate_id: str
    question_text: str
    topic: str
    bloom_level: str
    marks: float = Field(gt=0)
    bloom_rationale: str = ""
    model_answer: str = ""
    rubric_criteria: list[CriteriaEvidence] = Field(default_factory=list)
    similarity_check: dict = Field(default_factory=dict)
    decision: str = "pending"


class ExamRecommendation(BaseModel):
    recommendation_id: str
    run_id: str
    course_code: str
    exam_id: str
    topic: str
    bloom_level: str
    question_type: str
    mark_range: tuple[float, float]
    priority_score: float = Field(ge=0.0, le=1.0)
    component_breakdown: dict[str, float | None]
    evidence: dict = Field(default_factory=dict)
    candidates: list[CandidateQuestion] = Field(default_factory=list)
    decision: str = "pending"
    created_at: datetime = Field(default_factory=utcnow)


class AnalysisRun(BaseModel):
    run_id: str
    course_code: str
    exam_id: str
    status: str = "queued"
    input_filters: dict = Field(default_factory=dict)
    data_counts: dict = Field(default_factory=dict)
    algorithm_version: str = "analytics-v1"
    model_version: str | None = None
    embedding_model: str | None = None
    quantization: str | None = None
    prompt_version: str | None = None
    thresholds: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    checkpoints: dict = Field(default_factory=dict)
    errors: list[dict] = Field(default_factory=list)
    publication_state: str = "unpublished"