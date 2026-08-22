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

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
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
from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis
from Gradex_AI_Server.app.mongodb import insert_diagram_evaluation, list_diagram_evaluations
from Gradex_AI_Server.app.analytics_api import router as analytics_router
from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis
from Gradex_AI_Server.app.auth import configured_api_key, ensure_dev_api_key, require_api_key
from Gradex_AI_Server.app.core.database import connect_to_mongo, close_mongo_connection, db_instance
from Gradex_AI_Server.app.viva_copilot.router import router as viva_copilot_router


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
    


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
