import httpx
import pytest

from app.api import deps
from app.db.repository import upsert_exam_analytics
from app.main import app
from tests.test_exam_analytics import exam_document


async def test_recommendations_endpoint_returns_ranked_questions(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        await upsert_exam_analytics(test_db, exam_document())
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/lecturers/exams/IT2040/Final%20Examination/recommendations?limit=5"
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exam_id"] == "IT2040@Final Examination"
        assert "weakness_scores" in data
        assert "recommendations" in data
        assert len(data["recommendations"]) <= 5
        # each rec has scoring fields
        for r in data["recommendations"]:
            assert "recommendation_score" in r
            assert "priority" in r
            assert "canonical_topic" in r
            assert "reason" in r
        # grouped buckets
        assert "high_priority" in data
        assert "medium_priority" in data
    finally:
        app.dependency_overrides.clear()
        await test_db["analytics_snapshots"].delete_many({})


async def test_recommendations_404_without_analytics(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/lecturers/exams/SE9999/Final/recommendations"
            )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.clear()
