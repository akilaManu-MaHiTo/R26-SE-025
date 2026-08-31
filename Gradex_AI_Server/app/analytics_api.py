"""Proxy routes for V2_QuestionExamPredictionEngine — spec §2-§14 three-level architecture.

Level 1 (precomputed, lecturer): examAnalytics — class statistics, topic/Bloom/question
performance, attention areas, insights. Generated after submissions are graded.
Level 2 (lazy, student login): studentExamAnalysis — personal performance, gaps,
recommendations, next-question strategy. Generated on first dashboard access, cached.
Level 3 (on-demand): generatedQuestions — personalized practice content via Qwen.
Only generated when student explicitly requests it.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_db
from app.db.repository import (
    find_exam_analytics,
    find_exam_analysis_status,
    find_generated_questions,
    find_graded_submissions_for_exam,
    find_student_analytics,
    upsert_student_exam_result,
)
from app.services.exam_analytics import ExamNotFound, compute_exam_analytics
from app.services.practice_questions import generate_practice_questions
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics
from app.analytics.student_document import performance_status

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/exams")
async def list_exams(db=Depends(get_db)):
    """Return all analyzed exams with their status."""
    cursor = db["analyzedExams"].find({}, {"_id": 0}).sort([("year", -1), ("session_name", 1)])
    exams = await cursor.to_list(length=100)
    return exams


@router.get("/exams/{course_code}/{session_name}/analytics")
async def exam_analytics(course_code: str, session_name: str, db=Depends(get_db)):
    """Return full exam analytics document for a given course and session."""
    document = await find_exam_analytics(db, course_code, session_name)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return document


@router.get("/exams/{course_code}/{session_name}/students")
async def exam_student_list(course_code: str, session_name: str, db=Depends(get_db)):
    """Spec §5 — per-student lightweight summary (studentExamResults view).

    Persisted to studentExamResults collection for fast lecturer list loads;
    each entry mirrors spec's {student_id, exam_id, course, score, status,
    analysis_status, submitted_at}.
    """
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name)
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
        row = {
            "student_id": student_id,
            "exam_id": f"{course_code}@{session_name}",
            "course": {"code": course_code, "name": course_code},
            "subject_code": course_code,
            "session_name": session_name,
            "score": {
                "obtained": obtained,
                "maximum": maximum,
                "percentage": round(percentage, 2),
            },
            "status": performance_status(percentage),
            "analysis_status": "generated" if cached else "pending",
            "submitted_at": submission.get("processed_at"),
        }
        rows.append(row)
        # Best-effort cache into spec collection — never fail the request
        try:
            await upsert_student_exam_result(db, row)
        except Exception:
            pass
    return rows


@router.get("/exams/{course_code}/{session_name}/student/{student_id}")
async def exam_student_detail(
    course_code: str, session_name: str, student_id: str, db=Depends(get_db)
):
    """Return cached studentExamAnalysis if it exists (no generation)."""
    document = await find_student_analytics(db, student_id, course_code, session_name)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"no analytics for student {student_id} in {course_code} {session_name}",
        )
    return document


# ─── Spec §6: Student Login — lazy generation (cache check → generate → save) ──
@router.get("/exams/{course_code}/{session_name}/student/{student_id}/dashboard")
async def student_dashboard_lazy(
    course_code: str, session_name: str, student_id: str, db=Depends(get_db)
):
    """Spec §6 — Student Login Flow.

    1. Check studentExamAnalysis cache.
    2. If hit → return immediately (fast path).
    3. If miss → generate deterministically (scores/topics/Bloom) + Qwen semantic
       insights (with rule fallback), persist to both legacy and spec collections,
       then return.
    Subsequent logins hit step 2 and never recompute.
    """
    try:
        return await ensure_student_analytics(db, student_id, course_code, session_name)
    except StudentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ─── Spec §7 alternative compact path for client convenience ──────────────────
@router.get("/student/{student_id}/dashboard")
async def student_dashboard_compact(
    student_id: str,
    course_code: str = Query(..., description="e.g. IT2040"),
    session_name: str = Query(..., description="e.g. Final Examination 2021"),
    db=Depends(get_db),
):
    try:
        return await ensure_student_analytics(db, student_id, course_code, session_name)
    except StudentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ─── Spec §8 Level 3: on-demand personalized practice questions (Qwen) ───────
@router.post("/exams/{course_code}/{session_name}/student/{student_id}/practice-questions")
async def create_practice_questions(
    course_code: str, session_name: str, student_id: str, db=Depends(get_db)
):
    """Level 3 — only when student explicitly requests practice content."""
    analysis = await ensure_student_analytics(db, student_id, course_code, session_name)
    result = await generate_practice_questions(
        db, student_id, course_code, session_name, analysis.next_question_strategy
    )
    if result["status"] != "ok":
        raise HTTPException(
            status_code=503,
            detail={
                "reason": result.get("reason", "generation_failed"),
                "target": analysis.next_question_strategy.model_dump(),
            },
        )
    return result["document"]


@router.get("/exams/{course_code}/{session_name}/student/{student_id}/practice-questions")
async def get_practice_questions(
    course_code: str,
    session_name: str,
    student_id: str,
    fresh: bool = False,
    db=Depends(get_db),
):
    exam_id = f"{course_code}@{session_name}"
    cached = await find_generated_questions(db, student_id, exam_id)
    if cached is not None and not fresh:
        return cached
    return await create_practice_questions(course_code, session_name, student_id, db)  # type: ignore[arg-type]
