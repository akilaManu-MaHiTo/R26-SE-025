import asyncio
import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.analytics.student_document import performance_status
from app.api.deps import get_db
from app.db.repository import (
    find_exam_analytics,
    find_graded_submissions_for_exam,
    find_student_analytics,
    list_all_exams,
)
from app.schemas.exam_analytics import ExamAnalyticsDocument
from app.llm.ollama import check_llm_detailed_health
from app.services.exam_analytics import ExamNotFound, compute_exam_analytics
from app.services.recommendation import recommend_for_weak_areas
from app.services.student_accounts import provision_student_accounts
from app.services.teaching_actions import get_teaching_actions
from app.services.topic_canonicalization import canonicalize_topics

router = APIRouter(prefix="/lecturers", tags=["lecturers"])


@router.get("/llm-health")
async def llm_health():
    """Real LLM health: ollama reachable + model pulled. Used by question-exam Model online banner."""
    return await check_llm_detailed_health()


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
    try:
        document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
        if document is None:
            try:
                document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
            except ExamNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute analytics: {exc}") from exc
    # Provision student accounts for all graded submissions of this exam (best-effort)
    try:
        await provision_student_accounts(db, course_code, session_name, year, month, semester)
    except Exception:
        pass
    try:
        canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
        document.update(canonical)
    except Exception:
        # canonicalization is best-effort; return base document if it fails
        pass
    try:
        return ExamAnalyticsDocument.model_validate(document)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics document validation failed: {exc}") from exc


@router.get("/exams/{course_code}/{session_name}/analytics/stream")
async def lecturer_exam_analytics_stream(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    """SSE stream for real-time analyze — PULSE·AI says what it's doing (Bloom, topic)."""
    async def event_generator():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # Fast path: cached
        cached = await find_exam_analytics(db, course_code, session_name, year, month, semester)
        if cached is not None:
            yield sse("progress", {"phase": "cached", "message": "PULSE·AI — Using cached analytics"})
            try:
                await provision_student_accounts(db, course_code, session_name, year, month, semester)
            except Exception:
                pass
            try:
                canonical = await canonicalize_topics(db, cached, course_code, session_name, year, month, semester)
                cached.update(canonical)
            except Exception:
                pass
            yield sse("result", cached)
            return

        queue: asyncio.Queue[str] = asyncio.Queue()

        def progress_cb(msg: str):
            try:
                queue.put_nowait(msg)
            except Exception:
                pass

        # Run compute in background task
        compute_task = asyncio.create_task(
            compute_exam_analytics(db, course_code, session_name, year, month, semester, progress_callback=progress_cb)
        )

        # Stream progress while compute runs
        while not compute_task.done():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.3)
                yield sse("progress", {"phase": "analyzing", "message": msg})
            except asyncio.TimeoutError:
                # keep connection alive
                yield sse("ping", {"message": "alive"})
            except Exception:
                break

        # Drain remaining queue
        while not queue.empty():
            try:
                msg = queue.get_nowait()
                yield sse("progress", {"phase": "analyzing", "message": msg})
            except Exception:
                break

        try:
            document = await compute_task
        except ExamNotFound as exc:
            yield sse("error", {"detail": str(exc)})
            return
        except Exception as exc:
            yield sse("error", {"detail": f"Failed to compute analytics: {exc}"})
            return

        # Post-processing
        yield sse("progress", {"phase": "finalizing", "message": "PULSE·AI — Provisioning student accounts & canonicalizing topics..."})
        try:
            await provision_student_accounts(db, course_code, session_name, year, month, semester)
        except Exception:
            pass
        try:
            canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
            document.update(canonical)
        except Exception:
            pass

        yield sse("result", document)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/exams/{course_code}/{session_name}/students")
