from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
PerformanceStatus = Literal["Strong", "Developing", "Needs Improvement", "Critical"]
RecommendationPriority = Literal["Critical", "High", "Medium", "Low"]
QuestionDifficulty = Literal["Easy", "Medium", "Hard"]


class OverallPerformance(BaseModel):
    score: float = Field(ge=0)
    maximum: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus

    @model_validator(mode="after")
    def score_does_not_exceed_maximum(self):
        if self.score > self.maximum:
            raise ValueError("score cannot exceed maximum")
        return self


class BloomAnalysis(BaseModel):
    level: BloomLevel
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class Performance(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def score_does_not_exceed_max_score(self):
        if self.score > self.max_score:
            raise ValueError("score cannot exceed max_score")
        return self


class CriterionPerformance(BaseModel):
    criterion: str = Field(min_length=1)
    max_marks: float = Field(gt=0)
    awarded_marks: float = Field(ge=0)
    achieved: bool

    @model_validator(mode="after")
    def awarded_marks_do_not_exceed_max_marks(self):
        if self.awarded_marks > self.max_marks:
            raise ValueError("awarded_marks cannot exceed max_marks")
        return self


class QuestionPerformance(BaseModel):
    question_id: str = Field(min_length=1)
    question_no: str = Field(min_length=1)
    question_text: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    bloom_analysis: BloomAnalysis
    performance: Performance
    criteria_performance: list[CriterionPerformance] = Field(default_factory=list)


class TopicPerformance(BaseModel):
    topic: str = Field(min_length=1)
    questions_attempted: int = Field(ge=0)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)
    status: PerformanceStatus

    @model_validator(mode="after")
    def score_does_not_exceed_max_score(self):
        if self.score > self.max_score:
            raise ValueError("score cannot exceed max_score")
        return self


class BloomPerformance(BaseModel):
    level: BloomLevel
    questions_attempted: int = Field(ge=0)
    average_score: float = Field(ge=0, le=100)
    status: PerformanceStatus


class LearningGap(BaseModel):
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    priority: RecommendationPriority


class LearningAnalysis(BaseModel):
    overall_performance: PerformanceStatus
    strong_topics: list[str] = Field(default_factory=list)
    developing_topics: list[str] = Field(default_factory=list)
    weak_topics: list[str] = Field(default_factory=list)
    critical_topics: list[str] = Field(default_factory=list)
    learning_gaps: list[LearningGap] = Field(default_factory=list)


class Recommendation(BaseModel):
    topic: str = Field(min_length=1)
    priority: RecommendationPriority
    action: str = Field(min_length=1)


class NextQuestionStrategy(BaseModel):
    recommended_topics: list[str] = Field(default_factory=list)
    recommended_bloom_levels: list[BloomLevel] = Field(default_factory=list)
    recommended_difficulty: QuestionDifficulty
    number_of_questions: Literal[5]


class ModelMetadata(BaseModel):
    bloom_model: str = Field(min_length=1)
    bloom_model_type: str = Field(min_length=1)
    grading_source: str = Field(min_length=1)
    rag_context_used: bool


class StudentAnalyticsDocument(BaseModel):
    student_id: str = Field(min_length=1)
    subject_code: str = Field(min_length=1)
    subject_name: str = Field(min_length=1)
    year: int
    month: int = Field(ge=1, le=12)
    semester: int = Field(ge=1)
    session_name: str = Field(min_length=1)
    overall_performance: OverallPerformance
    question_performance: list[QuestionPerformance] = Field(default_factory=list)
    topic_performance: list[TopicPerformance] = Field(default_factory=list)
    bloom_performance: list[BloomPerformance] = Field(default_factory=list)
    learning_analysis: LearningAnalysis
    recommendations: list[Recommendation] = Field(default_factory=list)
    next_question_strategy: NextQuestionStrategy
    model_metadata: ModelMetadata
    generated_at: datetime
    analysis_version: str = Field(min_length=1)
