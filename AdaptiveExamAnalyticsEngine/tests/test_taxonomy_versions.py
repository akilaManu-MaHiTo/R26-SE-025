from copy import deepcopy
from types import SimpleNamespace

import pytest
from pymongo.errors import DuplicateKeyError

from app.db import repository


class Collection:
    def __init__(self):
        self.doc = None

    async def find_one(self, query, projection=None):
        return deepcopy(self.doc)

    async def insert_one(self, doc):
        if self.doc is not None:
            raise DuplicateKeyError("already exists")
        self.doc = deepcopy(doc)

    async def replace_one(self, query, doc, **kwargs):
        matches = self.doc is not None and self.doc["version"] == query.get("version")
        if matches:
            self.doc = deepcopy(doc)
        return SimpleNamespace(matched_count=int(matches))

    async def update_one(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_taxonomy_keeps_old_versions_and_rejects_stale_save():
    db = {"course_taxonomies": Collection(), "courses": Collection()}
    old = {"sql": {"canonical_topic": "SQL", "aliases": [], "subtopics": []}}
    new = {"sql": {"canonical_topic": "SQL queries", "aliases": [], "subtopics": []}}
    await repository.upsert_course_taxonomy(db, "IT2040", old)
    await repository.upsert_course_taxonomy(db, "IT2040", new, expected_version=1)
    saved = await repository.get_course_taxonomy(db, "IT2040")
    assert saved["version"] == 2
    assert saved["topics"] == new
    assert saved["history"][0]["version"] == 1
    assert saved["history"][0]["topics"] == old
    with pytest.raises(repository.TaxonomyVersionConflict):
        await repository.upsert_course_taxonomy(db, "IT2040", old, expected_version=1)
    assert (await repository.get_course_taxonomy(db, "IT2040"))["topics"] == new


@pytest.mark.asyncio
async def test_first_edit_preserves_existing_legacy_version():
    db = {"course_taxonomies": Collection(), "courses": Collection()}
    db["course_taxonomies"].doc = {"course_code": "IT2040", "version": 5, "topics": {"old": {}}, "created_at": "original"}
    await repository.upsert_course_taxonomy(db, "IT2040", {"new": {}}, expected_version=5)
    saved = await repository.get_course_taxonomy(db, "IT2040")
    assert saved["version"] == 6
    assert saved["history"][0]["version"] == 5
    assert saved["history"][0]["topics"] == {"old": {}}


@pytest.mark.asyncio
async def test_taxonomy_api_saves_history_and_rejects_conflicts():
    import httpx
    from app.api.deps import get_db
    from app.main import app

    db = {"course_taxonomies": Collection(), "courses": Collection()}
    db["courses"].doc = {"code": "CS3010"}
    topics = {"scheduling": {"canonical_topic": "Scheduling", "aliases": ["FCFS"], "subtopics": []}}
    await repository.upsert_course_taxonomy(db, "CS3010", topics)
    app.dependency_overrides[get_db] = lambda: db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            url = "/api/courses/CS3010/taxonomy"
            changed = deepcopy(topics)
            changed["scheduling"]["aliases"] = ["FCFS", "Round robin"]
            saved = await client.put(url, json={"version": 1, "topics": changed})
            assert saved.status_code == 200, saved.text
            assert saved.json()["version"] == 2
            assert "history" not in saved.json()
            conflict = await client.put(url, json={"version": 1, "topics": topics})
            assert conflict.status_code == 409
            old = await client.get(url + "/history/1")
            assert old.json()["topics"] == topics
            latest = await client.get(url)
            assert latest.json()["topics"] == changed
            history = await client.get(url + "/history")
            assert [item["version"] for item in history.json()] == [2, 1]
            missing = await client.get(url + "/history/99")
            assert missing.status_code == 404
            changed["scheduling"]["canonical_topic"] = ""
            invalid = await client.put(url, json={"version": 2, "topics": changed})
            assert invalid.status_code == 400
            assert (await client.get(url)).json()["version"] == 2
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_concurrent_save_does_not_replace_newer_version():
    class RacingCollection(Collection):
        async def replace_one(self, query, doc, **kwargs):
            self.doc["version"] += 1
            return await super().replace_one(query, doc, **kwargs)

    db = {"course_taxonomies": RacingCollection(), "courses": Collection()}
    await repository.upsert_course_taxonomy(db, "CS3010", {"old": {}})
    with pytest.raises(repository.TaxonomyVersionConflict):
        await repository.upsert_course_taxonomy(db, "CS3010", {"new": {}}, expected_version=1)
    assert (await repository.get_course_taxonomy(db, "CS3010"))["topics"] == {"old": {}}


@pytest.mark.asyncio
async def test_reanalysis_reloads_taxonomy_from_database(monkeypatch):
    from app.api import lecturer
    from app.taxonomy import normalizer
    from tests.test_exam_analytics import exam_document

    normalizer.reload_cache()
    normalizer._cache["CS3010"] = {"topic": {"canonical_topic": "Old topic"}}

    async def current_taxonomy(db, code):
        return {"topics": {"topic": {"canonical_topic": "Updated topic"}}, "version": 2}

    async def compute(db, code, *args, **kwargs):
        topics = await normalizer.load_taxonomy(db, code)
        document = exam_document()
        document["question_performance"][0]["topic"] = topics["topic"]["canonical_topic"]
        return document

    monkeypatch.setattr(repository, "get_course_taxonomy", current_taxonomy)
    monkeypatch.setattr(lecturer, "compute_exam_analytics", compute)
    try:
        result = await lecturer.lecturer_exam_reanalyse("CS3010", "Final Examination", 2022, 7, 1, db={})
        assert result.question_performance[0].topic == "Updated topic"
    finally:
        normalizer.reload_cache()
