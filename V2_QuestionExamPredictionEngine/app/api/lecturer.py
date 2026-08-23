from fastapi import APIRouter, Depends, HTTPException, Query

from app.analytics.student_document import performance_status
from app.api.deps import get_db
from app.db.repository import (
    find_exam_analytics,
    find_graded_submissions_for_exam,
    find_student_analytics,
    list_all_exams,
)
from app.schemas.exam_analytics import ExamAnalyticsDocument
from app.services.exam_analytics import ExamNotFound, compute_exam_analytics
from app.services.recommendation import recommend_for_weak_areas
from app.services.teaching_actions import get_teaching_actions
from app.services.topic_canonicalization import canonicalize_topics

router = APIRouter(prefix="/lecturers", tags=["lecturers"])


@router.get("/exams")
async def list_exams(db=Depends(get_db)):
    """List all available exams with basic stats."""
    exams = await list_all_exams(db)
    return exams


@router.get(
    "/exams/{course_code}/{session_name}/analytics",
    response_model=ExamAnalyticsDocument,
)
async def lecturer_exam_analytics(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
    document.update(canonical)
    return ExamAnalyticsDocument.model_validate(document)


@router.get("/exams/{course_code}/{session_name}/students")
async def lecturer_student_list(
    course_code: str, session_name: str, db=Depends(get_db)
):
    submissions = await find_graded_submissions_for_exam(
        db, course_code, session_name
    )
    if not submissions:
        raise HTTPException(status_code=404, detail="no graded submissions for exam")
    rows = []
    for submission in submissions:
        student_id = submission["student_id"]
        evaluation = submission.get("evaluation") or {}
        obtained = evaluation.get("total_score")
        if obtained is None:
            obtained = submission.get("max_marks_paper_total")
        obtained = float(obtained or 0.0)
        maximum = evaluation.get("max_score")
        if maximum is None:
            maximum = submission.get("max_marks_paper_total")
        maximum = float(maximum or 0.0)
        percentage = (obtained / maximum * 100.0) if maximum else 0.0
        cached = await find_student_analytics(
            db, student_id, course_code, session_name
        )
        rows.append(
            {
                "student_id": student_id,
                "score": {
                    "obtained": obtained,
                    "maximum": maximum,
                    "percentage": round(percentage, 2),
                },
                "status": performance_status(percentage),
                "analysis_status": "generated" if cached else "pending",
                "submitted_at": submission.get("processed_at"),
            }
        )
    return rows


@router.get("/exams/{course_code}/{session_name}/teaching-actions")
async def lecturer_teaching_actions(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
    if document is None:
        raise HTTPException(status_code=404, detail="No analytics found")
    return await get_teaching_actions(
        db,
        course_code,
        session_name,
        document.get("canonical_topic_performance", []),
        document.get("question_performance", []),
    )


@router.get("/exams/{course_code}/{session_name}/recommendations")
async def lecturer_recommendations(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    limit: int = Query(10, ge=1, le=50),
    db=Depends(get_db),
):
    """Lecturer dashboard: weak areas + ranked exam question recommendations.

    Uses student analytics (Phase 3 weakness) + curriculum (question_bank, Phase 1)
    + taxonomy (Phase 2) + weighted scoring (Phase 4).
    """
    document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    # enrich with canonical if missing
    if not document.get("canonical_topic_performance"):
        try:
            canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
            document.update(canonical)
        except Exception:
            pass
    result = recommend_for_weak_areas(document, limit=limit)
    return {
        "exam_id": f"{course_code}@{session_name}",
        "subject_code": course_code,
        "session_name": session_name,
        "year": document.get("year"),
        "month": document.get("month"),
        "semester": document.get("semester"),
        "weakness_scores": result["weakness_scores"],
        "ranked_weak_topics": result["ranked_weak_topics"],
        "recommendations": result["recommendations"],
        "high_priority": result["high_priority"],
        "medium_priority": result["medium_priority"],
        "total_candidates": len(result["recommendations"]),
    }
