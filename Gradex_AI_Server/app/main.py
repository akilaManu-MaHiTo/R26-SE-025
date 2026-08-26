from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from queue import Queue
import sys
import json
from threading import Thread
from uuid import uuid4
from typing import Any, Optional
import os

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.errors import InvalidId

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT, V2_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

from DiagramEvaluationEngine.predict import run_er_pipeline
from Gradex_AI_Server.app.mongodb import insert_diagram_evaluation, list_diagram_evaluations
from Gradex_AI_Server.app.analytics_api import router as analytics_router
from Gradex_AI_Server.app.auth import configured_api_key, ensure_dev_api_key, require_api_key
from Gradex_AI_Server.app.core.database import connect_to_mongo, close_mongo_connection, db_instance
from Gradex_AI_Server.app.viva_copilot.router import router as viva_copilot_router
from V2_QuestionExamPredictionEngine.app.api.lecturer import router as v2_lecturer_router


MAX_VIVA_UPLOAD_BYTES = 1024 * 1024 * 1024
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}


def _analyze_timeout_seconds() -> float:
    raw = (os.getenv("VIVA_ANALYZE_TIMEOUT_SECONDS") or "600").strip()
    try:
        value = float(raw)
    except ValueError:
        return 600.0
    return value if value > 0 else 600.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not configured_api_key():
        ensure_dev_api_key()
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Gradex AI Server", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analytics_router)
app.include_router(viva_copilot_router)
app.include_router(v2_lecturer_router, prefix="/api")

UPLOAD_DIR = PROJECT_ROOT / "Gradex_AI_Server" / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ENGINE_DATA_EXAM = PROJECT_ROOT / "QuestionExamPredictionEngine" / "data" / "exams" / "exam2022.json"
ENGINE_DATA_ANSWERS = PROJECT_ROOT / "QuestionExamPredictionEngine" / "data" / "answers" / "student_answers2022.json"


class RubricCriterionPayload(BaseModel):
    id: str
    name: str
    description: str = ""
    score: float = Field(ge=0)
    max: float = Field(gt=0)


class PublishVivaMarkPayload(BaseModel):
    assessment_mode: str
    technical_accuracy: Optional[float] = Field(default=None, ge=0, le=10)
    student_id: Optional[str] = None
    published: bool = True


def _parse_object_id(mark_id: str) -> ObjectId:
    try:
        return ObjectId(mark_id)
    except (InvalidId, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid mark_id.") from exc


def _save_json_upload(upload: UploadFile, destination: Path) -> None:
    contents = upload.file.read()
    if not contents:
        raise HTTPException(status_code=400, detail=f"Empty upload for {upload.filename or destination.name}.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(contents)


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=True)}\n\n"


class DiagramEvaluationSaveRequest(BaseModel):
    student_id: str = ""
    subject_code: str = ""
    subject_name: str = ""
    year: int
    month: int
    semester: int
    session_name: str = ""
    diagram_marks: int = 0
    diagram_details: dict[str, Any] = Field(default_factory=dict)
    diagram_entity_relations: list[dict[str, Any]] = Field(default_factory=list)
    diagram_relations: list[dict[str, Any]] = Field(default_factory=list)
    remarks: str = ""
    evaluation_result: dict[str, Any] = Field(default_factory=dict)


def _normalize_text(value: str, fallback: str = "") -> str:
    trimmed = value.strip() if isinstance(value, str) else ""
    return trimmed or fallback


def _normalize_record(payload: DiagramEvaluationSaveRequest) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    details = payload.diagram_details if isinstance(payload.diagram_details, dict) else {}
    if isinstance(details, dict):
        details = {key: value for key, value in details.items() if key != "annotated_image"}

    evaluation_result = payload.evaluation_result if isinstance(payload.evaluation_result, dict) else {}
    if isinstance(evaluation_result, dict):
        evaluation_result = {
            key: value
            for key, value in evaluation_result.items()
            if key != "annotated_image"
        }

    entity_relations = (
        payload.diagram_entity_relations
        if isinstance(payload.diagram_entity_relations, list)
        else []
    )
    relations = (
        payload.diagram_relations
        if isinstance(payload.diagram_relations, list)
        else []
    )

    return {
        "student_id": _normalize_text(payload.student_id, "UNKNOWN"),
        "subject_code": _normalize_text(payload.subject_code),
        "subject_name": _normalize_text(payload.subject_name),
        "year": int(payload.year),
        "month": int(payload.month),
        "semester": int(payload.semester),
        "session_name": _normalize_text(payload.session_name, "Final Examination"),
        "diagram_marks": int(payload.diagram_marks),
        "diagram_details": details,
        "diagram_entity_relations": entity_relations,
        "diagram_relations": relations,
        "remarks": _normalize_text(payload.remarks),
        "evaluation_result": evaluation_result,
        "created_at": now,
        "updated_at": now,
        "source": "diagram-evaluation",
    }


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if value.__class__.__name__ == "ObjectId":
        return str(value)
    return value

