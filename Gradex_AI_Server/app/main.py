from pathlib import Path
import sys
import json
from uuid import uuid4
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT, V2_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis
from Gradex_AI_Server.app.predict_api import router as predict_router

app = FastAPI(title="Gradex AI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict_router)

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
