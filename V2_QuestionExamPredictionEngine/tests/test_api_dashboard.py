import httpx

from app.api import deps
from app.db.repository import upsert_student_analytics
from app.main import app


TOP_LEVEL_KEYS = {
    "student_id",
    "course",
    "assessment",
    "question_analysis",
    "topic_performance",
    "bloom_performance",
    "learning_analysis",
    "recommendations",
    "next_question_generation",
    "model_metadata",
}


def valid_document(
    *,
    student_id: str = "IT-TASK-7-API",
    course_code: str = "SE3040",
    session_name: str = "Semester 1 Final Exam",
) -> dict:
    return {
        "student_id": student_id,
        "course": {"code": course_code, "name": "Software Engineering"},
        "assessment": {
            "session_name": session_name,
            "rubric_ref": "rubric-001",
            "total_score": 6.0,
            "max_score": 10.0,
            "percentage": 60.0,
        },
        "question_analysis": [],
        "topic_performance": [
            {
                "topic": "Testing",
                "questions_attempted": 1,
                "score": 6.0,
                "max_score": 10.0,
                "percentage": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "bloom_performance": [
            {
                "level": "Understand",
                "questions_attempted": 1,
                "average_score": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "weak_topics": ["Testing"],
            "strong_topics": [],
            "weak_bloom_levels": ["Understand"],
            "weak_subtopics": ["Unit testing"],
            "learning_gaps": ["Review unit testing."],
        },
        "recommendations": [],
        "next_question_generation": {
            "recommended_bloom_level": "Apply",
            "recommended_difficulty": "Medium",
            "recommended_topics": ["Testing"],
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "rubric",
            "rag_context_used": False,
        },
    }


async def test_dashboard_endpoint_returns_exact_persisted_contract(test_db):
    student_id = "IT-TASK-7-HAPPY"
    await upsert_student_analytics(test_db, valid_document(student_id=student_id))
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(f"/api/students/{student_id}/dashboard")

        assert response.status_code == 200
        body = response.json()
        assert set(body) == TOP_LEVEL_KEYS
        assert body["student_id"] == student_id
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
                f"/api/students/{student_id}/dashboard"
                "?course_code=IT2040&session_name=Semester%202%20Final%20Exam"
            )

        assert response.status_code == 200
        body = response.json()
        assert body["course"]["code"] == "IT2040"
        assert body["assessment"]["session_name"] == "Semester 2 Final Exam"
    finally:
        app.dependency_overrides.clear()
        await test_db["student_analytics"].delete_many({"student_id": student_id})


async def test_dashboard_endpoint_unknown_student_returns_404(test_db):
    student_id = "IT-TASK-7-MISSING"
    await test_db["student_analytics"].delete_many({"student_id": student_id})
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(f"/api/students/{student_id}/dashboard")

        assert response.status_code == 404
        assert response.json() == {
            "detail": "no saved analytics found for student"
        }
    finally:
        app.dependency_overrides.clear()


def test_dashboard_openapi_exposes_only_replacement_parameters():
    operation = app.openapi()["paths"][
        "/api/students/{student_id}/dashboard"
    ]["get"]

    assert [parameter["name"] for parameter in operation["parameters"]] == [
        "student_id",
        "course_code",
        "session_name",
    ]
