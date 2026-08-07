from pydantic import BaseModel, Field, model_validator

from app.analytics.taxonomy import BLOOM_LEVELS, QUESTION_TYPES, TOPICS


class ClassificationResponse(BaseModel):
    primary_topic: str
    topic_weights: dict[str, float] = Field(description="Weights must sum to 1.0.")
    bloom_level: str
    question_type: str
    key_concepts: list[str] = Field(default_factory=list)
    rationale: str = ""
    review_flag: bool = False

    @model_validator(mode="after")
    def validate_taxonomy(self) -> "ClassificationResponse":
        if self.primary_topic not in TOPICS:
            raise ValueError(f"primary_topic must be one of {TOPICS}")
        for topic in self.topic_weights:
            if topic not in TOPICS:
                raise ValueError(f"unknown topic in topic_weights: {topic}")
        if self.bloom_level not in BLOOM_LEVELS:
            raise ValueError(f"bloom_level must be one of {BLOOM_LEVELS}")
        if self.question_type not in QUESTION_TYPES:
            raise ValueError(f"question_type must be one of {QUESTION_TYPES}")
        if abs(sum(self.topic_weights.values()) - 1.0) > 1e-6:
            raise ValueError("topic_weights must sum to 1.0")
        return self