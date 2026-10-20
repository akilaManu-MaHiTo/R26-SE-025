import httpx
import pytest
from fastapi import FastAPI
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.api import dashboard, course_rag as material_routes
from app.api.deps import get_db
from app.schemas.course_rag import MaterialDocument, MaterialInventory
from Gradex_AI_Server.app import session_auth


@pytest.fixture
def study_api(monkeypatch):
    app = FastAPI()
    session_auth.setup_auth(app)
    app.include_router(dashboard.router, prefix="/api")
    app.dependency_overrides[get_db] = lambda: object()

    async def student(connection):
        return {"email": "s@example.test", "role": "student", "student_id": "S1"}

    async def exams(db, student_id):
        return [{"subject_code": "IT2040"}]

    monkeypatch.setattr(session_auth, "session_user", student)
    monkeypatch.setattr(dashboard, "list_exams_for_student", exams)
    return app


async def test_students_can_only_read_own_course_lectures_and_tutorials(study_api, monkeypatch):
    from app.services import course_rag

    def item(id, course, kind):
        return MaterialDocument(document_id=id * 24, course_code=course, document_type=kind,
                                filename=f"{kind}.pdf", pages=1, chunks=1, mode="keyword", pdf_available=True)

    items = [item("a", "IT2040", "lecture"), item("b", "IT2040", "tutorial"),
             item("c", "IT2040", "exam"), item("d", "IT9999", "lecture")]

    class Rag:
        def list_documents(self):
            return MaterialInventory(status="ok", items=items)

        def document_pdf(self, document_id):
            return b"%PDF test"

    monkeypatch.setattr(course_rag, "get_course_rag", lambda: Rag())
    monkeypatch.setattr(material_routes, "get_course_rag", lambda: Rag())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=study_api), base_url="http://test") as client:
        response = await client.get("/api/students/S1/materials")
        assert response.status_code == 200
        assert [i["document_id"] for i in response.json()["items"]] == ["a" * 24, "b" * 24]
        assert (await client.get("/api/students/S1/materials/" + "a" * 24 + "/pdf")).content == b"%PDF test"
        for id in ("c", "d", "e"):
            assert (await client.get(f"/api/students/S1/materials/{id * 24}/pdf")).status_code == 404
        assert (await client.get("/api/students/S2/materials")).status_code == 403
        assert (await client.get("/api/students/S2/materials/" + "a" * 24 + "/pdf")).status_code == 403
        assert (await client.get("/api/lecturers/materials")).status_code == 403


async def test_practice_uses_selected_exam_identity(monkeypatch):
    from types import SimpleNamespace
    from app.schemas.student import NextQuestionStrategy

    calls = []
    strategy = NextQuestionStrategy(recommended_topics=["SQL"], recommended_bloom_levels=["Apply"],
                                    recommended_difficulty="Easy", number_of_questions=5)

    async def analysis(*args):
        calls.append(args)
        return SimpleNamespace(next_question_strategy=strategy)

    async def generate(*args, **kwargs):
        return {"status": "ok", "document": {"exam_id": kwargs["exam_id"]}}

    monkeypatch.setattr(dashboard, "ensure_student_analytics", analysis)
    monkeypatch.setattr(dashboard, "generate_practice_questions", generate)
    result = await dashboard.create_practice_questions("S1", "IT2040", "Final", object(), year=2024, month=6, semester=1)
    assert calls[0][4:] == (2024, 6, 1)
    assert result["exam_id"] == "IT2040@Final@2024-6-1"


async def test_practice_cache_lookup_is_scoped_to_selected_exam(monkeypatch):
    from unittest.mock import AsyncMock

    cached = AsyncMock(return_value=None)
    create = AsyncMock(return_value={"questions": []})
    monkeypatch.setattr(dashboard, "find_generated_questions", cached)
    monkeypatch.setattr(dashboard, "create_practice_questions", create)
    db = object()
    await dashboard.get_practice_questions("S1", "IT2040", "Final", False, db, 2024, 6, 1)
    cached.assert_awaited_once_with(db, "S1", "IT2040@Final@2024-6-1")
    create.assert_awaited_once_with("S1", "IT2040", "Final", db, 2024, 6, 1)
