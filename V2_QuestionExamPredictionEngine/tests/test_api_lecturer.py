import httpx

from app.api import deps
from app.db.repository import upsert_exam_analytics, upsert_student_analytics
from app.main import app
from app.schemas.student import StudentAnalyticsDocument
from run_sample import load_raw_sample_documents
from tests.test_exam_analytics import exam_document
from tests.test_run_sample import _clean_sample_documents


def valid_student_document() -> dict:
    return {
        "student_id": "IT22145976",
        "subject_code": "IT2040",
        "subject_name": "Database Management Systems",
        "year": 2022,
        "month": 7,
        "semester": 1,
        "session_name": "Final Examination",
        "overall_performance": {
            "score": 60.0,
            "maximum": 100.0,
            "percentage": 60.0,
            "status": "Developing",
        },
        "question_performance": [],
        "topic_performance": [],
        "bloom_performance": [],
        "learning_analysis": {
            "overall_performance": "Developing",
            "strong_topics": [],
            "developing_topics": [],
            "weak_topics": [],
            "critical_topics": [],
            "learning_gaps": [],
        },
        "recommendations": [],
        "next_question_strategy": {
            "recommended_topics": [],
            "recommended_bloom_levels": [],
            "recommended_difficulty": "Medium",
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "colab",
            "rag_context_used": False,
        },
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


async def test_lecturer_analytics_endpoint_returns_document(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        await upsert_exam_analytics(test_db, exam_document())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/lecturers/exams/IT2040/Final%20Examination/analytics"
            )
        assert response.status_code == 200
        assert response.json()["subject_code"] == "IT2040"
        assert response.json()["session_name"] == "Final Examination"
    finally:
        app.dependency_overrides.clear()
        await test_db["analytics_snapshots"].delete_many({})


async def test_lecturer_students_endpoint_reports_analysis_status(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    await _clean_sample_documents(test_db)
    try:
        _, _, submissions = load_raw_sample_documents()
        for submission in submissions:
            submission_document = {
                key: value for key, value in submission.items() if key != "_id"
            }
            await test_db["submissions"].replace_one(
                {
                    "student_id": submission["student_id"],
                    "subject_code": "IT2040",
                    "session_name": "Final Examination",
                },
                submission_document,
                upsert=True,
            )
        await upsert_student_analytics(test_db, valid_student_document())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/lecturers/exams/IT2040/Final%20Examination/students"
            )
        assert response.status_code == 200
        rows = response.json()
        assert len(rows) == 5
        statuses = {row["student_id"]: row["analysis_status"] for row in rows}
        assert statuses["IT22145976"] == "generated"
    finally:
        app.dependency_overrides.clear()
        await _clean_sample_documents(test_db)


async def test_lecturer_analytics_endpoint_returns_404_without_submissions(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/lecturers/exams/SE3040/Semester%201%20Final%20Exam/analytics"
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        await test_db["analytics_snapshots"].delete_many(
            {"subject_code": "SE3040", "session_name": "Semester 1 Final Exam"}
        )


async def test_lecturer_students_endpoint_returns_404_without_submissions(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/lecturers/exams/SE3040/Semester%201%20Final%20Exam/students"
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_valid_student_document_is_a_reshaped_student_analytics_document():
    document = valid_student_document()
    validated = StudentAnalyticsDocument.model_validate(document)
    assert validated.student_id == "IT22145976"
    assert validated.subject_code == "IT2040"
    assert validated.subject_name == "Database Management Systems"
    assert validated.session_name == "Final Examination"