@app.post("/api/digaram-evaluate")
@app.post("/api/diagram-evaluate")
async def diagram_evaluate(image: UploadFile = File(...), stream: bool = False):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")

    ext = Path(image.filename or "").suffix or ".jpg"
    file_path = UPLOAD_DIR / f"{uuid4().hex}{ext}"
    file_path.write_bytes(contents)

    if not stream:
        try:
            return run_er_pipeline(file_path)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}") from exc

    event_queue: Queue = Queue()
    sentinel = object()

    def worker() -> None:
        try:
            result = run_er_pipeline(file_path, progress_callback=event_queue.put)
            event_queue.put({"type": "result", "payload": result})
        except Exception as exc:
            event_queue.put({"type": "error", "payload": str(exc)})
        finally:
            event_queue.put(sentinel)

    Thread(target=worker, daemon=True).start()

    async def stream_events():
        while True:
            item = await __import__("asyncio").to_thread(event_queue.get)
            if item is sentinel:
                break
            if isinstance(item, dict) and item.get("type") == "error":
                yield _sse_event("error", {"detail": item["payload"]})
                break
            if isinstance(item, dict) and item.get("type") == "result":
                yield _sse_event("result", item["payload"])
                continue
            yield _sse_event("progress", item if isinstance(item, dict) else {"message": str(item)})

    return StreamingResponse(stream_events(), media_type="text/event-stream")


@app.post("/api/diagram-evaluate-save")
async def diagram_evaluate_save(payload: DiagramEvaluationSaveRequest):
    try:
        record = _normalize_record(payload)
        inserted_id = insert_diagram_evaluation(record)
        return _json_safe({
            "status": "saved",
            "inserted_id": str(inserted_id),
            "record": record,
        })
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save diagram evaluation: {exc}") from exc

@app.get("/api/diagram-evaluate-details")
async def diagram_evaluate_details():
    try:
        return _json_safe(list_diagram_evaluations())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class SubjectRubricConceptPayload(BaseModel):
    id: str
    name: str
    description: str = ""
    weight: float = Field(default=3.0, ge=0, le=5)


class SubjectRubricUpdatePayload(BaseModel):
    subject_name: str
    concepts: list[SubjectRubricConceptPayload]


@app.post("/api/subject-content/upload", dependencies=[Depends(require_api_key)])
async def upload_subject_content(
    file: UploadFile = File(...),
    subject_code: str = Form(...),
    subject_name: str = Form(...),
):
    """Upload a subject PDF; extracts its text and asks Groq to distill it into
    a concept rubric (list of {name, description, weight}) used by
    /api/viva-analyze's optional technical-accuracy step. Independent of
    GradingEngine/VivaEvaluationEngine — see subject_rubric_service.py."""
    from Gradex_AI_Server.app.subject_rubric_service import (
        RubricGenerationError,
        extract_pdf_text,
        generate_concept_rubric,
        upsert_subject_rubric,
    )

    filename = file.filename or ""
    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")

    code = subject_code.strip()
    name = subject_name.strip()
    if not code:
        raise HTTPException(status_code=400, detail="subject_code is required.")

    tmp_path = UPLOAD_DIR / f"{uuid4().hex}.pdf"
    tmp_path.write_bytes(contents)
    try:
        text = extract_pdf_text(str(tmp_path))
        concepts = generate_concept_rubric(text, name or code)
        return await upsert_subject_rubric(db_instance, code, name, filename, concepts)
    except RubricGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to process subject content: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)


