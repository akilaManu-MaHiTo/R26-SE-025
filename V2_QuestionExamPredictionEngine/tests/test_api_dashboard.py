import httpx
import pytest

from app.api import deps
from app.db.repository import upsert_student_analytics
from app.main import app
from app.services import student_pipeline
from run_sample import load_raw_sample_documents, seed_raw_samples


TOP_LEVEL_KEYS = {
    "student_id",
    "subject_code",
    "subject_name",
    "year",
    "month",
    "semester",
    "session_name",
    "overall_performance",
    "question_performance",
    "topic_performance",
    "bloom_performance",
    "learning_analysis",
    "recommendations",
    "next_question_strategy",
    "model_metadata",
    "generated_at",
    "analysis_version",
}


def valid_document(
    *,
    student_id: str = "IT-TASK-7-API",
    course_code: str = "SE3040",
    session_name: str = "Semester 1 Final Exam",
) -> dict:
    return {
        "student_id": student_id,
        "subject_code": course_code,
        "subject_name": (
            "Database Management Systems" if course_code == "IT2040" else "Software Engineering"
        ),
        "year": 2022,
        "month": 7,
        "semester": 1,
        "session_name": session_name,
        "overall_performance": {
            "score": 6.0,
            "maximum": 10.0,
            "percentage": 60.0,
            "status": "Developing",
        },
        "question_performance": [],
        "topic_performance": [
            {
                "topic": "Testing",
                "questions_attempted": 1,
                "score": 6.0,
                "max_score": 10.0,
                "percentage": 60.0,
                "status": "Developing",
            }
        ],
        "bloom_performance": [
            {
                "level": "Understand",
                "questions_attempted": 1,
                "average_score": 60.0,
                "status": "Developing",
            }
        ],
        "learning_analysis": {
            "overall_performance": "Developing",
            "strong_topics": [],
            "developing_topics": ["Testing"],
            "weak_topics": [],
            "critical_topics": [],
            "learning_gaps": [],
        },
        "recommendations": [],
        "next_question_strategy": {
            "recommended_topics": ["Testing"],
            "recommended_bloom_levels": ["Understand"],
            "recommended_difficulty": "Medium",
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "rubric",
            "rag_context_used": False,
        },
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


async def _clean_sample_documents(db):
    _, _, submissions = load_raw_sample_documents()
    student_ids = [submission["student_id"] for submission in submissions]
    await db["courses"].delete_many({"code": "IT2040"})
    await db["rubricCollection"].delete_many(
        {"subject_code": "IT2040", "session_name": "Final Examination"}
    )
    await db["submissions"].delete_many(
        {"student_id": {"$in": student_ids}}
    )
    await db["student_analytics"].delete_many(
        {"student_id": {"$in": student_ids}}
    )


async def fake_semantics(_course, _question, _criteria):
    return {
        "status": "ok",
        "semantics": {
            "level": "Understand",
            "topic": "Databases",
            "subtopic": "DBMS Fundamentals",
            "confidence": 0.9,
            "reason": "The question asks for an explanation.",
        },
    }


async def fake_insights(_student_id, _evidence):
    return {"status": "degraded", "reason": "offline_test"}


async def test_dashboard_endpoint_returns_exact_persisted_contract(test_db):
    student_id = "IT-TASK-7-HAPPY"
    await upsert_student_analytics(
        test_db,
        valid_document(
            student_id=student_id,
            course_code="SE3040",
            session_name="Semester 1 Final Exam",
        ),
    )
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/students/{student_id}/dashboard",
                params={
                    "course_code": "SE3040",
                    "session_name": "Semester 1 Final Exam",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert set(body) == TOP_LEVEL_KEYS
        assert body["student_id"] == student_id
        assert body["subject_code"] == "SE3040"
        assert body["subject_name"] == "Software Engineering"
        assert body["session_name"] == "Semester 1 Final Exam"
        assert body["year"] == 2022
        assert body["month"] == 7
        assert body["semester"] == 1
        assert body["topic_performance"][0]["questions_attempted"] == 1
        assert body["bloom_performance"][0]["questions_attempted"] == 1
        assert "_id" not in body
    finally:
        app.dependency_overrides.clear()
        await test_db["student_analytics"].delete_many({"student_id": student_id})


async def test_dashboard_endpoint_forwards_course_and_session_filters(test_db):
    student_id = "IT-TASK-7-FILTERS"
    await upsert_student_analytics(
        test_db,
        valid_document(
            student_id=student_id,
            course_code="SE3040",
            session_name="Semester 1 Final Exam",
        ),
    )
    await upsert_student_analytics(
        test_db,
        valid_document(
            student_id=student_id,
            course_code="IT2040",
            session_name="Semester 2 Final Exam",
        ),
    )
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/students/{student_id}/dashboard",
                params={
                    "course_code": "IT2040",
                    "session_name": "Semester 2 Final Exam",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert body["subject_code"] == "IT2040"
        assert body["subject_name"] == "Database Management Systems"
        assert body["session_name"] == "Semester 2 Final Exam"
    finally:
        app.dependency_overrides.clear()
        await test_db["student_analytics"].delete_many({"student_id": student_id})


async def test_dashboard_endpoint_generates_on_first_access(
    test_db, monkeypatch
):
    _, _, submissions = load_raw_sample_documents()
    student_id = submissions[0]["student_id"]
    await _clean_sample_documents(test_db)
    try:
        await seed_raw_samples(test_db)
        monkeypatch.setattr(
            student_pipeline, "classify_question_semantics", fake_semantics
        )
        monkeypatch.setattr(
            student_pipeline, "generate_student_insights", fake_insights
        )
        app.dependency_overrides[deps.get_db] = lambda: test_db
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/students/{student_id}/dashboard",
                params={
                    "course_code": "IT2040",
                    "session_name": "Final Examination",
                },
            )

        assert response.status_code == 200
        body = response.json()
        assert set(body) == TOP_LEVEL_KEYS
        assert body["subject_code"] == "IT2040"
        assert body["session_name"] == "Final Examination"
        persisted = await test_db["student_analytics"].find_one(
            {"student_id": student_id}
        )
        assert persisted is not None
    finally:
        app.dependency_overrides.clear()
        await _clean_sample_documents(test_db)


async def test_dashboard_endpoint_unknown_student_returns_404(test_db):
    student_id = "IT-TASK-7-MISSING"
    await test_db["student_analytics"].delete_many({"student_id": student_id})
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                f"/api/students/{student_id}/dashboard",
                params={
                    "course_code": "SE3040",
                    "session_name": "Semester 1 Final Exam",
                },
            )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "no graded submission found for student"
        }
    finally:
        app.dependency_overrides.clear()


def test_dashboard_openapi_exposes_required_course_and_session_params():
    operation = app.openapi()["paths"][
        "/api/students/{student_id}/dashboard"
    ]["get"]
    params = {
        parameter["name"]: parameter for parameter in operation["parameters"]
    }

    assert set(params) == {"student_id", "course_code", "session_name"}
    assert params["course_code"]["required"] is True
    assert params["session_name"]["required"] is True
