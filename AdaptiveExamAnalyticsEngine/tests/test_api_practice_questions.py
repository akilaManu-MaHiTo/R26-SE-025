import httpx

from app.api import deps
from app.main import app


async def test_practice_post_returns_generated_questions(test_db, monkeypatch):
    from app.schemas.student import StudentAnalyticsDocument

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        async def fake_ensure(db, student_id, course_code, session_name):
            return StudentAnalyticsDocument.model_validate(valid_document())

        async def fake_generate(db, student_id, course_code, session_name, strategy):
            return {"status": "ok", "document": {"questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}]}}

        from app.api import dashboard as dashboard_api
        from tests.test_api_dashboard import valid_document

        monkeypatch.setattr(dashboard_api, "ensure_student_analytics", fake_ensure)
        monkeypatch.setattr(dashboard_api, "generate_practice_questions", fake_generate)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/students/IT22145976/practice-questions?course_code=IT2040&session_name=Final%20Examination%202021"
            )
        assert response.status_code == 200
        assert response.json()["questions"][0]["topic"] == "SQL"
    finally:
        app.dependency_overrides.clear()


async def test_practice_post_returns_503_when_generation_degrades(
    test_db, monkeypatch
):
    from app.schemas.student import StudentAnalyticsDocument

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        async def fake_ensure(db, student_id, course_code, session_name):
            return StudentAnalyticsDocument.model_validate(valid_document())

        async def fake_generate(db, student_id, course_code, session_name, strategy):
            return {"status": "degraded", "reason": "qwen_unavailable"}

        from app.api import dashboard as dashboard_api
        from tests.test_api_dashboard import valid_document

        monkeypatch.setattr(dashboard_api, "ensure_student_analytics", fake_ensure)
        monkeypatch.setattr(dashboard_api, "generate_practice_questions", fake_generate)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/students/IT22145976/practice-questions?course_code=IT2040&session_name=Final%20Examination%202021"
            )
        assert response.status_code == 503
        assert response.json()["detail"]["reason"] == "qwen_unavailable"
        assert response.json()["detail"]["target"]["recommended_topics"] == ["Testing"]
    finally:
        app.dependency_overrides.clear()


async def test_practice_get_returns_cached_batch_when_not_fresh(test_db):
    from app.db.repository import upsert_generated_questions

    cached_document = {
        "student_id": "IT22145976",
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Databases"},
        "request": {"recommended_topics": ["SQL"]},
        "questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}],
        "generated_at": "2026-08-12T00:00:00Z",
        "generation_version": "1.0",
    }
    await upsert_generated_questions(test_db, cached_document)
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/students/IT22145976/practice-questions",
                params={
                    "course_code": "IT2040",
                    "session_name": "Final Examination 2021",
                    "fresh": "false",
                },
            )
        assert response.status_code == 200
        assert response.json()["questions"][0]["topic"] == "SQL"
        assert response.json()["exam_id"] == "IT2040@Final Examination 2021"
    finally:
        app.dependency_overrides.clear()
        await test_db["generatedQuestions"].delete_many({"student_id": "IT22145976"})


async def test_practice_get_regenerates_when_no_cache(test_db, monkeypatch):
    from app.schemas.student import StudentAnalyticsDocument

    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        async def fake_ensure(db, student_id, course_code, session_name):
            return StudentAnalyticsDocument.model_validate(valid_document())

        async def fake_generate(db, student_id, course_code, session_name, strategy):
            return {"status": "ok", "document": {"questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}]}}

        from app.api import dashboard as dashboard_api
        from tests.test_api_dashboard import valid_document

        monkeypatch.setattr(dashboard_api, "ensure_student_analytics", fake_ensure)
        monkeypatch.setattr(dashboard_api, "generate_practice_questions", fake_generate)

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/students/IT22145976/practice-questions",
                params={
                    "course_code": "IT2040",
                    "session_name": "Final Examination 2021",
                    "fresh": "true",
                },
            )
        assert response.status_code == 200
        assert response.json()["questions"][0]["topic"] == "SQL"
    finally:
        app.dependency_overrides.clear()