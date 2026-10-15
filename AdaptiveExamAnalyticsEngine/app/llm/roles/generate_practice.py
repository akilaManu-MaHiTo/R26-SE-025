from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

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


def practice_batch_matches_target(questions: list[dict], target: dict) -> bool:
    try:
        batch = PracticeQuestions(requested_count=target.get("number_of_questions", 0), questions=questions)
    except ValidationError:
        return False
    topics = target.get("recommended_topics") or []
    levels = target.get("recommended_bloom_levels") or []
    if not topics or not levels or len(batch.questions) != batch.requested_count:
        return False
    prompts = {" ".join(question.prompt.casefold().split()) for question in batch.questions}
    return len(prompts) == len(batch.questions) and all(
        question.topic in topics and question.bloom_level in levels
        and question.difficulty == target.get("recommended_difficulty")
        for question in batch.questions
    )
