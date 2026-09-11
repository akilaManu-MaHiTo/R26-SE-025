from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.student import BloomLevel


NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class QuestionSemantics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: BloomLevel
    topic: str = Field(min_length=1)
    subtopic: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class InsightRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: Literal["High", "Medium", "Low"]
    topic: NonBlankText
    bloom_level: BloomLevel
    action: NonBlankText


class GenerationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_bloom_level: BloomLevel
    recommended_difficulty: Literal["Easy", "Medium", "Hard"]
    recommended_topics: list[str]


class StudentInsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    learning_gaps: list[str]
    recommendations: list[InsightRecommendation]
    generation_target: GenerationTarget
