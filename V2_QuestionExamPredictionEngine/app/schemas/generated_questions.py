"""Canonical schema for generated practice-question documents."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.student import BloomLevel, CourseInfo, QuestionDifficulty


class GeneratedQuestion(BaseModel):
    prompt: str = Field(min_length=1)
    bloom_level: BloomLevel
    topic: str = Field(min_length=1)
    difficulty: QuestionDifficulty
    hints: list[str] = Field(default_factory=list)


class QuestionGenerationRequest(BaseModel):
    recommended_topics: list[str] = Field(default_factory=list)
    recommended_bloom_levels: list[BloomLevel] = Field(default_factory=list)
    recommended_difficulty: QuestionDifficulty
    number_of_questions: Literal[5]


class GeneratedQuestionsDocument(BaseModel):
    student_id: str = Field(min_length=1)
    exam_id: str = Field(min_length=1)
    course: CourseInfo
    request: QuestionGenerationRequest
    questions: list[GeneratedQuestion] = Field(default_factory=list)
    generated_at: datetime
    generation_version: str = Field(min_length=1)