@app.get("/api/subject-content/{subject_code}", dependencies=[Depends(require_api_key)])
async def get_subject_content(subject_code: str):
    from Gradex_AI_Server.app.subject_rubric_service import get_subject_rubric

    rubric = await get_subject_rubric(db_instance, subject_code)
    if rubric is None:
        raise HTTPException(status_code=404, detail="No subject rubric found for this subject_code.")
    return rubric


@app.put("/api/subject-content/{subject_code}", dependencies=[Depends(require_api_key)])
async def update_subject_content(subject_code: str, payload: SubjectRubricUpdatePayload):
    """Lets a lecturer review/curate the AI-drafted concept rubric before it's
    used for grading."""
    from Gradex_AI_Server.app.subject_rubric_service import replace_subject_rubric

    concepts = [c.model_dump() for c in payload.concepts]
    try:
        return await replace_subject_rubric(db_instance, subject_code, payload.subject_name, concepts)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _require_marks_collection():
    if db_instance.marks_col is None:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not connected. Check MONGODB_URL / DATABASE_NAME and Atlas credentials.",
        )
    return db_instance.marks_col


def _summarize_mark_document(document: dict[str, Any]) -> dict[str, Any]:
    assessment = document.get("assessment") or {}
    return {
        "mark_id": str(document.get("_id")),
        "video_filename": document.get("video_filename"),
        "student_id": document.get("student_id"),
        "processed_at": document.get("processed_at"),
        "published": bool(document.get("published")),
        "published_at": document.get("published_at"),
        "assessment_mode": document.get("assessment_mode"),
        "video_status": document.get("video_status"),
        "confidence_score": document.get("confidence_score"),
        "engagement_score": document.get("engagement_score"),
        "ai_performance_score": document.get("ai_performance_score"),
        "technical_accuracy": document.get("technical_accuracy"),
        "final_score": document.get("final_score"),
        "final_grade": document.get("final_grade"),
        "status": assessment.get("status"),
        "scoring_version": document.get("scoring_version"),
    }


@app.get("/api/viva-marks", dependencies=[Depends(require_api_key)])
async def list_viva_marks(
    limit: int = 20,
    student_id: Optional[str] = None,
    published: Optional[bool] = None,
):
    """List recent viva marks saved after POST /api/viva-analyze."""
    marks_col = _require_marks_collection()
    safe_limit = max(1, min(limit, 100))
    query: dict[str, Any] = {}
    if student_id and student_id.strip():
        query["student_id"] = student_id.strip()
    if published is not None:
        query["published"] = published

    try:
        cursor = marks_col.find(query).sort("processed_at", -1).limit(safe_limit)
        documents = await cursor.to_list(length=safe_limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB query failed: {exc}") from exc

    return {
        "items": [_summarize_mark_document(doc) for doc in documents],
        "count": len(documents),
    }


@app.get("/api/viva-marks/{mark_id}", dependencies=[Depends(require_api_key)])
async def get_viva_mark(mark_id: str):
    """Fetch one saved viva mark by Mongo ObjectId."""
    marks_col = _require_marks_collection()
    object_id = _parse_object_id(mark_id)
    try:
        document = await marks_col.find_one({"_id": object_id})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MongoDB query failed: {exc}") from exc
    if not document:
        raise HTTPException(status_code=404, detail="Mark not found.")
    return _json_safe(document)


@app.patch("/api/viva-marks/{mark_id}/publish", dependencies=[Depends(require_api_key)])
async def publish_viva_mark(mark_id: str, payload: PublishVivaMarkPayload):
    """Persist published assessment: canonical X, human technical (or null), server-computed /100 + grade."""
    from Gradex_AI_Server.app.viva_marks import apply_publish_to_mark
    from VivaEvaluationEngine.services.assessment_scoring import MODE_WITH, MODE_WITHOUT

    object_id = _parse_object_id(mark_id)
    marks_col = _require_marks_collection()

    mode = payload.assessment_mode.strip()
    if mode not in {MODE_WITHOUT, MODE_WITH}:
        raise HTTPException(status_code=400, detail="assessment_mode must be WITHOUT_TECHNICAL_ACCURACY or WITH_TECHNICAL_ACCURACY.")
    if mode == MODE_WITH and payload.technical_accuracy is None:
        raise HTTPException(status_code=400, detail="technical_accuracy is required for WITH_TECHNICAL_ACCURACY.")

    student_id = (payload.student_id or "").strip() or None
    technical = None if mode == MODE_WITHOUT else payload.technical_accuracy

    try:
        return await apply_publish_to_mark(
            marks_col,
            object_id,
            mode=mode,
            technical_accuracy=technical,
            student_id=student_id,
            human_published=True,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="Mark not found.") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="MongoDB is not reachable. Marks cannot be published until Atlas auth succeeds.",
        ) from None


