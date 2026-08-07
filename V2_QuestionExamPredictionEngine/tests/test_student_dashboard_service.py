from datetime import datetime, timezone

import pytest

from app.db.repository import insert_attempts, save_run
from app.schemas.student import StudentDashboard
from app.services import student_dashboard
from app.services.student_dashboard import StudentDashboardNotFound, build_student_dashboard
from tests.fixtures.fixture_data import COURSE, expected_attempt_records

FAKE_RUN = "run-fixture"


async def _seed(test_db):
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


async def test_build_dashboard_returns_full_dashboard(test_db):
    await _seed(test_db)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN)
    assert isinstance(dash, StudentDashboard)
    assert dash.student_key == "stu-001"
    assert dash.course_code == COURSE
    assert len(dash.exams) == 2
    assert len(dash.bloom_skills) == 6
    assert len(dash.topic_skills) == 8
    assert dash.weakest_topics
    assert dash.recommendations
    assert all(r.source == "deterministic" for r in dash.recommendations)
    assert "topics" in dash.cohort_comparison


async def test_build_dashboard_resolves_latest_run(test_db):
    await _seed(test_db)
    dash = await build_student_dashboard(test_db, "stu-001")
    assert dash.run_id == FAKE_RUN


async def test_build_dashboard_unknown_student_raises(test_db):
    await _seed(test_db)
    with pytest.raises(StudentDashboardNotFound):
        await build_student_dashboard(test_db, "nobody", run_id=FAKE_RUN)


async def test_build_dashboard_llm_failure_falls_back_to_deterministic(test_db, monkeypatch):
    await _seed(test_db)

    async def raise_unavailable(*a, **k):
        raise Exception("ollama down")

    monkeypatch.setattr(student_dashboard, "study_actions", raise_unavailable)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN, include_llm=True)
    assert all(r.source == "deterministic" for r in dash.recommendations)


async def test_build_dashboard_llm_ok_uses_llm_source(test_db, monkeypatch):
    await _seed(test_db)

    class FakeActions:
        def model_dump(self):
            return {
                "student_key": "stu-001",
                "actions": [
                    {"action": "review", "topic": "Schema Refinement", "rationale": "r", "practice_topics": ["joins"]}
                ],
            }

    async def fake_study_actions(student_key, weak_topics, evidence):
        return {"status": "ok", **FakeActions().model_dump()}

    monkeypatch.setattr(student_dashboard, "study_actions", fake_study_actions)
    dash = await build_student_dashboard(test_db, "stu-001", run_id=FAKE_RUN, include_llm=True)
    assert dash.recommendations[0].source == "llm"