import httpx
import pytest
from fastapi import FastAPI


def test_search_route_registered_on_standalone_app():
    from app.main import app
    assert "/api/lecturers/materials/search" in app.openapi()["paths"]


@pytest.fixture
def api(tmp_path, monkeypatch):
    from app.api.course_rag import router
    from app.config import settings
    from Gradex_AI_Server.app import session_auth
    monkeypatch.setattr(settings, "course_rag_index", str(tmp_path / "index.sqlite3"))
    application = FastAPI()
    session_auth.setup_auth(application)
    application.include_router(router, prefix="/api")
    return application


async def test_search_requires_lecturer_session(api, monkeypatch):
    from Gradex_AI_Server.app import session_auth
    headers = {"Origin": "http://test"}
    payload = {"course_code": "IT2040", "query": "normalization"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        assert (await client.post("/api/lecturers/materials/search", json=payload, headers=headers)).status_code == 401
        async def student(connection):
            return {"email": "s@example.test", "role": "student", "student_id": "S1"}
        monkeypatch.setattr(session_auth, "session_user", student)
        assert (await client.post("/api/lecturers/materials/search", json=payload, headers=headers)).status_code == 403
        async def lecturer(connection):
            return {"email": "l@example.test", "role": "lecturer"}
        monkeypatch.setattr(session_auth, "session_user", lecturer)
        response = await client.post("/api/lecturers/materials/search", json=payload, headers=headers)
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        assert response.json()["sources"] == []
        assert (await client.post("/api/lecturers/materials/search", json={**payload, "limit": 100}, headers=headers)).status_code == 422


async def test_search_returns_actual_page_citations(api, tmp_path, monkeypatch):
    from app.config import settings
    from app.services.course_rag import CourseRag
    from tests.test_course_rag import pdf
    from Gradex_AI_Server.app import session_auth
    monkeypatch.setattr(settings, "embedding_available", False)
    async def lecturer(connection):
        return {"email": "l@example.test", "role": "lecturer"}
    monkeypatch.setattr(session_auth, "session_user", lecturer)
    CourseRag(settings.course_rag_index, semantic=False).index_pdf(
        pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant facts from database relations."), "IT2040", "lecture", 2024)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://test") as client:
        response = await client.post("/api/lecturers/materials/search", headers={"Origin": "http://test"}, json={
            "course_code": "it2040", "query": "normalization", "document_types": ["lecture"], "limit": 1})
    assert response.status_code == 200
    source = response.json()["sources"][0]
    assert (source["course_code"], source["filename"], source["page_number"], source["year"]) == (
        "IT2040", "Lecture.pdf", 1, 2024)
