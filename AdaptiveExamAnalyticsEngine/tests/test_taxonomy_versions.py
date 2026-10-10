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
