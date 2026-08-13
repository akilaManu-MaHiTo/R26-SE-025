from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.student import BloomLevel, QuestionDifficulty


NonBlankText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class PracticeQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: NonBlankText
    bloom_level: BloomLevel
    topic: NonBlankText
    difficulty: QuestionDifficulty
    hints: list[str] = Field(default_factory=list)


class PracticeQuestions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    requested_count: int = Field(ge=1)
    questions: list[PracticeQuestion] = Field(default_factory=list)
