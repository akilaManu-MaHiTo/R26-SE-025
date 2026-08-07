from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_db
from app.db.repository import find_recommendations, latest_run_id
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard

router = APIRouter(prefix="/api/predict", tags=["predict"])


def _trim_recommendation(rec: dict) -> dict:
    return {
        "topic": rec.get("topic"),
        "bloom_level": rec.get("bloom_level"),
        "question_type": rec.get("question_type"),
        "mark_range": list(rec.get("mark_range") or []),
        "priority_score": rec.get("priority_score"),
        "component_breakdown": rec.get("component_breakdown"),
        "evidence": rec.get("evidence"),
    }


@router.get("/exam-recommendations")
async def exam_recommendations(db=Depends(get_db)) -> dict:
    try:
        run_id = await latest_run_id(db)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Prediction backend unavailable: {exc}")
    if run_id is None:
        return {"status": "no_run", "run_id": None, "recommendations": []}
    try:
        run_doc = await db["analysis_runs"].find_one(
            {"run_id": run_id}, {"course_code": 1, "exam_id": 1}
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Prediction backend unavailable: {exc}")
    recs = await find_recommendations(db, run_id)
    return {
        "status": "ok",
        "run_id": run_id,
        "course_code": (run_doc or {}).get("course_code"),
        "exam_id": (run_doc or {}).get("exam_id"),
        "recommendations": [_trim_recommendation(r) for r in recs],
    }


@router.get("/students/{student_key}/dashboard")
async def student_dashboard(
    student_key: str,
    run_id: str | None = None,
    include_llm: bool = False,
    db=Depends(get_db),
):
    try:
        return await build_student_dashboard(db, student_key, run_id, include_llm)
    except StudentDashboardNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))