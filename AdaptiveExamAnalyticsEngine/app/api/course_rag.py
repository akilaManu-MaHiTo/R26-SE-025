"""Lecturer-only access to the analytics engine's independent material index."""
from fastapi import APIRouter

from app.schemas.course_rag import SearchRequest, SearchResult
from app.services.course_rag import get_course_rag

router = APIRouter(prefix="/lecturers/materials", tags=["course materials"])


@router.post("/search", response_model=SearchResult)
def search_materials(payload: SearchRequest):
    # A sync route keeps PDF-model/SQLite work off the async event loop.
    return get_course_rag().search(payload)
