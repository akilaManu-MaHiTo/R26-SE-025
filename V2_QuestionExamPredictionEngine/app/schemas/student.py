from typing import Literal

from pydantic import BaseModel, Field, model_validator

BloomLevel = Literal["Remember", "Understand", "Apply", "Analyze", "Evaluate", "Create"]
PerformanceStatus = Literal["Strong", "Needs Improvement", "Critical"]
RecommendationPriority = Literal["High", "Medium", "Low"]
QuestionDifficulty = Literal["Easy", "Medium", "Hard"]


class CourseInfo(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


class AssessmentInfo(BaseModel):
    session_name: str = Field(min_length=1)
    rubric_ref: str = Field(min_length=1)
    total_score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    percentage: float = Field(ge=0, le=100)

    @model_validator(mode="after")
    def total_score_does_not_exceed_max_score(self):
        if self.total_score > self.max_score:
            raise ValueError("total_score cannot exceed max_score")
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


class QuestionAnalysis(BaseModel):
    question_no: str
    question: str
    topic: str
    subtopic: str
    bloom_analysis: BloomAnalysis
    performance: Performance
    criteria_performance: list[CriterionPerformance] = Field(default_factory=list)


class TopicPerformance(BaseModel):
    topic: str = Field(min_length=1)
    question_count: int = Field(ge=0)
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
    question_count: int = Field(ge=0)
    average_score: float = Field(ge=0, le=100)
    status: PerformanceStatus


class LearningAnalysis(BaseModel):
    overall_performance: PerformanceStatus
    weak_topics: list[str] = Field(default_factory=list)
    strong_topics: list[str] = Field(default_factory=list)
    weak_bloom_levels: list[BloomLevel] = Field(default_factory=list)
    weak_subtopics: list[str] = Field(default_factory=list)
    learning_gaps: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    priority: RecommendationPriority
    topic: str = Field(min_length=1)
    bloom_level: BloomLevel
    action: str = Field(min_length=1)


class NextQuestionGeneration(BaseModel):
    recommended_bloom_level: BloomLevel
    recommended_difficulty: QuestionDifficulty
    recommended_topics: list[str] = Field(default_factory=list)
    number_of_questions: Literal[5]


class ModelMetadata(BaseModel):
    bloom_model: str = Field(min_length=1)
    bloom_model_type: str = Field(min_length=1)
    grading_source: str = Field(min_length=1)
    rag_context_used: bool


class StudentAnalyticsDocument(BaseModel):
    student_id: str = Field(min_length=1)
    course: CourseInfo
    assessment: AssessmentInfo
    question_analysis: list[QuestionAnalysis] = Field(default_factory=list)
    topic_performance: list[TopicPerformance] = Field(default_factory=list)
    bloom_performance: list[BloomPerformance] = Field(default_factory=list)
    learning_analysis: LearningAnalysis
    recommendations: list[Recommendation] = Field(default_factory=list)
    next_question_generation: NextQuestionGeneration
    model_metadata: ModelMetadata
