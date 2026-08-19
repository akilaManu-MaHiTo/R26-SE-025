from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import sys
import json
from uuid import uuid4
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId
from bson.errors import InvalidId

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis
from Gradex_AI_Server.app.core.database import connect_to_mongo, close_mongo_connection, db_instance


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(title="Gradex AI Server", version="1.0.0", lifespan=lifespan)

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


@app.post("/api/digaram-evaluate")
@app.post("/api/diagram-evaluate")
async def diagram_evaluate(image: UploadFile = File(...)):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported.")

    contents = await image.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")

    ext = Path(image.filename or "").suffix or ".jpg"
    file_path = UPLOAD_DIR / f"{uuid4().hex}{ext}"
    file_path.write_bytes(contents)

    try:
        from DiagramEvaluationEngine.predict import run_er_pipeline

        result = run_er_pipeline(file_path)
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Diagram evaluation unavailable: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {exc}") from exc

    return result


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


@app.patch("/api/viva-marks/{mark_id}/publish")
async def publish_viva_mark(mark_id: str, payload: PublishVivaMarkPayload):
    """Persist published assessment: canonical X, human technical (or null), server-computed /100 + grade."""
    if db_instance.marks_col is None:
        raise HTTPException(status_code=503, detail="MongoDB is not connected.")

    from VivaEvaluationEngine.services.assessment_scoring import (
        MODE_WITH,
        MODE_WITHOUT,
        build_assessment,
    )

    mode = payload.assessment_mode.strip()
    if mode not in {MODE_WITHOUT, MODE_WITH}:
        raise HTTPException(status_code=400, detail="assessment_mode must be WITHOUT_TECHNICAL_ACCURACY or WITH_TECHNICAL_ACCURACY.")
    if mode == MODE_WITH and payload.technical_accuracy is None:
        raise HTTPException(status_code=400, detail="technical_accuracy is required for WITH_TECHNICAL_ACCURACY.")
    if mode == MODE_WITHOUT:
        technical = None
    else:
        technical = payload.technical_accuracy

    object_id = _parse_object_id(mark_id)
    existing = await db_instance.marks_col.find_one({"_id": object_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Mark not found.")

    engine_result = existing.get("result") or {}
    assessment = build_assessment(
        engine_result,
        mode=mode,
        technical_accuracy=technical,
    )
    published_at = datetime.now(timezone.utc)
    student_id = (payload.student_id or "").strip() or None
    update = {
        "published": bool(payload.published),
        "human_published": True,
        "published_at": published_at,
        "student_id": student_id,
        "assessment_mode": mode,
        "features": assessment.get("training_features"),
        "feature_schema_version": assessment.get("feature_schema_version"),
        "scoring_version": assessment.get("scoring_version"),
        "ai_performance_score": (assessment.get("ai_performance") or {}).get("score"),
        "technical_accuracy": assessment.get("technical_accuracy"),
        "final_score": assessment.get("final_score"),
        "final_grade": assessment.get("grade"),
        "assessment": assessment,
    }

    result = await db_instance.marks_col.update_one({"_id": object_id}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Mark not found.")

    return {
        "mark_id": mark_id,
        "published": update["published"],
        "published_at": published_at.isoformat(),
        "student_id": student_id,
        "assessment_mode": mode,
        "ai_performance_score": update["ai_performance_score"],
        "technical_accuracy": update["technical_accuracy"],
        "final_score": update["final_score"],
        "final_grade": update["final_grade"],
        "status": assessment.get("status"),
        "scoring_version": update["scoring_version"],
        "feature_schema_version": update["feature_schema_version"],
    }


@app.post("/api/viva-analyze")
async def viva_analyze(video: UploadFile = File(...)):
    """
    Analyze a viva recording for emotion detection and engagement scoring.
    
    Returns:
        - timeline: Frame-by-frame emotion and engagement analysis
        - confidence_score: Facial affect positivity score (0-100), or null if coverage insufficient
        - engagement_score: Overall engagement score (0-100), or null if coverage insufficient
        - coverage / video_status: Face-hit diagnostics
        - audio_analysis: Transcript, acoustics, grade (may be degraded/insufficient)
        - summary: Summary statistics
    """
    import asyncio
    import time
    request_start = time.time()
    
    if not video.content_type or not video.content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Only video uploads are supported.")

    contents = await video.read()
    upload_complete = time.time()
    upload_time = upload_complete - request_start
    print(f"[VIVA] Upload received: {len(contents) / 1024 / 1024:.2f} MB in {upload_time:.2f}s")
    
    if not contents:
        raise HTTPException(status_code=400, detail="Empty upload.")

    ext = Path(video.filename or "").suffix or ".mp4"
    file_path = UPLOAD_DIR / f"{uuid4().hex}{ext}"
    file_path.write_bytes(contents)
    file_saved = time.time()
    print(f"[VIVA] File saved: {file_path.name} in {file_saved - upload_complete:.2f}s")

    try:
        from Gradex_AI_Server.app.viva_service import analyze_video_file

        analysis_start = time.time()
        # ML pipeline is CPU/GPU-bound; keep the event loop free for other requests.
        result = await asyncio.to_thread(analyze_video_file, str(file_path), False)
        analysis_complete = time.time()
        analysis_time = analysis_complete - analysis_start
        total_time = analysis_complete - request_start
        
        print(f"[VIVA] Analysis complete in {analysis_time:.2f}s (Total: {total_time:.2f}s)")
        
        # Clean up the uploaded file after analysis
        try:
            file_path.unlink()
        except Exception:
            pass
        # Persist the result to MongoDB (vivamark.marks). Best-effort: a
        # storage failure should not fail an otherwise-successful analysis.
        try:
            mark_doc = {
                "video_filename": video.filename,
                "processed_at": datetime.now(timezone.utc),
                "confidence_score": result.get("confidence_score"),
                "engagement_score": result.get("engagement_score"),
                "video_status": result.get("video_status"),
                "assessment": result.get("assessment"),
                "scoring_version": (result.get("assessment") or {}).get("scoring_version"),
                "feature_schema_version": (result.get("assessment") or {}).get("feature_schema_version"),
                "result": result,
            }
            insert_result = await db_instance.marks_col.insert_one(mark_doc)
            result["mark_id"] = str(insert_result.inserted_id)
        except Exception as exc:
            print(f"[VIVA] Warning: failed to persist result to MongoDB: {exc}")
        return result
    except ModuleNotFoundError as exc:
        raise HTTPException(status_code=503, detail=f"Viva analysis unavailable: {exc}") from exc
    except FileNotFoundError as exc:
        # Model files or other required files missing
        raise HTTPException(status_code=503, detail=f"Viva model file not found: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Viva analysis failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
