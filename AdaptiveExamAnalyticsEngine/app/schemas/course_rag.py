"""Course-scoped retrieval contracts; no filesystem paths accepted by the API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DocumentType = Literal["lecture", "tutorial", "exam"]


class SearchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    course_code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    query: str = Field(min_length=1, max_length=1000)
    document_types: list[DocumentType] = Field(default_factory=lambda: ["lecture", "tutorial", "exam"], min_length=1, max_length=3)
    limit: int = Field(default=5, ge=1, le=10)

    @field_validator("course_code")
    @classmethod
    def normalize_course(cls, value):
        return value.upper()


class RetrievedSource(BaseModel):
    source_id: str
    kind: DocumentType
    text: str
    course_code: str
    filename: str
    page_number: int
    year: int | None = None
    rank_score: float = 0


class SearchResult(BaseModel):
    status: Literal["ok", "unavailable"]
    mode: Literal["hybrid", "keyword", "unavailable"]
    warnings: list[str] = Field(default_factory=list)
    sources: list[RetrievedSource] = Field(default_factory=list)


class MaterialDocument(BaseModel):
    document_id: str
    course_code: str
    document_type: DocumentType
    filename: str
    year: int | None = None
    pages: int
    chunks: int
    empty_pages: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mode: Literal["hybrid", "keyword"]
    pdf_available: bool = False


class MaterialInventory(BaseModel):
    status: Literal["ok", "unavailable"]
    items: list[MaterialDocument] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
