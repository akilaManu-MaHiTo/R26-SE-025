from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.student import BloomLevel


class QuestionSemantics(BaseModel):
    level: BloomLevel
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class InsightRecommendation(BaseModel):
    priority: Literal["High", "Medium", "Low"]
    topic: str
    bloom_level: BloomLevel
    action: str


class GenerationTarget(BaseModel):
    recommended_bloom_level: BloomLevel
    recommended_difficulty: Literal["Easy", "Medium", "Hard"]
    recommended_topics: list[str]


class StudentInsightResponse(BaseModel):
    learning_gaps: list[str]
    recommendations: list[InsightRecommendation]
    generation_target: GenerationTarget