@app.post("/api/viva-analyze", dependencies=[Depends(require_api_key)])
async def viva_analyze(
    video: UploadFile = File(...),
    assessment_mode: str = Form(default="WITHOUT_TECHNICAL_ACCURACY"),
    subject_code: Optional[str] = Form(default=None),
):
    """
    Analyze a viva recording for emotion detection and engagement scoring.

    `assessment_mode` is the examiner's upfront choice (before upload/recording,
    not changeable afterward — see VivaPage.tsx): WITHOUT_TECHNICAL_ACCURACY for
    communication/presentation vivas, WITH_TECHNICAL_ACCURACY for technical
    modules. Only WITHOUT auto-publishes; WITH always leaves the mark as an
    unpublished draft so a human must enter a technical score and publish before
    it counts as a grade — see PRD "no grade issued purely on AI authority".

    `subject_code` is optional. When set and a concept rubric exists for it
    (see /api/subject-content), an AI-suggested technical_accuracy_ai score is
    attached to the result as an advisory panel — never auto-published; the
    examiner still enters/reviews the technical score themselves.

    Returns:
        - timeline: Frame-by-frame emotion and engagement analysis
        - confidence_score: Facial affect positivity score (0-100), or null if coverage insufficient
        - engagement_score: Overall engagement score (0-100), or null if coverage insufficient
        - coverage / video_status: Face-hit diagnostics
        - audio_analysis: Transcript, acoustics, grade (may be degraded/insufficient)
        - summary: Summary statistics
        - assessment: Official Stage-1 mark (INCOMPLETE when the face is missing)
    """
    import asyncio
    import time
    from VivaEvaluationEngine.services.assessment_scoring import MODE_WITH, MODE_WITHOUT

    request_start = time.time()
    # A stray/unexpected value (or the Form(...) sentinel object seen when this
    # function is called directly, bypassing FastAPI's request parsing — as the
    # HTTP-layer tests do) falls back to the safe default rather than raising.
    requested_mode = assessment_mode if assessment_mode in {MODE_WITH, MODE_WITHOUT} else MODE_WITHOUT

    filename = video.filename or ""
    suffix = Path(filename).suffix.lower()
    content_type = (video.content_type or "").lower()
    looks_like_video = content_type.startswith("video/") or suffix in VIDEO_SUFFIXES
    if not looks_like_video:
        raise HTTPException(status_code=400, detail="Only video uploads are supported.")

    contents = await video.read()
    upload_complete = time.time()
    upload_time = upload_complete - request_start
    print(f"[VIVA] Upload received: {len(contents) / 1024 / 1024:.2f} MB in {upload_time:.2f}s")

    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(contents) > MAX_VIVA_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File size must be less than 1 GB.")

    ext = suffix if suffix in VIDEO_SUFFIXES else ".mp4"
    file_path = UPLOAD_DIR / f"{uuid4().hex}{ext}"
    file_path.write_bytes(contents)
    file_saved = time.time()
    print(f"[VIVA] File saved: {file_path.name} in {file_saved - upload_complete:.2f}s")

    try:
        from Gradex_AI_Server.app.viva_service import analyze_video_file

        analysis_start = time.time()
        timeout_s = _analyze_timeout_seconds()
        # ML pipeline is CPU/GPU-bound; keep the event loop free for other requests.
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(analyze_video_file, str(file_path), False),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=504,
                detail=f"Analysis exceeded {int(timeout_s)}s. Try a shorter recording.",
            ) from exc
        analysis_complete = time.time()
        analysis_time = analysis_complete - analysis_start
        total_time = analysis_complete - request_start

        # Optional technical-accuracy step. Deliberately NOT part of
        # analyze_video_file/viva_service.py's internal chain — it's layered
        # on here as a decoupled post-processing call so that file, and the
        # rest of VivaEvaluationEngine's existing pipeline, stay untouched.
        # subject_code may be the raw Form(...) sentinel object (not None) when
        # this handler is called directly, bypassing FastAPI's request parsing —
        # as the HTTP-layer tests do (see requested_mode above for the same issue).
        code = subject_code.strip() if isinstance(subject_code, str) else ""
        if code:
            try:
                from Gradex_AI_Server.app.subject_rubric_service import get_subject_rubric
                from VivaEvaluationEngine.services.technical_accuracy import (
                    attach_technical_accuracy,
                )

                concept_rubric = await get_subject_rubric(db_instance, code)
                result = attach_technical_accuracy(result, concept_rubric)
            except Exception as tech_exc:
                print(f"[VIVA] Warning: technical-accuracy scoring failed ({tech_exc})")
                result["technical_accuracy_ai"] = {
                    "status": "unavailable",
                    "model": None,
                    "overall_score": None,
                    "concepts": [],
                    "error": str(tech_exc),
                }

        print(f"[VIVA] Analysis complete in {analysis_time:.2f}s (Total: {total_time:.2f}s)")
        # Persist the result to MongoDB (vivamark.marks). Best-effort: a
        # storage failure should not fail an otherwise-successful analysis.
        from Gradex_AI_Server.app.core.database import ensure_marks_collection

        if not await ensure_marks_collection():
            result["persistence_error"] = (
                "MongoDB is not connected — mark was not saved. Publish is unavailable."
            )
            print(f"[VIVA] Warning: {result['persistence_error']}")
        else:
            try:
                mark_doc = {
                    "video_filename": video.filename,
                    "processed_at": datetime.now(timezone.utc),
                    "published": False,
                    "human_published": False,
                    "student_id": None,
                    "confidence_score": result.get("confidence_score"),
                    "engagement_score": result.get("engagement_score"),
                    "video_status": result.get("video_status"),
                    "assessment": result.get("assessment"),
                    "scoring_version": (result.get("assessment") or {}).get("scoring_version"),
                    "feature_schema_version": (result.get("assessment") or {}).get("feature_schema_version"),
                    "result": result,
                }
                insert_result = await db_instance.marks_col.insert_one(mark_doc)
                mark_object_id = insert_result.inserted_id
                result["mark_id"] = str(mark_object_id)
                result["published"] = False
                result["assessment_mode"] = requested_mode

                if requested_mode == MODE_WITH:
                    # Technical viva: never auto-publish. The mark stays a draft
                    # until an examiner enters a technical score and publishes —
                    # this is what makes "reviewed before publishing" true rather
                    # than aspirational for the assessments that need it.
                    print(f"[VIVA] Technical viva — mark {result['mark_id']} saved as draft, awaiting examiner review.")
                else:
                    from Gradex_AI_Server.app.viva_marks import (
                        auto_publish_without_technical,
                        merge_auto_publish_into_analyze_result,
                    )

                    try:
                        auto_payload = await auto_publish_without_technical(
                            db_instance.marks_col,
                            mark_object_id,
                            result,
                        )
                        if auto_payload:
                            merge_auto_publish_into_analyze_result(result, auto_payload)
                            print(f"[VIVA] Auto-published mark {result['mark_id']} (non-technical viva)")
                    except Exception as auto_exc:
                        print(f"[VIVA] Warning: auto-publish failed; mark remains draft. ({auto_exc})")
            except Exception as exc:
                result["persistence_error"] = (
                    "Could not save mark (Mongo authentication or network failed)."
                )
                print(f"[VIVA] Warning: failed to persist result to MongoDB ({type(exc).__name__}: {exc})")
                await ensure_marks_collection()
        return result
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Viva analysis unavailable: {exc}") from exc
    except FileNotFoundError as exc:
        message = str(exc)
        if "Could not open video" in message or "video file" in message.lower():
            raise HTTPException(
                status_code=400,
                detail="This file could not be opened as a video. Upload MP4 or WEBM.",
            ) from exc
        raise HTTPException(status_code=503, detail=f"Viva model file not found: {exc}") from exc
    except HTTPException:
        raise
    except Exception as exc:
        if exc.__class__.__name__ == "VideoUnreadableError" or "could not be opened as a video" in str(exc).lower():
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=f"Viva analysis failed: {exc}") from exc
    finally:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
