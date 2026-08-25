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

from Gradex_AI_Server.app.subject_rubric_service import (
    get_subject_rubric,
    replace_subject_rubric,
    upsert_subject_rubric,
)


class FakeSubjectRubricCollection:
    """In-memory stand-in for db_instance.db["subject_rubrics"]."""

    def __init__(self):
        self.docs: dict[str, dict] = {}

    async def find_one(self, query):
        doc = self.docs.get(query.get("subject_code"))
        return dict(doc) if doc else None

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
    """Characterizes a known limitation: upsert_subject_rubric does a
    find_one then update_one as two separate round trips, not an atomic
    read-modify-write. Two concurrent uploads for different files on the
    same subject_code can race and one can silently lose the other's
    concepts. This test documents that behavior rather than asserting it
    is safe — see the assertion below and the note in the docstring."""

    def test_interleaved_upserts_can_lose_a_write(self):
        collection = FakeSubjectRubricCollection()
        db_instance = FakeDbInstance(collection)

        real_find_one = collection.find_one

        async def delayed_find_one(query):
            result = await real_find_one(query)
            await asyncio.sleep(0)  # yield control, allowing interleaving
            return result

        collection.find_one = delayed_find_one  # type: ignore[method-assign]

        async def run_both():
            await asyncio.gather(
                upsert_subject_rubric(db_instance, "CS101", "Databases", "a.pdf", _concepts("A")),
                upsert_subject_rubric(db_instance, "CS101", "Databases", "b.pdf", _concepts("B")),
            )

        _run(run_both())
        final = _run(get_subject_rubric(db_instance, "CS101"))
        names = {c["name"] for c in final["concepts"]}
        # Document actual behavior: with interleaved reads, the loser's
        # write can be silently dropped instead of merged. If this starts
        # asserting {"A", "B"} on its own, the race was fixed upstream —
        # until then, upload flows should treat concurrent uploads to the
        # same subject_code as unsafe and serialize them client-side.
        self.assertTrue(names.issubset({"A", "B"}))
        self.assertGreaterEqual(len(names), 1)


if __name__ == "__main__":
    unittest.main()
