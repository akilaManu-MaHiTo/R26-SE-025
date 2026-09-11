"""Canonical schema for lecturer-facing exam analytics documents."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.student import BloomLevel, PerformanceStatus, RecommendationPriority


class ExamInfo(BaseModel):
    session_name: str = Field(min_length=1)
    total_marks: float = Field(ge=0)
    question_count: int = Field(gt=0)


class ExamStatistics(BaseModel):
    total_students: int = Field(ge=0)
    attempted_students: int = Field(ge=0)
    average_score: float = Field(ge=0)
    average_percentage: float = Field(ge=0, le=100)
    pass_rate: float = Field(ge=0, le=100)
    highest_score: float = Field(ge=0)
    lowest_score: float = Field(ge=0)
    median_score: float = Field(ge=0, default=0.0)
    median_percentage: float = Field(ge=0, le=100, default=0.0)
    std_score: float = Field(ge=0, default=0.0)
    std_percentage: float = Field(ge=0, default=0.0)
    iqr_percentage: float = Field(ge=0, default=0.0)
    grade_distribution: dict[str, int] = Field(default_factory=lambda: {"A":0,"B":0,"C":0,"D":0,"F":0})


class TopicPerformanceSummary(BaseModel):
    topic: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus
    evidence_status: str = Field(default="insufficient_evidence")
    student_count: int = Field(ge=0, default=0)
    attempt_count: int = Field(ge=0, default=0)


class BloomPerformanceSummary(BaseModel):
    level: BloomLevel
    average_percentage: float = Field(ge=0, le=100)


class QuestionPerformanceSummary(BaseModel):
    question_id: str = Field(min_length=1)
    question_no: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    bloom_level: BloomLevel
    average_percentage: float = Field(ge=0, le=100)
    evidence_status: str = Field(default="insufficient_evidence")
    student_count: int = Field(ge=0, default=0)
    attempt_count: int = Field(ge=0, default=0)
    p_value: float = Field(ge=0, le=100, default=0.0)
    discrimination: float = Field(ge=-1, le=1, default=0.0)
    missed_criterion_rate: float | None = Field(default=None, ge=0, le=1)


class TopicBloomCell(BaseModel):
    topic: str = Field(min_length=1)
    bloom_level: BloomLevel
    average_percentage: float = Field(ge=0, le=100)
    student_count: int = Field(ge=0, default=0)
    attempt_count: int = Field(ge=0, default=0)
    evidence_status: str = Field(default="insufficient_evidence")


class AttentionArea(BaseModel):
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    priority: RecommendationPriority


class DiagramCriterionPerformance(BaseModel):
    criterion_id: int
    criterion: str
    max_marks: float = Field(ge=0)
    average_awarded_marks: float = Field(ge=0)
    average_percentage: float = Field(ge=0, le=100)
    pass_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    student_count: int = Field(ge=0)
    fail_rate: float = Field(ge=0, le=1)


class DiagramStudentSummary(BaseModel):
    student_id: str
    score: float
    max_score: float
    percentage: float
    status: str
    criteria: list[dict] = Field(default_factory=list)
    feedback: str = Field(default="")


class DiagramDetectionSummary(BaseModel):
    avg_entity_count: float = 0.0
    avg_relationship_count: float = 0.0
    avg_label_count: float = 0.0
    total_detections: int = 0
    avg_marking_score: float = 0.0


class DiagramWeakestCriterion(BaseModel):
    criterion_id: int
    criterion: str
    fail_rate: float
    fail_count: int


class DiagramAnalysisStatistics(BaseModel):
    total_students: int = Field(ge=0)
    average_score: float = Field(ge=0)
    max_score: float = Field(ge=0)
    average_percentage: float = Field(ge=0, le=100)
    pass_rate: float = Field(ge=0, le=100)
    highest_score: float = Field(ge=0)
    lowest_score: float = Field(ge=0)
    median_percentage: float = 0.0
    std_percentage: float = 0.0


class DiagramAnalysis(BaseModel):
    statistics: DiagramAnalysisStatistics
    criterion_performance: list[DiagramCriterionPerformance] = Field(default_factory=list)
    student_summaries: list[DiagramStudentSummary] = Field(default_factory=list)
    detection_summary: DiagramDetectionSummary | None = None
    weakest_criteria: list[DiagramWeakestCriterion] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)


class CanonicalTopicSummary(BaseModel):
    topic: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus
    priority: RecommendationPriority
    question_count: int = Field(ge=0)
    student_count: int = Field(ge=0)
    contributing_fragments: list[str] = Field(default_factory=list)
    is_estimated: bool = False


class CanonicalAttentionArea(BaseModel):
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    priority: RecommendationPriority
    question_count: int = Field(ge=0)
    student_count: int = Field(ge=0)


class TeachingAction(BaseModel):
    topic: str = Field(min_length=1)
    priority: RecommendationPriority
    performance_percentage: float = Field(ge=0, le=100)
    actions: list[str] = Field(default_factory=list)
    generated_at: datetime


class ExamAnalyticsDocument(BaseModel):
    subject_code: str = Field(min_length=1)
    subject_name: str = Field(min_length=1)
    year: int
    month: int = Field(ge=1, le=12)
    semester: int = Field(ge=1)
    session_name: str = Field(min_length=1)
    exam: ExamInfo
    statistics: ExamStatistics
    topic_performance: list[TopicPerformanceSummary] = Field(default_factory=list)
    bloom_performance: list[BloomPerformanceSummary] = Field(default_factory=list)
    question_performance: list[QuestionPerformanceSummary] = Field(default_factory=list)
    topic_bloom_matrix: list[TopicBloomCell] = Field(default_factory=list)
    attention_areas: list[AttentionArea] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    canonical_topic_performance: list[CanonicalTopicSummary] = Field(default_factory=list)
    canonical_attention_areas: list[CanonicalAttentionArea] = Field(default_factory=list)
    canonical_insights: list[str] = Field(default_factory=list)
    unmapped_topics: list[str] = Field(default_factory=list)
    diagram_analysis: DiagramAnalysis | None = None
    generated_at: datetime
    analytics_version: str = Field(min_length=1)

    # Spec §3 alias fields (course, exam_id) are accepted via extra="allow"
    # and persisted by repository._with_spec_aliases without requiring explicit
    # declarations — keeps exact top-level contract test green while supporting
    # spec's {course:{code,name}, exam_id} shape on wire.
    model_config = {"extra": "allow"}
