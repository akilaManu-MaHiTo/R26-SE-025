"""Task 3 TDD: Taxonomy CRUD API mocked tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.api import deps


@pytest.mark.asyncio
async def test_get_upsert_delete_taxonomy():
    """Brief mocked test — GET/PUT/DELETE mocked via repository patches."""
    mock_db = MagicMock()
    mock_courses = AsyncMock()
    mock_courses.find_one = AsyncMock(return_value={"code": "CS3010"})
    # route db["..."] calls
    def _getitem(name):
        if name == "courses":
            return mock_courses
        # fallback for course_taxonomies direct find (seed fallback)
        m = AsyncMock()
        m.find_one = AsyncMock(return_value=None)
        return m
    mock_db.__getitem__.side_effect = _getitem

    # patch repository helpers used inside router
    with patch("app.db.repository.get_course_taxonomy", new=AsyncMock(side_effect=[
        None,  # GET: no taxonomy yet -> version 0
        None,  # PUT: no existing doc
    ])), patch("app.db.repository.upsert_course_taxonomy", new=AsyncMock(return_value={
        "course_code": "CS3010",
        "topics": {"process_scheduling": {"canonical_topic": "Process Scheduling", "aliases": ["Sched"], "subtopics": ["FCFS"]}},
        "version": 1,
        "updated_at": "2026-09-16T00:00:00+00:00",
    })), patch("app.db.repository.find_taxonomy_usage_count", new=AsyncMock(return_value=0)), \
         patch("app.db.repository.seed_it2040_if_empty", new=AsyncMock(return_value=None)), \
          patch("app.api.taxonomy.invalidate_taxonomy_cache", new=AsyncMock(return_value=None)):

        app.dependency_overrides[deps.get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.get("/api/courses/CS3010/taxonomy")
                # GET should return 200 with version 0 empty topics
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["course_code"] == "CS3010"
                assert body["version"] == 0
                assert body["topics"] == {}

                # PUT new topic via slug "new" -> slugified
                resp2 = await ac.put("/api/courses/CS3010/taxonomy/new", json={
                    "canonical_topic": "Process Scheduling",
                    "aliases": ["Sched"],
                    "subtopics": ["FCFS"]
                })
                assert resp2.status_code == 200, resp2.text
                body2 = resp2.json()
                assert body2["canonical_id"] == "process_scheduling"
                assert body2["version"] == 1
                assert body2["topic"]["canonical_topic"] == "Process Scheduling"
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_404_when_course_missing():
    mock_db = MagicMock()
    mock_courses = AsyncMock()
    mock_courses.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = mock_courses
    # ensure any other collection returns dummy
    mock_db.__getitem__.side_effect = lambda name: mock_courses if name == "courses" else AsyncMock()

    app.dependency_overrides[deps.get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/courses/CS9999/taxonomy")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_put_version_conflict_409():
    mock_db = MagicMock()
    mock_courses = AsyncMock()
    mock_courses.find_one = AsyncMock(return_value={"code": "CS3010"})
    mock_db.__getitem__.side_effect = lambda name: mock_courses if name == "courses" else AsyncMock()

    with patch("app.db.repository.get_course_taxonomy", new=AsyncMock(return_value={
        "course_code": "CS3010",
        "topics": {},
        "version": 5,
        "updated_at": "2026-09-16T00:00:00+00:00",
    })), patch("app.api.taxonomy.invalidate_taxonomy_cache", new=AsyncMock()):
        app.dependency_overrides[deps.get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.put("/api/courses/CS3010/taxonomy/new",
                    headers={"If-Match": "1"},
                    json={"canonical_topic": "Process Scheduling", "aliases": [], "subtopics": []})
                assert resp.status_code == 409
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_delete_warns_when_used():
    mock_db = MagicMock()
    mock_courses = AsyncMock()
    mock_courses.find_one = AsyncMock(return_value={"code": "CS3010"})
    mock_db.__getitem__.side_effect = lambda name: mock_courses if name == "courses" else AsyncMock()

    with patch("app.db.repository.get_course_taxonomy", new=AsyncMock(return_value={
        "course_code": "CS3010",
        "topics": {"process_scheduling": {"canonical_topic": "Process Scheduling", "aliases": [], "subtopics": []}},
        "version": 1,
        "updated_at": "2026-09-16T00:00:00+00:00",
    })), patch("app.db.repository.find_taxonomy_usage_count", new=AsyncMock(return_value=3)), \
         patch("app.db.repository.upsert_course_taxonomy", new=AsyncMock(return_value={
             "course_code": "CS3010", "topics": {}, "version": 2, "updated_at": "2026-09-16T01:00:00+00:00"
         })), patch("app.api.taxonomy.invalidate_taxonomy_cache", new=AsyncMock()):
        app.dependency_overrides[deps.get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.delete("/api/courses/CS3010/taxonomy/process_scheduling")
                assert resp.status_code == 200, resp.text
                body = resp.json()
                assert body["deleted"] is True
                assert body["warning"] is not None
                assert "3" in body["warning"]
                assert body["version"] == 2
        finally:
            app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_seed_only_it2040_400():
    mock_db = MagicMock()
    app.dependency_overrides[deps.get_db] = lambda: mock_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post("/api/courses/CS3010/taxonomy/seed")
            assert resp.status_code == 400
    finally:
        app.dependency_overrides.clear()

    # IT2040 success path
    with patch("app.db.repository.seed_it2040_if_empty", new=AsyncMock(return_value={
        "course_code": "IT2040", "topics": {"sql": {"canonical_topic": "SQL", "aliases": [], "subtopics": []}}, "version": 1, "updated_at": "2026-09-16T00:00:00+00:00"
    })):
        app.dependency_overrides[deps.get_db] = lambda: mock_db
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                resp = await ac.post("/api/courses/IT2040/taxonomy/seed")
                assert resp.status_code == 200, resp.text
                assert resp.json()["course_code"] == "IT2040"
        finally:
            app.dependency_overrides.clear()
