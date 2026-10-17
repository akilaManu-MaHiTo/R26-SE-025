import asyncio
import json
from collections import Counter
from datetime import datetime, timezone
from math import isfinite
from uuid import uuid4

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from app.analytics.student_document import performance_status
from app.api.deps import get_db
from app.db.repository import (
    find_exam_analytics,
    find_graded_submission,
    find_graded_submissions_for_exam,
    find_student_analytics,
    find_diagram_evaluations_for_exam,
    find_diagram_markings_for_exam,
    list_all_exams,
)
from app.schemas.exam_analytics import ExamAnalyticsDocument
from app.schemas.exam_creator import CreatorPaper, CreatorRequest, GenerateRequest
from app.services.exam_creator import course_bank, review_paper, generate_for_paper
from app.llm.ollama import check_llm_detailed_health
from app.services.exam_analytics import ANALYTICS_VERSION, ExamNotFound, compute_exam_analytics
from app.services.recommendation import recommend_for_weak_areas
from app.services.student_dashboard import StudentNotFound, ensure_student_analytics, is_current_student_analysis
from app.services.teaching_actions import get_teaching_actions
from app.ingestion.student_data import normalize_question_no, saved_total_score, StudentDataError
from app.ingestion.answer_text import question_excerpt
from app.analytics.diagram_analysis import compute_diagram_analysis
from app.services.lecturer_grading import build_lecturer_grading_rows
from app.services.exam_paper_definition import load_exam_paper_definition

router = APIRouter(prefix="/lecturers", tags=["lecturers"])

_analytics_inflight: dict[str, asyncio.Task] = {}


@router.post("/exam-creator/review")
async def review_exam_creator(payload: CreatorRequest, db=Depends(get_db)):
    analytics = {}
    source = payload.paper.source_exam
    if source:
        analytics = await find_exam_analytics(db, payload.course_code, source.session_name,
                                             source.year, source.month, source.semester) or {}
    return review_paper(payload, analytics, course_bank(payload.course_code))


@router.post("/exam-creator/generate")
async def generate_exam_creator(payload: GenerateRequest):
    try:
        result = await generate_for_paper(payload, course_bank(payload.course_code))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if result["status"] != "ok":
        raise HTTPException(status_code=503, detail=result.get("detail") or result.get("reason", "Generation unavailable"))
    return result


# ── helpers (deduplicated from triple copy-paste) ──────────────────────
def _synthesize_diagram_doc(student_id: str, course_code: str, session_name: str, year, month, semester, evaluation_result: dict) -> dict:
    ev = evaluation_result or {}
    total = float(ev.get("total_score", 0) if ev else 0)
    max_sc = float(ev.get("max_score", 20) if ev else 20)
    pct = (total / max_sc * 100) if max_sc else 0
    return {
        "student_id": student_id,
        "subject_code": course_code,
        "subject_name": course_code,
        "year": year or 0,
        "month": month or 0,
        "semester": semester or 0,
        "session_name": session_name,
        "overall_performance": {"score": total, "maximum": max_sc, "percentage": round(pct, 2), "status": performance_status(pct)},
        "question_performance": [],
        "topic_performance": [],
        "bloom_performance": [],
        "learning_analysis": {"overall_performance": performance_status(pct), "strong_topics": [], "developing_topics": [], "weak_topics": [], "critical_topics": [], "learning_gaps": []},
        "model_metadata": {"bloom_model": "diagram", "bloom_model_type": "diagram", "grading_source": "diagram", "rag_context_used": False},
        "generated_at": ev.get("created_at") or "",
        "analysis_version": "1.0",
        "analysis_status": "diagram_only",
    }


def _strip_ai_tips(doc: dict) -> dict:
    filtered = dict(doc)
    filtered.pop("recommendations", None)
    filtered.pop("next_question_strategy", None)
    la = filtered.get("learning_analysis")
    if isinstance(la, dict):
        la_copy = dict(la)
        la_copy.pop("learning_gaps", None)
        la_copy["learning_gaps"] = []
        filtered["learning_analysis"] = la_copy
    return filtered


