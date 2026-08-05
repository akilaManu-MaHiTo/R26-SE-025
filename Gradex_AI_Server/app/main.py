from pathlib import Path
from queue import Queue
import sys
import json
from datetime import datetime, timezone
from threading import Thread
from uuid import uuid4
from typing import Any, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

from DiagramEvaluationEngine.predict import run_er_pipeline
from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis
from Gradex_AI_Server.app.mongodb import insert_diagram_evaluation, list_diagram_evaluations

app = FastAPI(title="Gradex AI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = PROJECT_ROOT / "Gradex_AI_Server" / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ENGINE_DATA_EXAM = PROJECT_ROOT / "QuestionExamPredictionEngine" / "data" / "exams" / "exam2022.json"
ENGINE_DATA_ANSWERS = PROJECT_ROOT / "QuestionExamPredictionEngine" / "data" / "answers" / "student_answers2022.json"


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
    


@app.get("/api/analytics/report")
async def analytics_report():
    try:
        return build_exam_report()
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Analytics report not available: {exc}") from exc


@app.post("/api/analytics/run")
async def analytics_run(
    exam_json: UploadFile | None = File(None),
    student_json: UploadFile | None = File(None),
):
    try:
        if exam_json is not None:
            _save_json_upload(exam_json, ENGINE_DATA_EXAM)
        if student_json is not None:
            _save_json_upload(student_json, ENGINE_DATA_ANSWERS)
        return run_exam_analysis()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Analytics run failed: {exc}") from exc


@app.get("/api/analytics/historical")
async def analytics_historical():
    """Load historical performance data from QuestionExamPredictionEngine output folder."""
    try:
        output_dir = PROJECT_ROOT / "QuestionExamPredictionEngine" / "output"
        if not output_dir.exists():
            return {"years": [], "data": {}}

        years_data = {}
        years_list = []

        # Iterate through years (2024, 2025, etc.)
        for year_dir in sorted(output_dir.iterdir()):
            if not year_dir.is_dir():
                continue

            try:
                year = int(year_dir.name)
            except ValueError:
                continue

            years_list.append(year)
            years_data[year] = []

            # Iterate through exam folders
            for exam_dir in year_dir.iterdir():
                if not exam_dir.is_dir():
                    continue

                exam_name = exam_dir.name

                # Iterate through timestamp folders
                for timestamp_dir in sorted(exam_dir.iterdir(), reverse=True):
                    if not timestamp_dir.is_dir():
                        continue

                    try:
                        # Load report files for the session
                        summary_file = timestamp_dir / "student_summary.json"
                        student_report_file = timestamp_dir / "student_report.json"
                        weak_topics_file = timestamp_dir / "weak_topics.json"
                        cognitive_gap_file = timestamp_dir / "cognitive_gap_analysis.json"
                        misunderstood_file = timestamp_dir / "misunderstood_questions.json"

                        if not summary_file.exists() or not weak_topics_file.exists():
                            continue

                        with open(summary_file, "r") as f:
                            student_summaries = json.load(f)
                        student_report = []
                        if student_report_file.exists():
                            with open(student_report_file, "r") as f:
                                student_report = json.load(f)
                        with open(weak_topics_file, "r") as f:
                            weak_topics = json.load(f)
                        cognitive_gap_analysis = []
                        if cognitive_gap_file.exists():
                            with open(cognitive_gap_file, "r") as f:
                                cognitive_gap_analysis = json.load(f)
                        misunderstood_questions = []
                        if misunderstood_file.exists():
                            with open(misunderstood_file, "r") as f:
                                misunderstood_questions = json.load(f)

                        # Calculate statistics
                        total_students = len(student_summaries)
                        avg_learning_score = (
                            sum(s.get("average_learning_score", 0) for s in student_summaries)
                            / total_students
                            if total_students > 0
                            else 0
                        )

                        # Performance band distribution
                        band_dist = {"High": 0, "Medium": 0, "Low": 0}
                        for student in student_summaries:
                            band = student.get("performance_band", "Medium")
                            if band in band_dist:
                                band_dist[band] += 1

                        years_data[year].append({
                            "exam": exam_name,
                            "timestamp": timestamp_dir.name,
                            "totalStudents": total_students,
                            "avgLearningScore": avg_learning_score,
                            "studentSummary": student_summaries,
                            "studentReport": student_report,
                            "weakTopics": weak_topics,
                            "cognitiveGapAnalysis": cognitive_gap_analysis,
                            "misunderstoodQuestions": misunderstood_questions,
                            "performanceBandDistribution": band_dist,
                            "summary": {
                                "total": total_students,
                                "atRisk": band_dist.get("Low", 0),
                                "avgScore": round(avg_learning_score * 100, 1),
                                "cogGaps": len([
                                    row
                                    for row in cognitive_gap_analysis
                                    if str(row.get("gap", "")).strip().upper() != "LOW"
                                ]),
                                "problemCount": len(misunderstood_questions),
                            },
                        })

                    except (json.JSONDecodeError, KeyError) as e:
                        print(f"Error processing {timestamp_dir}: {e}")
                        continue

        return {
            "years": sorted(years_list),
            "data": {str(year): data for year, data in years_data.items()},
        }

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load historical data: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
