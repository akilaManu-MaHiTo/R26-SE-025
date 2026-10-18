"""Canonical schema for generated practice-question documents.

Note: services/practice_questions builds a plain dict and calls repository directly;
this Pydantic model is currently not validated at runtime but retained for documentation
and potential future validation. Consider wiring it in practice_questions.py.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.student import BloomLevel, QuestionDifficulty


class CourseInfo(BaseModel):
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)


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