def _attach_diagram(target: dict, diagram, diagram_marking) -> dict:
    if diagram is not None or diagram_marking is not None:
        payload = {}
        if diagram is not None:
            payload["evaluation"] = diagram
        if diagram_marking is not None:
            payload["marking"] = diagram_marking
        target["diagram"] = payload
        if diagram is not None:
            target["diagram_evaluation"] = diagram
        if diagram_marking is not None:
            target["diagram_marking"] = diagram_marking
    return target


def _is_complete_snapshot(doc: dict | None) -> bool:
    if not doc:
        return False
    if doc.get("topic_assignment_pending"):
        return False
    # Legacy snapshots lack canonical fields or have wrong version
    if doc.get("analytics_version") != ANALYTICS_VERSION:
        return False
    if not isinstance(doc.get("canonical_topic_performance"), list):
        return False
    if not isinstance(doc.get("canonical_insights"), list):
        return False
    # Must have statistics
    if not isinstance(doc.get("statistics"), dict):
        return False
    try:
        ExamAnalyticsDocument.model_validate(doc)
    except ValidationError:
        return False
    return True


async def _refresh_diagram_analysis(db, document, course_code, session_name, year, month, semester):
    # Saved essay analytics may predate diagram grading; refresh without model inference.
    evaluations = await find_diagram_evaluations_for_exam(db, course_code, session_name, year, month, semester)
    markings = await find_diagram_markings_for_exam(db, course_code, session_name, year, month, semester) if evaluations else []
    return {**document, "diagram_analysis": compute_diagram_analysis(evaluations, markings)}


async def _find_canonical_exam(db, course_code, session_name, year, month, semester):
    from calendar import month_name
    identity = {"subjectCode": course_code, "session": {"$in": ["Final", "Final Examination"]} if session_name in ("Final", "Final Examination") else session_name}
    for key, value in (("examYear", year), ("examSemester", semester)):
        if value is not None:
            identity[key] = {"$in": [value, str(value)]}
    if month is not None:
        if not 1 <= month <= 12:
            raise HTTPException(422, "Invalid exam month")
        identity["examMonth"] = {"$in": [month, str(month), month_name[month]]}
    exams = await db["examkeys"].find(identity).to_list(length=2)
    if len(exams) > 1:
        raise HTTPException(409, "Select the exact exam year, month and semester; the exam identity is ambiguous")
    return exams[0] if exams else None


@router.get("/llm-health")
async def llm_health():
    """Real LLM health: ollama reachable + model pulled. Used by question-exam Model online banner."""
    return await check_llm_detailed_health()


@router.get("/bloom-health")
async def bloom_health():
    """Bloom model health: local ModernBERT safetensors availability."""
    from app.config import settings
    from app.classifier.bloom_classifier import is_bloom_model_available

    available = is_bloom_model_available()
    return {
        "enabled": bool(settings.bloom_enabled),
        "available": available,
        "model_dir": settings.bloom_model_dir,
        "threshold": float(settings.bloom_model_threshold),
        "max_length": int(settings.bloom_max_length),
        "device": settings.bloom_device,
        "online": available,
        "detail": "ok" if available else "model not found or disabled",
    }


