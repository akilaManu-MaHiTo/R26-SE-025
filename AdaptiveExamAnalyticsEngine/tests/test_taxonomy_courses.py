import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI
from app.api import deps
from app.api.taxonomy import router

app = FastAPI()
app.include_router(router)

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



