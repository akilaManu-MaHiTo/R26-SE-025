from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.db.repository import find_generated_questions
from app.schemas.student import StudentAnalyticsDocument
from app.services.practice_questions import generate_practice_questions
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


@router.post("/{student_id}/practice-questions")
async def create_practice_questions(
    student_id: str, course_code: str, session_name: str, db=Depends(get_db)
):
    analysis = await ensure_student_analytics(db, student_id, course_code, session_name)
    result = await generate_practice_questions(db, student_id, course_code, session_name, analysis.next_question_strategy)
    if result["status"] != "ok":
        raise HTTPException(
            status_code=503,
            detail={"reason": result.get("reason", "generation_failed"),
                    "target": analysis.next_question_strategy.model_dump()},
        )
    return result["document"]


@router.get("/{student_id}/practice-questions")
async def get_practice_questions(
    student_id: str, course_code: str, session_name: str, fresh: bool = False, db=Depends(get_db)
):
    exam_id = f"{course_code}@{session_name}"
    cached = await find_generated_questions(db, student_id, exam_id)
    if cached is not None and not fresh:
        return cached
    return await create_practice_questions(student_id, course_code, session_name, db)
