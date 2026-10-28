from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from app.api.deps import get_db
from app.db.repository import find_generated_questions, list_exams_for_student
from app.schemas.student import StudentAnalyticsDocument
from app.services.practice_questions import GENERATION_VERSION, generate_practice_questions
from app.llm.roles.generate_practice import practice_batch_matches_target
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics

router = APIRouter(prefix="/students", tags=["students"])


@router.get("/{student_id}/materials")
async def student_materials(student_id: str, db=Depends(get_db)):
    from app.services.course_rag import get_course_rag

    exams = await list_exams_for_student(db, student_id)
    courses = {exam["subject_code"].upper() for exam in exams}
    inventory = await run_in_threadpool(get_course_rag().list_documents)
    # The shared index also contains exam papers, which are not student study resources.
    inventory.items = [item for item in inventory.items
                       if item.course_code in courses and item.document_type in {"lecture", "tutorial"}]
    return inventory


@router.get("/{student_id}/materials/{document_id}/pdf")
async def student_material_pdf(student_id: str, document_id: str, db=Depends(get_db)):
    from app.api.course_rag import download_material

    inventory = await student_materials(student_id, db)
    if inventory.status != "ok":
        raise HTTPException(503, "Study materials are temporarily unavailable. Please try again later.")
    if not any(item.document_id == document_id for item in inventory.items):
        raise HTTPException(404, "Study material not found")
    return await run_in_threadpool(download_material, document_id)


def practice_exam_id(course_code, session_name, year, month, semester):
    key = f"{course_code}@{session_name}"
    return f"{key}@{year}-{month}-{semester}" if any(v is not None for v in (year, month, semester)) else key


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
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
    db=Depends(get_db),
) -> StudentAnalyticsDocument:
    try:
        return await ensure_student_analytics(
            db, student_id, course_code, session_name, year, month, semester
        )
    except StudentNotFound as exc:
        # Use 423 when exam not yet analyzed, 404 when no submission
        msg = str(exc)
        if "Wait for lecture" in msg:
            raise HTTPException(status_code=423, detail=msg) from exc
        raise HTTPException(status_code=404, detail=msg) from exc


@router.post("/{student_id}/practice-questions")
async def create_practice_questions(
    student_id: str, course_code: str, session_name: str, db=Depends(get_db),
    year: int | None = None, month: int | None = None, semester: int | None = None,
):
    analysis = await student_dashboard(student_id, course_code, session_name, year, month, semester, db)
    kwargs = {"exam_id": practice_exam_id(course_code, session_name, year, month, semester)} if any(v is not None for v in (year, month, semester)) else {}
    result = await generate_practice_questions(db, student_id, course_code, session_name, analysis.next_question_strategy, **kwargs)
    if result["status"] != "ok":
        raise HTTPException(
            status_code=503,
            detail={"reason": result.get("reason", "generation_failed"),
                    "target": analysis.next_question_strategy.model_dump()},
        )
    return result["document"]


@router.get("/{student_id}/practice-questions")
async def get_practice_questions(
    student_id: str, course_code: str, session_name: str, fresh: bool = False, db=Depends(get_db),
    year: int | None = None, month: int | None = None, semester: int | None = None,
):
    exam_id = practice_exam_id(course_code, session_name, year, month, semester)
    cached = await find_generated_questions(db, student_id, exam_id)
    if cached is not None and not fresh and cached.get("generation_version") == GENERATION_VERSION:
        analysis = await student_dashboard(student_id, course_code, session_name, year, month, semester, db)
        target = analysis.next_question_strategy.model_dump()
        if cached.get("request") == target and practice_batch_matches_target(cached.get("questions"), target):
            return cached
    if any(v is not None for v in (year, month, semester)):
        return await create_practice_questions(student_id, course_code, session_name, db, year, month, semester)
    return await create_practice_questions(student_id, course_code, session_name, db)
