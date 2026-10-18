import json as _json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_course_taxonomies_in_collections():
    from app.db.repository import COLLECTIONS, _UNIQUE_INDEXES

    assert "course_taxonomies" in COLLECTIONS
    assert ("course_code", 1) in _UNIQUE_INDEXES["course_taxonomies"]


@pytest.mark.asyncio
async def test_upsert_inc_version_creates_v1():
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value=None)
    mock_tax.replace_one = AsyncMock()
    mock_courses = AsyncMock()
    mock_courses.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "course_taxonomies": mock_tax,
        "courses": mock_courses,
    }.get(name, MagicMock())

    doc = await repository.upsert_course_taxonomy(
        mock_db, "CS3010", {"os": {"canonical_topic": "OS", "aliases": [], "subtopics": []}}, updated_by="lecturer@x"
    )
    assert doc["version"] == 1
    assert doc["course_code"] == "CS3010"
    mock_tax.find_one.assert_called_once_with({"course_code": "CS3010"})
    mock_tax.insert_one.assert_called_once()
    # ensure replace_one called with normalized code
    assert mock_tax.insert_one.call_args[0][0]["course_code"] == "CS3010"


@pytest.mark.asyncio
async def test_upsert_inc_version_increments_1_to_2():
    from app.db import repository

    existing = {
        "course_code": "CS3010",
        "topics": {"os": {"canonical_topic": "OS", "aliases": [], "subtopics": []}},
        "version": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value=existing)
    mock_tax.replace_one = AsyncMock()
    mock_courses = AsyncMock()
    mock_courses.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "course_taxonomies": mock_tax,
        "courses": mock_courses,
    }.get(name, MagicMock())

    doc = await repository.upsert_course_taxonomy(
        mock_db, "CS3010", {"os": {"canonical_topic": "OS2", "aliases": [], "subtopics": []}}, updated_by="lecturer@y"
    )
    assert doc["version"] == 2
    assert doc["created_at"] == existing["created_at"]
    assert doc["course_code"] == "CS3010"
    mock_courses.update_one.assert_called_once_with(
        {"code": "CS3010"}, {"$set": {"taxonomy_version": 2, "taxonomy_updated_at": doc["updated_at"]}}
    )


@pytest.mark.asyncio
async def test_upsert_normalizes_course_code():
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value=None)
    mock_tax.replace_one = AsyncMock()
    mock_courses = AsyncMock()
    mock_courses.update_one = AsyncMock()
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: {
        "course_taxonomies": mock_tax,
        "courses": mock_courses,
    }.get(name, MagicMock())

    doc = await repository.upsert_course_taxonomy(mock_db, " cs3010 ", {"a": {}}, updated_by="u")
    assert doc["course_code"] == "CS3010"
    mock_tax.find_one.assert_called_with({"course_code": "CS3010"})
    mock_tax.insert_one.assert_called_with({"_id": "CS3010", **doc})
    mock_courses.update_one.assert_called_with({"code": "CS3010"}, {"$set": {"taxonomy_version": 1, "taxonomy_updated_at": doc["updated_at"]}})


@pytest.mark.asyncio
async def test_get_course_taxonomy_normalizes_and_returns():
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value={"course_code": "CS3010", "topics": {}, "version": 1})
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_tax

    doc = await repository.get_course_taxonomy(mock_db, " cs3010 ")
    assert doc["course_code"] == "CS3010"
    mock_tax.find_one.assert_called_once_with({"course_code": "CS3010"}, {"_id": 0})


@pytest.mark.asyncio
async def test_get_course_taxonomy_returns_none_when_missing():
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value=None)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_tax

    doc = await repository.get_course_taxonomy(mock_db, "IT9999")
    assert doc is None
    mock_tax.find_one.assert_called_once_with({"course_code": "IT9999"}, {"_id": 0})


@pytest.mark.asyncio
async def test_seed_it2040_if_empty_returns_none_when_exists():
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value={"course_code": "IT2040", "version": 1})
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_tax

    result = await repository.seed_it2040_if_empty(mock_db)
    assert result is None
    mock_tax.find_one.assert_called_once_with({"course_code": "IT2040"})


