"""Canonical schema for lecturer-facing exam analytics documents."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.student import BloomLevel, PerformanceStatus, RecommendationPriority


class ExamCourse(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


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


class TopicPerformanceSummary(BaseModel):
    topic: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus


class BloomPerformanceSummary(BaseModel):
    level: BloomLevel
    average_percentage: float = Field(ge=0, le=100)


class QuestionPerformanceSummary(BaseModel):
    question_id: str = Field(min_length=1)
    question_no: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    bloom_level: BloomLevel
    average_percentage: float = Field(ge=0, le=100)


class AttentionArea(BaseModel):
    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    average_percentage: float = Field(ge=0, le=100)
    priority: RecommendationPriority


class ExamAnalyticsDocument(BaseModel):
    exam_id: str = Field(min_length=1)
    course: ExamCourse
    exam: ExamInfo
    statistics: ExamStatistics
    topic_performance: list[TopicPerformanceSummary] = Field(default_factory=list)
    bloom_performance: list[BloomPerformanceSummary] = Field(default_factory=list)
    question_performance: list[QuestionPerformanceSummary] = Field(default_factory=list)
    attention_areas: list[AttentionArea] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
    generated_at: datetime
    analytics_version: str = Field(min_length=1)
