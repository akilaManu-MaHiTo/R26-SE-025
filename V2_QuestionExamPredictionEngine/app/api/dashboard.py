from fastapi import APIRouter, Depends, HTTPException

from pydantic import BaseModel

from app.api.deps import get_db
from app.db.repository import find_generated_questions, find_user_by_email, list_exams_for_student
from app.schemas.student import StudentAnalyticsDocument
from app.services.practice_questions import generate_practice_questions
from app.services.student_accounts import verify_password
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics

router = APIRouter(prefix="/students", tags=["students"])


class StudentLoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def student_login(payload: StudentLoginRequest, db=Depends(get_db)):
    email = payload.email.strip().lower()
    user = await find_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(payload.password, user.get("password_hash") or ""):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"student_id": user["student_id"], "email": user["email"], "role": "student"}


@router.get("/{student_id}/exams")
async def student_exams(student_id: str, db=Depends(get_db)):
    """List exams where this student has a graded submission (for dashboard selector)."""
    exams = await list_exams_for_student(db, student_id)
    return exams


@router.get("/{student_id}/profile")
async def student_profile(student_id: str, db=Depends(get_db)):
    """Lightweight profile for StudentDashboard header (student_id, email, exam count)."""
    from app.db.repository import find_user_by_student_id

    user = await find_user_by_student_id(db, student_id)
    exams = await list_exams_for_student(db, student_id)
    return {
        "student_id": student_id,
        "email": user["email"] if user else f"{student_id.lower()}@my.sliit.lk",
        "exam_count": len(exams),
        "exams": exams,
    }


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
