from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.schemas.student import StudentDashboard
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_key}/dashboard", response_model=StudentDashboard)
async def student_dashboard(
    student_key: str,
    run_id: str | None = None,
    include_llm: bool = False,
    db=Depends(get_db),
) -> StudentDashboard:
    try:
        return await build_student_dashboard(db, student_key, run_id, include_llm)
    except StudentDashboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))