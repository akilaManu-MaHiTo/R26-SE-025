from fastapi import FastAPI
from fastapi.testclient import TestClient

import Gradex_AI_Server.app.predict_api as predict_api
from Gradex_AI_Server.app.predict_api import router


def _make_client(monkeypatch) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[predict_api.get_db] = lambda: None
    return TestClient(app)


def test_exam_recommendations_ok(monkeypatch):
    async def fake_run(db):
        return "run-1"

    async def fake_find(db, run_id):
        return [
            {
                "topic": "SQL",
                "bloom_level": "Apply",
                "question_type": "problem_solving",
                "mark_range": [1.0, 4.0],
                "priority_score": 0.9,
                "component_breakdown": {"weakness": 0.8},
                "evidence": {"mastery": 0.4},
            }
        ]

    class FakeRunCollection:
        async def find_one(self, *args, **kwargs):
            return {"course_code": "SE2032", "exam_id": "e1"}

    class FakeDb:
        def __getitem__(self, key):
            return FakeRunCollection()

    monkeypatch.setattr(predict_api, "latest_run_id", fake_run)
    monkeypatch.setattr(predict_api, "find_recommendations", fake_find)
    db = FakeDb()

    client = _make_client(monkeypatch)
    client.app.dependency_overrides[predict_api.get_db] = lambda: db
    response = client.get("/api/predict/exam-recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["run_id"] == "run-1"
    assert body["recommendations"][0]["topic"] == "SQL"
    assert body["recommendations"][0]["priority_score"] == 0.9


def test_exam_recommendations_no_run(monkeypatch):
    async def fake_run(db):
        return None

    monkeypatch.setattr(predict_api, "latest_run_id", fake_run)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/exam-recommendations")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_run"
    assert body["recommendations"] == []


def test_student_dashboard_ok(monkeypatch):
    async def fake_build(db, student_key, run_id, include_llm):
        return {
            "student_key": student_key,
            "weakest_topics": ["SQL"],
            "recommendations": [{"action": "Review SQL", "topic": "SQL", "source": "deterministic"}],
        }

    monkeypatch.setattr(predict_api, "build_student_dashboard", fake_build)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/students/stu-001/dashboard")
    assert response.status_code == 200
    body = response.json()
    assert body["student_key"] == "stu-001"
    assert body["recommendations"][0]["action"] == "Review SQL"


def test_student_dashboard_not_found(monkeypatch):
    async def fake_build(db, student_key, run_id, include_llm):
        raise predict_api.StudentDashboardNotFound("no attempts found for student")

    monkeypatch.setattr(predict_api, "build_student_dashboard", fake_build)
    client = _make_client(monkeypatch)
    response = client.get("/api/predict/students/nobody/dashboard")
    assert response.status_code == 404