from fastapi import APIRouter, Depends, HTTPException

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
    course_code: str, session_name: str, db=Depends(get_db)
):
    document = await find_exam_analytics(db, course_code, session_name)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
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