@pytest.mark.asyncio
async def test_seed_it2040_if_empty_calls_upsert_when_empty(monkeypatch):
    from app.db import repository

    mock_tax = AsyncMock()
    mock_tax.find_one = AsyncMock(return_value=None)
    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = lambda name: mock_tax if name == "course_taxonomies" else MagicMock()

    # Mock file system: make _Path return a fake path that exists and has json content
    fake_path = MagicMock()
    fake_path.exists.return_value = True
    fake_path.read_text.return_value = _json.dumps({"seed_topic": {"canonical_topic": "Seed", "aliases": [], "subtopics": []}})
    fake_path.__truediv__.return_value = fake_path
    mock_path_obj = MagicMock()
    mock_path_obj.resolve.return_value = mock_path_obj
    mock_path_obj.parents = [fake_path, fake_path, fake_path]
    mock_path_obj.__truediv__.return_value = fake_path

    monkeypatch.setattr(repository, "_Path", MagicMock(return_value=mock_path_obj))
    # Also need to ensure _json is real json but loads works
    mock_upsert = AsyncMock(return_value={"course_code": "IT2040", "version": 1, "topics": {}})
    monkeypatch.setattr(repository, "upsert_course_taxonomy", mock_upsert)

    result = await repository.seed_it2040_if_empty(mock_db)
    assert result is not None
    mock_upsert.assert_called_once()
    call_args = mock_upsert.call_args
    assert call_args[0][1] == "IT2040" or call_args[0][0] == mock_db and call_args[0][1] == "IT2040"
    # verify upsert called with IT2040 and seed data
    assert "IT2040" in str(call_args)


@pytest.mark.asyncio
async def test_find_taxonomy_usage_count_counts_case_insensitive():
    from app.db import repository

    docs = [
        {"canonical_topic_performance": [{"topic": "OS"}, {"topic": "os"}, {"topic": "DBMS"}]},
        {"canonical_topic_performance": [{"topic": "Os"}]},
        {"canonical_topic_performance": []},
        {},
    ]
    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    mock_analytics = MagicMock()
    mock_analytics.find = MagicMock(return_value=mock_cursor)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_analytics

    count = await repository.find_taxonomy_usage_count(mock_db, "CS3010", "os")
    assert count == 3  # OS/os/Os
    mock_analytics.find.assert_called_once_with({"subject_code": "CS3010"})


@pytest.mark.asyncio
async def test_find_taxonomy_usage_count_normalizes_course_code():
    from app.db import repository

    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_analytics = MagicMock()
    mock_analytics.find = MagicMock(return_value=mock_cursor)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_analytics

    await repository.find_taxonomy_usage_count(mock_db, " cs3010 ", " os ")
    mock_analytics.find.assert_called_once_with({"subject_code": "CS3010"})


@pytest.mark.asyncio
async def test_find_taxonomy_usage_count_handles_mismatched_shape():
    from app.db import repository

    docs = [
        {"canonical_topic_performance": None},
        {"canonical_topic_performance": "not-a-list"},
        {"canonical_topic_performance": [{"topic": None}, {"no_topic": "OS"}, "string", 123]},
        {"canonical_topic_performance": [{"topic": "  OS  "}]},  # whitespace handling
    ]
    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    mock_analytics = MagicMock()
    mock_analytics.find = MagicMock(return_value=mock_cursor)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_analytics

    count = await repository.find_taxonomy_usage_count(mock_db, "CS3010", "os")
    assert count == 1  # only the last doc matches after strip+casefold


@pytest.mark.asyncio
async def test_find_taxonomy_usage_count_returns_zero_when_no_match():
    from app.db import repository

    docs = [
        {"canonical_topic_performance": [{"topic": "DBMS"}, {"topic": "Networks"}]},
    ]
    mock_cursor = AsyncMock()
    mock_cursor.to_list = AsyncMock(return_value=docs)
    mock_analytics = MagicMock()
    mock_analytics.find = MagicMock(return_value=mock_cursor)
    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_analytics

    count = await repository.find_taxonomy_usage_count(mock_db, "CS3010", "os")
    assert count == 0
