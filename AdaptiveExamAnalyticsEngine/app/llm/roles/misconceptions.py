from typing import Literal

from pydantic import BaseModel, Field


class MisconceptionItem(BaseModel):
    statement: str
    evidence: str
    confidence: Literal["confirmed", "inferred_low_confidence"]


class MisconceptionSummary(BaseModel):
    topic: str
    misconceptions: list[MisconceptionItem] = Field(default_factory=list)
    source_summary: str = ""