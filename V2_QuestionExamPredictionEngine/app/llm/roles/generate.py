from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, TOPICS


class CandidateQuestion(BaseModel):
    text: str
    topic: str
    bloom_level: str
    marks: float = Field(gt=0)
    rationale: str = ""
    model_answer: str = ""
    rubric_criteria: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "CandidateQuestion":
        if self.topic not in TOPICS:
            raise ValueError(f"topic must be one of {TOPICS}")
        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level must be one of {BLOOM_LEVELS}")
        return self


class CandidateQuestions(BaseModel):
    target_topic: str
    target_bloom: str
    requested_count: int = Field(ge=1)
    candidates: list[CandidateQuestion] = Field(default_factory=list)