@router.post("/bloom-predict")
async def bloom_predict(payload: dict):
    """Direct Bloom prediction: ONLY ModernBERT (models/bloom_modernbert), no rules/LLM fallback."""
    text = str(payload.get("text") or payload.get("question_text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text/question_text required")
    from app.classifier.bloom_classifier import is_bloom_model_available, predict_bloom
    from app.classifier.rules import classify_by_rules

    if not is_bloom_model_available():
        raise HTTPException(
            status_code=503,
            detail="Bloom ModernBERT not available — ensure models/bloom_modernbert/bloom.safetensors + tokenizer exist",
        )
    try:
        b = predict_bloom(text)
        rules = classify_by_rules(text, bloom_level=b["level"])
        bloom = b
        status = "bloom_model"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Bloom inference failed: {exc}") from exc
    return {
        "text": text,
        "status": status,
        "bloom": bloom,
        "topic_hint": [a.topic for a in rules.topic_assignments[:3]],
    }


@router.get("/exams")
async def list_exams(db=Depends(get_db)):
    """List all available exams with basic stats."""
    exams = await list_all_exams(db)
    return exams


async def _exam_question(db, course_code, session_name, question_no, year, month, semester):
    identity = {"subject_code": course_code, "session_name": session_name,
                "year": year, "month": month, "semester": semester}
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name, year, month, semester)
    references = {str(s["rubric_ref"]) for s in submissions if s.get("rubric_ref")}
    if len(references) > 1:
        raise HTTPException(status_code=409, detail="This exam contains multiple graded rubric versions. Review the exam's rubric assignments before viewing question evidence.")
    reference = next((s["rubric_ref"] for s in submissions if s.get("rubric_ref")), None)
    if reference is not None:
        identity["_id"] = reference
    rubric = await db["rubricCollection"].find_one(identity)
    if rubric is None and isinstance(reference, str) and ObjectId.is_valid(reference):
        rubric = await db["rubricCollection"].find_one({**identity, "_id": ObjectId(reference)})
    number = normalize_question_no(question_no)
    question = next((q for q in (rubric or {}).get("questions", [])
                     if normalize_question_no(q.get("question_no")) == number), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found for this exam session")
    return rubric, question, submissions


class QuestionTopicPayload(BaseModel):
    topic: str | None = Field(..., max_length=120)


@router.put("/exams/{course_code}/{session_name}/questions/{question_no}/topic")
async def approve_question_topic(
    course_code: str, session_name: str, question_no: str,
    payload: QuestionTopicPayload,
    year: int = Query(...), month: int = Query(...), semester: int = Query(...),
    db=Depends(get_db),
):
    from app.taxonomy.normalizer import load_taxonomy

    rubric, question, _ = await _exam_question(db, course_code, session_name, question_no, year, month, semester)
    taxonomy = await load_taxonomy(db, course_code)
    topics = {entry["canonical_topic"] for entry in taxonomy.values()}
    topic = payload.topic.strip() if payload.topic is not None else None
    if topic is not None and (topic not in topics or topic == "Unclassified"):
        raise HTTPException(status_code=422, detail="Choose a topic from this course's taxonomy")
    questions = [dict(q) for q in rubric["questions"]]
    for q in questions:
        if q.get("question_no") == question.get("question_no"):
            q["approved_topic"] = topic
            q["topic_reviewed_at"] = datetime.now(timezone.utc).isoformat()
    result = await db["rubricCollection"].update_one(
        {"_id": rubric["_id"], "questions": rubric["questions"]}, {"$set": {"questions": questions}},
    )
    if not result.matched_count:
        raise HTTPException(status_code=409, detail="The rubric changed. Reload the question before saving.")
    identity = {"subject_code": course_code, "session_name": session_name,
                "year": year, "month": month, "semester": semester}
    for collection in ("examAnalytics", "analytics_snapshots", "student_analytics", "studentExamAnalysis"):
        await db[collection].update_many(identity, {"$set": {"topic_assignment_pending": True}})
    return {"question_no": normalize_question_no(question_no), "approved_topic": topic}


@router.get("/exams/{course_code}/{session_name}/questions/{question_no}")
async def lecturer_question_detail(
    course_code: str, session_name: str, question_no: str,
    year: int = Query(...), month: int = Query(...), semester: int = Query(...),
    db=Depends(get_db),
):
    """Read question evidence from the rubric and graded submissions, without AI."""
    rubric, question, submissions = await _exam_question(db, course_code, session_name, question_no, year, month, semester)
    number = normalize_question_no(question_no)
    from app.taxonomy.normalizer import load_taxonomy
    taxonomy = await load_taxonomy(db, course_code)
    try:
        criteria = question.get("criteria") or []
        maximum = sum(float(c["marks"]) for c in criteria) if criteria else float(question["max_marks"])
        if not isfinite(maximum) or maximum <= 0:
            raise ValueError("invalid maximum")
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Question has invalid maximum marks")

    responses = []
    excluded_count = 0
    for submission in submissions:
        rows = (submission.get("evaluation") or {}).get("results")
        if rows is None:
            rows = submission.get("results") or []
        result = next((row for row in rows if normalize_question_no(row.get("q_no", row.get("question_no"))) == number), None)
        if result is None:
            continue
        try:
            score = float(result["score"])
            if not isfinite(score) or not 0 <= score <= maximum:
                raise ValueError("invalid score")
        except (KeyError, TypeError, ValueError):
            excluded_count += 1
            continue
        excerpt = result.get("answer_excerpt")
        source = result.get("slice_source")
        if excerpt is None:
            transcript = submission.get("cleaned_ocr_transcript") or submission.get("raw_ocr_transcript") or ""
            excerpt = question_excerpt(transcript, number)
            if excerpt:
                source = "ocr"
        responses.append({
            "student_id": str(submission.get("student_id") or submission.get("student_key") or "Unknown"),
            "score": score,
            "answer_excerpt": excerpt,
            "slice_source": source,
            "feedback": result.get("feedback"),
        })
    counts = Counter(response["score"] for response in responses)
    return {
        "question_no": number,
        "approved_topic": question.get("approved_topic"),
        "topic_options": sorted(entry["canonical_topic"] for entry in taxonomy.values()),
        "question_text": question.get("question_text") or None,
        "max_marks": maximum,
        "mark_distribution": [{"marks": marks, "count": count} for marks, count in sorted(counts.items())],
        "responses": responses,
        "excluded_count": excluded_count,
    }


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
        # Treat legacy/incomplete snapshots as stale and rebuild lazily (no DB deletion)
        # If rebuild fails, retain last good result (clearly stale) rather than 500
        if document is not None and not _is_complete_snapshot(document):
            try:
                fresh = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
                document = fresh
            except Exception:
                document = {**document, "snapshot_status": "stale",
                    "refresh_warning": "Refresh failed. These saved essay analytics may be outdated; review grading issues and reanalyse."}
        elif document is None:
            try:
                document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
            except ExamNotFound as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except StudentDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute analytics: {exc}") from exc
    # Analytics reads have no account-creation side effect — provisioning moved to dedicated endpoint
    # (student access no longer depends on opening lecturer dashboard)
    try:
        document = await _refresh_diagram_analysis(db, document, course_code, session_name, year, month, semester)
        return ExamAnalyticsDocument.model_validate(document)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics document validation failed: {exc}") from exc


@router.post("/exams/{course_code}/{session_name}/analytics/reanalyse")
async def lecturer_exam_reanalyse(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    """Explicit recomputation — forces fresh analytics ignoring cache, for Reanalyse button."""
    try:
        from app.taxonomy.normalizer import invalidate_taxonomy_cache
        await invalidate_taxonomy_cache(course_code)
        document = await compute_exam_analytics(
            db, course_code, session_name, year, month, semester, force_reclassify=True,
        )
    except ExamNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except StudentDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reanalyse: {exc}") from exc
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

        # Fast path: cached (only if complete snapshot)
        cached = await find_exam_analytics(db, course_code, session_name, year, month, semester)
        if cached is not None and _is_complete_snapshot(cached):
            cached = await _refresh_diagram_analysis(db, cached, course_code, session_name, year, month, semester)
            yield sse("progress", {"phase": "cached", "message": "PULSE·AI — Using cached analytics"})
            yield sse("result", cached)
            return
        # Stale/incomplete snapshot: fall through to recompute (do not return mixed revision)
        if cached is not None and not _is_complete_snapshot(cached):
            yield sse("progress", {"phase": "analyzing", "message": "PULSE·AI — Cached snapshot incomplete, recomputing..."})

        queue: asyncio.Queue[str] = asyncio.Queue()

        def progress_cb(msg: str):
            # Thread-safe bridge: schedule put on event loop if called from worker thread
            try:
                loop = asyncio.get_running_loop()
                loop.call_soon_threadsafe(queue.put_nowait, msg)
            except Exception:
                try:
                    queue.put_nowait(msg)
                except Exception:
                    pass

        # Deduplicate in-flight jobs by full exam identity
        job_key = f"{course_code}:{session_name}:{year}:{month}:{semester}"
        existing = _analytics_inflight.get(job_key)
        if existing and not existing.done():
            compute_task = existing
            yield sse("progress", {"phase": "analyzing", "message": "PULSE·AI — Joining existing analysis job..."})
        else:
            compute_task = asyncio.create_task(
                compute_exam_analytics(db, course_code, session_name, year, month, semester, progress_callback=progress_cb)
            )
            _analytics_inflight[job_key] = compute_task
            def _cleanup(fut):
                _analytics_inflight.pop(job_key, None)
            compute_task.add_done_callback(_cleanup)

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

        # Post-processing: document already complete (canonical + weakness included)
        yield sse("progress", {"phase": "finalizing", "message": "PULSE·AI — Finalizing snapshot..."})
        yield sse("result", document)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/exams/{course_code}/{session_name}/provision-accounts")
async def lecturer_provision_accounts(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    """Dedicated student account provisioning (idempotent) — replaces analytics-read side effect."""
    from app.services.student_accounts import provision_student_accounts as _provision
    try:
        result = await _provision(db, course_code, session_name, year, month, semester)
        return {"provisioned": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to provision accounts: {exc}") from exc


@router.get("/exams/{course_code}/{session_name}/paper")
async def lecturer_exam_paper(
    course_code: str, session_name: str,
    year: int = Query(...), month: int = Query(..., ge=1, le=12), semester: int = Query(...),
    db=Depends(get_db),
):
    exam = await _find_canonical_exam(db, course_code, session_name, year, month, semester)
    if exam is None:
        raise HTTPException(404, "No canonical exam record was found for this question paper")
    try:
        return await load_exam_paper_definition(db, exam)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/exams/{course_code}/{session_name}/students")
async def lecturer_student_list(
    course_code: str,
    session_name: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    db=Depends(get_db),
):
    from app.db.repository import load_exam_paper_sources

    exam = await _find_canonical_exam(db, course_code, session_name, year, month, semester)
    if exam:
        sources = await load_exam_paper_sources(db, exam["examKey"])
        try:
            rows = build_lecturer_grading_rows(exam["examKey"], sources)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        for row in rows:
            cached = await find_student_analytics(db, row["student_id"], course_code, session_name, year, month, semester)
            if is_current_student_analysis(cached):
                row["analysis_status"] = "generated"
        return rows

    # Legacy exams without a canonical record retain their existing read path.
    submissions = await find_graded_submissions_for_exam(
        db, course_code, session_name, year, month, semester
    )
    # Also include diagram-evaluated students
    diagram_evals = await find_diagram_evaluations_for_exam(
        db, course_code, session_name, year, month, semester
    )
    # Merge: diagram students not already in submissions
    submission_ids = {s["student_id"] for s in submissions}
    for de in diagram_evals:
        if de["student_id"] not in submission_ids:
            # Synthesize a pseudo-submission from diagram evaluation
            ev_result = de.get("evaluation_result") or {}
            submissions.append({
                "student_id": de["student_id"],
                "subject_code": de.get("subject_code", course_code),
                "session_name": session_name,
                "year": year,
                "month": month,
                "semester": semester,
                "status": "graded",
                "evaluation": {
                    "total_score": ev_result.get("total_score", 0),
                    "max_score": ev_result.get("max_score", 20),
                },
                "max_marks_paper_total": ev_result.get("max_score", 20),
            })
            submission_ids.add(de["student_id"])
    if not submissions:
        raise HTTPException(status_code=404, detail="no graded submissions for exam")
    rows = []
    for submission in submissions:
        student_id = submission["student_id"]
        evaluation = submission.get("evaluation") or {}
        score = saved_total_score(submission)
        cached = await find_student_analytics(
            db, student_id, course_code, session_name, year, month, semester
        )
        rows.append(
            {
                "student_id": student_id,
                "score": score,
                "status": performance_status(score["percentage"]) if score["percentage"] is not None else "Unavailable",
                "analysis_status": "generated" if is_current_student_analysis(cached) else "pending",
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
    auto_analyze: bool = Query(True, description="When true (default), lecturer click triggers analysis generation if not cached"),
    db=Depends(get_db),
):
    """Lecturer view of a single student's performance — excludes AI improvement tips by default.

    When `auto_analyze=true` (default), clicking a student triggers `ensure_student_analytics`
    generation (PULSE·AI) so lecturer sees spinner + progress until ready. Set `auto_analyze=false`
    to read saved analytics or existing diagram results without running analysis.
    Returns the StudentAnalyticsDocument minus `recommendations`, `next_question_strategy`,
    and `learning_analysis.learning_gaps` so lecturers see raw performance only.
    Pass `include_ai_tips=true` to get the full document (student-equivalent).
    """
    doc = await find_student_analytics(db, student_id, course_code, session_name, year, month, semester)
    if not is_current_student_analysis(doc):
        if not auto_analyze:
            from app.db.repository import find_graded_submission, find_diagram_evaluation_for_student, find_diagram_marking_for_student

            diagram = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
            marking = await find_diagram_marking_for_student(db, student_id, course_code, session_name, year, month, semester)
            if diagram is not None or marking is not None:
                saved = diagram if diagram is not None else marking
                doc = _synthesize_diagram_doc(
                    student_id, course_code, session_name,
                    saved.get("year", year), saved.get("month", month), saved.get("semester", semester),
                    saved.get("evaluation_result") or {},
                )
                if not include_ai_tips:
                    doc = _strip_ai_tips(doc)
                return _attach_diagram(doc, diagram, marking)

            sub = await find_graded_submission(db, student_id, course_code, session_name, year, month, semester)
            if sub is None:
                raise HTTPException(status_code=404, detail=f"no graded submission for student {student_id} in {course_code} {session_name}")
            raise HTTPException(status_code=423, detail=f"analytics not yet generated for student {student_id} — ensure exam is analyzed")
        # Auto-analyze for lecturer dashboard (start analysis on click)
        try:
            doc_model = await ensure_student_analytics(db, student_id, course_code, session_name, year, month, semester)
            doc = doc_model.model_dump(mode="json") if hasattr(doc_model, "model_dump") else dict(doc_model)
        except StudentNotFound as exc:
            try:
                from app.db.repository import find_diagram_evaluation_for_student, find_diagram_marking_for_student
                _d = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
                _m = await find_diagram_marking_for_student(db, student_id, course_code, session_name, year, month, semester)
                if _d is not None or _m is not None:
                    doc = _synthesize_diagram_doc(student_id, course_code, session_name, year, month, semester, (_d or {}).get("evaluation_result") or {})
                else:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to analyze student {student_id}: {exc}") from exc
    # Enrich with diagram data (best-effort)
    try:
        from app.db.repository import find_diagram_evaluation_for_student, find_diagram_marking_for_student
        diagram = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
        diagram_marking = await find_diagram_marking_for_student(db, student_id, course_code, session_name, year, month, semester)
    except Exception:
        diagram, diagram_marking = None, None

    if not include_ai_tips:
        filtered = _strip_ai_tips(doc)
        _attach_diagram(filtered, diagram, diagram_marking)
        return filtered
    _attach_diagram(doc, diagram, diagram_marking)
    return doc


@router.get("/exams/{course_code}/{session_name}/student/{student_id}/questions/{question_no}")
async def lecturer_student_answer_evidence(
    course_code: str,
    session_name: str,
    student_id: str,
    question_no: str,
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    semester: int = Query(..., ge=1),
    db=Depends(get_db),
):
    """Read saved grading evidence for this exact student attempt, without analysis."""
    submission = await db["submissions"].find_one({
        "student_id": student_id, "subject_code": course_code, "session_name": session_name,
        "year": year, "month": month, "semester": semester,
        "status": "graded", "archived_at": None,
    }, sort=[("_id", -1)])
    if submission is None:
        raise HTTPException(status_code=404, detail="No saved submission for this student and exam.")
    rows = (submission.get("evaluation") or {}).get("results")
    if rows is None:
        rows = submission.get("results") or []
    number = normalize_question_no(question_no)
    result = next((row for row in rows
                   if normalize_question_no(row.get("q_no", row.get("question_no"))) == number), None)
    if result is None:
        raise HTTPException(status_code=404, detail="No saved grading evidence for this question.")
    excerpt = result.get("answer_excerpt")
    source = result.get("slice_source")
    # An explicitly empty saved slice must not be replaced with a different OCR answer.
    if excerpt is None and source != "empty":
        transcript = submission.get("cleaned_ocr_transcript") or submission.get("raw_ocr_transcript") or ""
        excerpt = question_excerpt(transcript, number)
        if excerpt:
            source = "ocr"
    return {
        "question_no": number,
        "answer_excerpt": excerpt or None,
        "slice_source": source,
        "feedback": result.get("feedback") or None,
        "justification": result.get("justification") or None,
        "criteria_breakdown": [{
            "point": item.get("point") or item.get("criterion") or "",
            "awarded_marks": item.get("awarded_marks"),
            "reason": item.get("reason") or item.get("feedback") or None,
        } for item in result.get("criteria_breakdown") or []],
        "grading_source": result.get("grading_source") or (submission.get("evaluation") or {}).get("grading_source"),
        "grading_error": result.get("error") or None,
    }


@router.get("/exams/{course_code}/{session_name}/student/{student_id}/stream")
async def lecturer_student_detail_stream(
    course_code: str,
    session_name: str,
    student_id: str,
    year: int | None = Query(None),
    month: int | None = Query(None),
    semester: int | None = Query(None),
    include_ai_tips: bool = Query(False),
    db=Depends(get_db),
):
    """SSE stream for lecturer student analyze — real progress (0-100) + result. Progress bar in topbar notification uses this."""
    async def event_generator():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

        # Fast path: cached — real 100% immediately
        cached = await find_student_analytics(db, student_id, course_code, session_name, year, month, semester)
        if is_current_student_analysis(cached):
            yield sse("progress", {"phase": "cached", "message": "PULSE·AI — Using cached student analysis", "progress": 100, "studentId": student_id})
            try:
                from app.db.repository import find_diagram_evaluation_for_student, find_diagram_marking_for_student
                _diag = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
                _mark = await find_diagram_marking_for_student(db, student_id, course_code, session_name, year, month, semester)
                _attach_diagram(cached, _diag, _mark)
            except Exception:
                pass
            if not include_ai_tips:
                yield sse("result", _strip_ai_tips(cached))
            else:
                yield sse("result", cached)
            return

        # Estimate total steps for real progress: questions + insights + save
        total_steps = 5
        try:
            sub = await find_graded_submission(db, student_id, course_code, session_name, year, month, semester)
            if sub and isinstance(sub.get("evaluation"), dict) and isinstance(sub["evaluation"].get("results"), list):
                q_cnt = len(sub["evaluation"]["results"])
                if q_cnt > 0:
                    total_steps = q_cnt + 2  # N questions + insights + final
            else:
                rubric = await db["rubricCollection"].find_one({"subject_code": course_code, "session_name": session_name}, {"questions": 1})
                if rubric and rubric.get("questions"):
                    total_steps = len(rubric["questions"]) + 2
        except Exception:
            total_steps = 5

        steps_done = 0
        queue: asyncio.Queue[str] = asyncio.Queue()

        def progress_cb(msg: str):
            try:
                queue.put_nowait(msg)
            except Exception:
                pass

        compute_task = asyncio.create_task(
            ensure_student_analytics(db, student_id, course_code, session_name, year, month, semester, progress_callback=progress_cb)
        )

        def progress_event(msg: str) -> str:
            nonlocal steps_done
            if msg == "queued":
                return sse("progress", {"phase": "queued", "message": "Queued — waiting for the previous student analysis", "progress": 0, "studentId": student_id})
            if msg == "started":
                return sse("progress", {"phase": "analyzing", "message": f"Analyzing {student_id}…", "progress": 0, "studentId": student_id})
            steps_done += 1
            prog = min(90, max(5, round((steps_done / total_steps) * 90)))
            if "insight" in msg.lower():
                prog = max(prog, 85)
            return sse("progress", {"phase": "analyzing", "message": msg, "progress": prog, "studentId": student_id, "stepsDone": steps_done, "totalSteps": total_steps})

        yield sse("progress", {"phase": "queued", "message": f"Submitting analysis for {student_id}…", "progress": 0, "studentId": student_id})

        while not compute_task.done():
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=0.35)
                yield progress_event(msg)
            except asyncio.TimeoutError:
                yield sse("ping", {"message": "alive", "progress": min(90, round((steps_done / total_steps) * 90)) if total_steps else 0, "studentId": student_id})
            except Exception:
                break

        while not queue.empty():
            try:
                msg = queue.get_nowait()
                yield progress_event(msg)
            except Exception:
                break

        if not compute_task.done():
            # still running, wait briefly
            try:
                await asyncio.wait_for(compute_task, timeout=5)
            except Exception:
                pass

        try:
            doc_model = await compute_task
            doc = doc_model.model_dump(mode="json") if hasattr(doc_model, "model_dump") else dict(doc_model)
        except StudentNotFound as exc:
            yield sse("error", {"detail": str(exc)})
            return
        except Exception as exc:
            yield sse("error", {"detail": f"Failed to analyze student {student_id}: {exc}"})
            return

        # Final 100%
        yield sse("progress", {"phase": "finalizing", "message": f"PULSE·AI — {student_id} analysis complete", "progress": 100, "studentId": student_id})

        try:
            from app.db.repository import find_diagram_evaluation_for_student, find_diagram_marking_for_student
            _diag2 = await find_diagram_evaluation_for_student(db, student_id, course_code, session_name, year, month, semester)
            _mark2 = await find_diagram_marking_for_student(db, student_id, course_code, session_name, year, month, semester)
            _attach_diagram(doc, _diag2, _mark2)
        except Exception:
            pass
        if not include_ai_tips:
            yield sse("result", _strip_ai_tips(doc))
        else:
            yield sse("result", doc)

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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
    # Ensure we use the same snapshot revision displayed on dashboard
    fingerprint = document.get("generated_at") or document.get("analytics_version")
    return await get_teaching_actions(
        db,
        course_code,
        session_name,
        document.get("canonical_topic_performance", []),
        document.get("question_performance", []),
        year=document.get("year") if year is None else year,
        month=document.get("month") if month is None else month,
        semester=document.get("semester") if semester is None else semester,
        evidence_fingerprint=str(fingerprint) if fingerprint else None,
    )


class ExamDraftPaper(CreatorPaper):
    pass


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
    course_code: str | None = Query(None),
):
    """Browse question bank - filter by source/year/topic for ExamCreator right panel."""
    import json
    import pathlib

    bank_path = pathlib.Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "question_bank.json"
    if not bank_path.exists():
        return []
    bank = json.loads(bank_path.read_text(encoding="utf-8"))
    filtered = bank
    if course_code:
        filtered = course_bank(course_code, filtered)
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
    # document already contains complete canonical snapshot; legacy fallback removed
    # If incomplete, the GET analytics path would have rebuilt; here we just validate presence
    if not document.get("canonical_topic_performance") and not _is_complete_snapshot(document):
        # lazy rebuild for legacy snapshot
        try:
            document = await compute_exam_analytics(db, course_code, session_name, document.get("year") or year, document.get("month") or month, document.get("semester") or semester)
        except Exception:
            pass
    try:
        result = recommend_for_weak_areas(document, limit=limit, question_bank=course_bank(course_code))
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