async def lecturer_student_list(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    submissions = await find_graded_submissions_for_exam(
        db, course_code, session_name, year, month, semester
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
            db, student_id, course_code, session_name, year, month, semester
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


@router.get("/exams/{course_code}/{session_name}/student/{student_id}")
async def lecturer_student_detail(
    course_code: str,
    session_name: str,
    student_id: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    include_ai_tips: bool = Query(False, description="When false, strip AI improvement tips (recommendations, next_question_strategy, learning_gaps)"),
    db=Depends(get_db),
):
    """Lecturer view of a single student's performance — excludes AI improvement tips by default.

    Returns the StudentAnalyticsDocument minus `recommendations`, `next_question_strategy`,
    and `learning_analysis.learning_gaps` so lecturers see raw performance only.
    Pass `include_ai_tips=true` to get the full document (student-equivalent).
    """
    doc = await find_student_analytics(db, student_id, course_code, session_name, year, month, semester)
    if doc is None:
        # No cached analytics — try to explain why (no submission vs not yet analyzed)
        from app.db.repository import find_graded_submission

        sub = await find_graded_submission(db, student_id, course_code, session_name, year, month, semester)
        if sub is None:
            raise HTTPException(status_code=404, detail=f"no graded submission for student {student_id} in {course_code} {session_name}")
        raise HTTPException(status_code=423, detail=f"analytics not yet generated for student {student_id} — ensure exam is analyzed")
    if not include_ai_tips:
        # Strip AI improvement tips — keep only raw performance
        filtered = dict(doc)
        filtered.pop("recommendations", None)
        filtered.pop("next_question_strategy", None)
        # Also strip AI-generated learning_gaps but keep weak/strong categorization
        la = filtered.get("learning_analysis")
        if isinstance(la, dict):
            la_copy = dict(la)
            la_copy.pop("learning_gaps", None)
            # Ensure at least an empty list so frontend doesn't break
            la_copy["learning_gaps"] = []
            filtered["learning_analysis"] = la_copy
        return filtered
    return doc


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


class ExamDraftPaper(BaseModel):
    exam: str = Field(min_length=1)
    year: int
    questions: list[dict] = Field(default_factory=list)


class ExamDraftCreate(BaseModel):
    draft_id: str | None = None
    subject_code: str = Field(min_length=1)
    subject_name: str | None = None
    paper: ExamDraftPaper


@router.post("/exams/drafts")
async def create_exam_draft(payload: ExamDraftCreate, db=Depends(get_db)):
    """Upload paper to cloud (Mongo exam_drafts) - accessible again via list/get."""
    from app.db.repository import upsert_exam_draft

    draft_id = payload.draft_id or f"draft_{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "draft_id": draft_id,
        "subject_code": payload.subject_code,
        "subject_name": payload.subject_name or payload.subject_code,
        "paper": payload.paper.model_dump(),
        "total_marks": sum(sum(p.get("max_marks", 0) for p in q.get("parts", [])) for q in payload.paper.questions),
        "question_count": len(payload.paper.questions),
        "created_at": now,
        "updated_at": now,
    }
    # preserve created_at if update
    existing = await db["exam_drafts"].find_one({"draft_id": draft_id}, {"created_at": 1})
    if existing and existing.get("created_at"):
        doc["created_at"] = existing["created_at"]
    await upsert_exam_draft(db, doc)
    return doc


@router.get("/exams/drafts")
async def list_exam_drafts(course_code: str | None = Query(None), db=Depends(get_db)):
    from app.db.repository import list_exam_drafts

    return await list_exam_drafts(db, course_code)


@router.get("/exams/drafts/{draft_id}")
async def get_exam_draft(draft_id: str, db=Depends(get_db)):
    from app.db.repository import find_exam_draft

    doc = await find_exam_draft(db, draft_id)
    if not doc:
        raise HTTPException(status_code=404, detail="draft not found")
    return doc


@router.delete("/exams/drafts/{draft_id}")
async def remove_exam_draft(draft_id: str, db=Depends(get_db)):
    from app.db.repository import delete_exam_draft

    ok = await delete_exam_draft(db, draft_id)
    if not ok:
        raise HTTPException(status_code=404, detail="draft not found")
    return {"deleted": True, "draft_id": draft_id}


@router.get("/question-bank")
async def question_bank(
    source_type: str | None = Query(None, description="lecture|tutorial|exam"),
    year: int | None = Query(None),
    canonical_topic: str | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
):
    """Browse question bank - filter by source/year/topic for ExamCreator right panel."""
    import json
    import pathlib

    bank_path = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "question_bank.json"
    if not bank_path.exists():
        return []
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    filtered = bank
    if source_type:
        filtered = [r for r in filtered if r.get("source_type") == source_type]
    if year:
        filtered = [r for r in filtered if r.get("year") == year]
    if canonical_topic:
        filtered = [r for r in filtered if r.get("canonical_topic") == canonical_topic]
    # exam questions sorted by year desc, tutorials by topic
    filtered.sort(key=lambda r: (r.get("year", 0), r.get("question_id")), reverse=True)
    return filtered[:limit]


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
    try:
        document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
        if document is None:
            try:
                document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
            except ExamNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute analytics: {exc}") from exc
    # enrich with canonical if missing
    if not document.get("canonical_topic_performance"):
        try:
            canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
            document.update(canonical)
        except Exception:
            pass
    try:
        result = recommend_for_weak_areas(document, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to generate recommendations: {exc}") from exc
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
