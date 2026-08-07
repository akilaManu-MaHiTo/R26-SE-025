from datetime import datetime, timezone

import httpx

from app.api import deps
from app.db.repository import insert_attempts, save_run
from app.main import app
from tests.fixtures.fixture_data import COURSE, expected_attempt_records

FAKE_RUN = "run-fixture"


async def test_dashboard_endpoint_happy_path(test_db):
    await insert_attempts(test_db, expected_attempt_records)
    await save_run(
        test_db,
        {
            "run_id": FAKE_RUN,
            "course_code": COURSE,
            "exam_id": "exam-2023",
            "status": "ready",
            "created_at": datetime.now(timezone.utc),
        },
    )

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/api/students/stu-001/dashboard?run_id={FAKE_RUN}")
        assert response.status_code == 200
        body = response.json()
        assert body["student_key"] == "stu-001"
        assert len(body["exams"]) == 2
        assert body["recommendations"][0]["source"] == "deterministic"
    finally:
        app.dependency_overrides.clear()
        await test_db["question_attempts"].delete_many({"analysis_run_id": FAKE_RUN})
        await test_db["analysis_runs"].delete_many({"run_id": FAKE_RUN})


async def test_dashboard_endpoint_unknown_student_404(test_db):
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/students/nobody/dashboard?run_id=run-fixture")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
