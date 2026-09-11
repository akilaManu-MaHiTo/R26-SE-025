"""Subject-rubric persistence (fake Mongo collection, no network).

Mirrors the FakeCol convention already used in test_viva_http.py, so this
exercises the actual upsert/merge/replace logic in subject_rubric_service.py
without touching a real Atlas cluster.

Run:
  python -m unittest Gradex_AI_Server.app.tests.test_subject_rubric_service -v
"""
from __future__ import annotations

import asyncio
import unittest

from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from Gradex_AI_Server.app.subject_rubric_service import (
    get_subject_rubric,
    replace_subject_rubric,
    upsert_subject_rubric,
)


class FakeSubjectRubricCollection:
    """In-memory stand-in for db_instance.db["subject_rubrics"], with enough
    of Mongo's real semantics (unique-index conflicts, conditional-match
    update_one, $set/$setOnInsert conflict rejection) to actually catch the
    class of bug a naive in-memory dict would silently paper over."""

    def __init__(self):
        self.docs: dict[str, dict] = {}
        self._unique_subject_code = False

    async def create_index(self, field, unique=False, **_kwargs):
        if field == "subject_code" and unique:
            self._unique_subject_code = True

    async def find_one(self, query):
        doc = self.docs.get(query.get("subject_code"))
        return dict(doc) if doc else None

    async def insert_one(self, doc):
        code = doc.get("subject_code")
        if self._unique_subject_code and code in self.docs:
            raise DuplicateKeyError(f"duplicate key: subject_code={code!r}")
        stored = {"_id": ObjectId(), **doc}
        self.docs[code] = stored

        class Result:
            inserted_id = stored["_id"]

        return Result()

    async def update_one(self, query, update, upsert=False):
        code = query.get("subject_code")
        existing = self.docs.get(code)
        set_fields = dict(update.get("$set", {}))
        set_on_insert = dict(update.get("$setOnInsert", {}))

        # Real MongoDB rejects an update where the same field path appears in
        # both $set and $setOnInsert (WriteError code 40, "would create a
        # conflict"). Enforce the same rule here so this fake actually catches
        # that class of bug instead of silently merging past it.
        conflicting = set(set_fields) & set(set_on_insert)
        if conflicting:
            raise ValueError(
                f"$set and $setOnInsert both target: {sorted(conflicting)} "
                "(MongoDB WriteError code 40 in real usage)"
            )

        # Optimistic-concurrency queries (e.g. {"subject_code": ..., "version": N})
        # must only match a document whose current version equals what the
        # caller read — otherwise this is a stale write and should report
        # matched_count=0, exactly like a real conditioned update_one would.
        if existing is not None and "version" in query and existing.get("version") != query["version"]:
            class Result:
                matched_count = 0

            return Result()

        if existing is None:
            if not upsert:
                class Result:
                    matched_count = 0

                return Result()
            new_doc = {"_id": ObjectId(), **set_on_insert, **set_fields}
            self.docs[code] = new_doc

            class Result:
                matched_count = 0
                upserted_id = new_doc["_id"]

            return Result()

        merged = {**existing, **set_fields}
        self.docs[code] = merged

        class Result:
            matched_count = 1

        return Result()


class FakeDbInstance:
    def __init__(self, collection):
        self.db = {"subject_rubrics": collection}


def _run(coro):
    return asyncio.run(coro)


def _concepts(*names):
    return [
        {"id": name.lower(), "name": name, "description": f"{name} desc", "weight": 3.0}
        for name in names
    ]


class UpsertTests(unittest.TestCase):
    def setUp(self):
        self.collection = FakeSubjectRubricCollection()
        self.db_instance = FakeDbInstance(self.collection)

    def test_get_returns_none_when_missing(self):
        result = _run(get_subject_rubric(self.db_instance, "CS999"))
        self.assertIsNone(result)

    def test_upsert_creates_new_document(self):
        rubric = _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Normalization", "Indexing")
            )
        )
        self.assertEqual(rubric["subject_code"], "CS101")
        self.assertEqual(rubric["subject_name"], "Databases")
        self.assertEqual({c["name"] for c in rubric["concepts"]}, {"Normalization", "Indexing"})
        self.assertTrue(all(c["source_file"] == "lecture1.pdf" for c in rubric["concepts"]))
        self.assertEqual([f["filename"] for f in rubric["source_files"]], ["lecture1.pdf"])
        self.assertIn("generated_at", rubric)
        self.assertIsInstance(rubric["_id"], str)

    def test_reupload_same_file_replaces_only_that_files_concepts(self):
        _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Normalization", "Indexing")
            )
        )
        _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture2.pdf", _concepts("Transactions")
            )
        )
        # Re-upload lecture1.pdf with a different concept set — its old
        # concepts should be dropped, lecture2.pdf's should be untouched.
        rubric = _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Joins")
            )
        )
        names = {c["name"] for c in rubric["concepts"]}
        self.assertEqual(names, {"Joins", "Transactions"})
        filenames = sorted(f["filename"] for f in rubric["source_files"])
        self.assertEqual(filenames, ["lecture1.pdf", "lecture2.pdf"])

    def test_dedup_by_name_case_insensitive_keeps_newest(self):
        _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Normalization")
            )
        )
        rubric = _run(
            upsert_subject_rubric(
                self.db_instance,
                "CS101",
                "Databases",
                "lecture2.pdf",
                [{"id": "normalization", "name": "normalization", "description": "updated", "weight": 5.0}],
            )
        )
        matches = [c for c in rubric["concepts"] if c["name"].lower() == "normalization"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["source_file"], "lecture2.pdf")
        self.assertEqual(matches[0]["description"], "updated")

    def test_get_after_upsert_round_trips(self):
        _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Normalization")
            )
        )
        fetched = _run(get_subject_rubric(self.db_instance, "CS101"))
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["subject_code"], "CS101")
        self.assertEqual(len(fetched["concepts"]), 1)


