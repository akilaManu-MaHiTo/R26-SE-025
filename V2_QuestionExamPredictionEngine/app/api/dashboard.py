from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.schemas.student import StudentAnalyticsDocument
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics

router = APIRouter(prefix="/students", tags=["students"])


@router.get(
    "/{student_id}/dashboard",
    response_model=StudentAnalyticsDocument,
)
async def student_dashboard(
    student_id: str,
    course_code: str,
    session_name: str,
    db=Depends(get_db),
) -> StudentAnalyticsDocument:
    try:
        return await ensure_student_analytics(
            db, student_id, course_code, session_name
        )
    except StudentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
