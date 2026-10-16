import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from app.api import deps
from app.api.taxonomy import router
from Gradex_AI_Server.app.auth import require_lecturer
from pymongo.errors import DuplicateKeyError, PyMongoError

app = FastAPI()
app.include_router(router)


@pytest.fixture
def course_collection():
    from bson import ObjectId
    from types import SimpleNamespace

    collection = MagicMock()
    collection.create_index = AsyncMock()
    collection.insert_one = AsyncMock(return_value=SimpleNamespace(inserted_id=ObjectId()))
    app.dependency_overrides[deps.get_db] = lambda: {"courses": collection}
    app.dependency_overrides[require_lecturer] = lambda: None
    yield collection
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_course_preserves_collection_schema(course_collection):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/courses", json={"code": " it2050 ", "name": " New Course ", "description": ""})
    assert response.status_code == 201, response.text
    assert response.json() == {
        "_id": str(course_collection.insert_one.return_value.inserted_id),
        "code": "IT2050", "name": "New Course", "description": "",
    }
    course_collection.insert_one.assert_awaited_once_with({"code": "IT2050", "name": "New Course", "description": ""})
    course_collection.create_index.assert_awaited_once_with("code", unique=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("field,value", [("code", " "), ("name", " ")])
async def test_create_course_rejects_blank_required_fields(course_collection, field, value):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/courses", json={"code": "IT2050", "name": "New Course", field: value})
    assert response.status_code == 422
    course_collection.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_duplicate_course_does_not_overwrite(course_collection):
    course_collection.insert_one.side_effect = DuplicateKeyError("duplicate")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/courses", json={"code": "IT2040", "name": "Duplicate"})
    assert response.status_code == 409
    course_collection.update_one.assert_not_called()


@pytest.mark.asyncio
async def test_create_course_requires_login(course_collection):
    app.dependency_overrides.pop(require_lecturer)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/courses", json={"code": "IT2050", "name": "New Course"})
    assert response.status_code == 401
    course_collection.insert_one.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_course_database_failure_is_safe(course_collection):
    course_collection.insert_one.side_effect = PyMongoError("private connection details")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/courses", json={"code": "IT2050", "name": "New Course"})
    assert response.status_code == 503
    assert "private" not in response.text

@pytest.mark.asyncio
async def test_list_taxonomy_courses_uses_analytics_database():
    from bson import ObjectId

    course_id = ObjectId()
    cursor = MagicMock()
    cursor.sort.return_value = cursor
    cursor.to_list = AsyncMock(return_value=[{
        "_id": course_id, "code": "IT2040", "name": "Database Management Systems",
    }])
    courses = MagicMock()
    courses.find.return_value = cursor
    db = {"courses": courses}
    app.dependency_overrides[deps.get_db] = lambda: db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/courses")
        assert response.status_code == 200, response.text
        assert response.json()["items"] == [{
            "_id": str(course_id), "code": "IT2040", "name": "Database Management Systems",
        }]
        cursor.sort.assert_called_once_with("code", 1)
    finally:
        app.dependency_overrides.clear()



