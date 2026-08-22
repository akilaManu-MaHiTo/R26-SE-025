from pydantic import BaseModel, Field


class StudyAction(BaseModel):
    action: str
    topic: str
    rationale: str = ""
    practice_topics: list[str] = Field(default_factory=list)


class StudyActions(BaseModel):
    student_key: str
    actions: list[StudyAction] = Field(default_factory=list)
    bounded_language: bool = True