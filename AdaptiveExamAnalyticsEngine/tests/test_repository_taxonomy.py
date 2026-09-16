import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_course_taxonomies_in_collections():
    from app.db.repository import COLLECTIONS, _UNIQUE_INDEXES
    assert "course_taxonomies" in COLLECTIONS
    assert ("course_code", 1) in _UNIQUE_INDEXES["course_taxonomies"]


@pytest.mark.asyncio
async def test_upsert_inc_version(monkeypatch):
    from app.db import repository
    mock_db = MagicMock()
    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.replace_one = AsyncMock()
    mock_col.find_one = AsyncMock(side_effect=[None, {"course_code": "CS3010", "topics": {"os": {"canonical_topic": "OS", "aliases": [], "subtopics": []}}, "version": 1}])
    mock_db.__getitem__.return_value = mock_col
    doc = await repository.upsert_course_taxonomy(mock_db, "CS3010", {"os": {"canonical_topic": "OS", "aliases": [], "subtopics": []}}, updated_by="lecturer@x")
    assert doc["version"] == 1
