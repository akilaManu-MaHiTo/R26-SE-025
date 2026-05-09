from pathlib import Path
import sys
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = PROJECT_ROOT / "DiagramEvaluationEngine"
for path in (PROJECT_ROOT, ENGINE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.append(path_str)

from DiagramEvaluationEngine.predict import run_er_pipeline
from Gradex_AI_Server.app.analytics_report import build_exam_report, run_exam_analysis

app = FastAPI(title="Gradex AI Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = PROJECT_ROOT / "Gradex_AI_Server" / "app"/ "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ENGINE_DATA_EXAM = PROJECT_ROOT / "Question-ExamPredictionEngine" / "data" / "exams" / "exam2022.json"
ENGINE_DATA_ANSWERS = PROJECT_ROOT / "Question-ExamPredictionEngine" / "data" / "answers" / "student_answers2022.json"


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
        result = run_er_pipeline(file_path)
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("Gradex_AI_Server.app.main:app", host="0.0.0.0", port=8000, reload=True)