class ReplaceTests(unittest.TestCase):
    def setUp(self):
        self.collection = FakeSubjectRubricCollection()
        self.db_instance = FakeDbInstance(self.collection)

    def test_replace_overwrites_concepts_entirely(self):
        _run(
            upsert_subject_rubric(
                self.db_instance, "CS101", "Databases", "lecture1.pdf", _concepts("Normalization", "Indexing")
            )
        )
        curated = [{"id": "normalization", "name": "Normalization", "description": "curated by lecturer", "weight": 5.0}]
        rubric = _run(replace_subject_rubric(self.db_instance, "CS101", "Databases", curated))
        self.assertEqual(len(rubric["concepts"]), 1)
        self.assertEqual(rubric["concepts"][0]["description"], "curated by lecturer")

    def test_replace_on_missing_subject_creates_it(self):
        rubric = _run(replace_subject_rubric(self.db_instance, "CS202", "Networks", []))
        self.assertEqual(rubric["subject_code"], "CS202")
        self.assertEqual(rubric["concepts"], [])


class ConcurrentUpsertRaceTest(unittest.TestCase):
    """upsert_subject_rubric uses optimistic concurrency (a version field +
    retry-on-conflict) specifically so two lecturers uploading different
    files for the same subject_code at the same moment don't silently
    clobber each other. These tests force the worst-case interleaving —
    both readers see the same stale state before either writes — and assert
    both uploads still survive."""

    def _with_interleaved_reads(self, collection):
        """Forces every find_one to yield control right after reading, so two
        concurrent callers both observe the same pre-write state — the
        precise interleaving that would lose a write under plain
        find-then-update, and that the version-conditioned update_one must
        detect and retry past."""
        real_find_one = collection.find_one

        async def delayed_find_one(query):
            result = await real_find_one(query)
            await asyncio.sleep(0)
            return result

        collection.find_one = delayed_find_one  # type: ignore[method-assign]

    def test_interleaved_creates_both_survive(self):
        """Worst case: neither writer has created the subject yet."""
        collection = FakeSubjectRubricCollection()
        db_instance = FakeDbInstance(collection)
        self._with_interleaved_reads(collection)

        async def run_both():
            await asyncio.gather(
                upsert_subject_rubric(db_instance, "CS101", "Databases", "a.pdf", _concepts("A")),
                upsert_subject_rubric(db_instance, "CS101", "Databases", "b.pdf", _concepts("B")),
            )

        _run(run_both())
        final = _run(get_subject_rubric(db_instance, "CS101"))
        names = {c["name"] for c in final["concepts"]}
        self.assertEqual(names, {"A", "B"})

    def test_interleaved_updates_both_survive(self):
        """Worst case: subject already exists, two more files race in."""
        collection = FakeSubjectRubricCollection()
        db_instance = FakeDbInstance(collection)
        _run(
            upsert_subject_rubric(
                db_instance, "CS101", "Databases", "zero.pdf", _concepts("Zero")
            )
        )
        self._with_interleaved_reads(collection)

        async def run_both():
            await asyncio.gather(
                upsert_subject_rubric(db_instance, "CS101", "Databases", "a.pdf", _concepts("A")),
                upsert_subject_rubric(db_instance, "CS101", "Databases", "b.pdf", _concepts("B")),
            )

        _run(run_both())
        final = _run(get_subject_rubric(db_instance, "CS101"))
        names = {c["name"] for c in final["concepts"]}
        self.assertEqual(names, {"Zero", "A", "B"})


if __name__ == "__main__":
    unittest.main()
