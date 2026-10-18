"""Tests for viva sessions (the label every analysis is filed under).

Run from repo root:

  python -m unittest Gradex_AI_Server.app.tests.test_viva_sessions -v
"""
from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException

from Gradex_AI_Server.app import viva_sessions as vs


def _request(email="a@example.com"):
    return SimpleNamespace(state=SimpleNamespace(user={"email": email, "role": "lecturer"}))


class _Cursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_a, **_k):
        return self

    def limit(self, *_a, **_k):
        return self

    async def to_list(self, length=None):
        return self.docs


class _FakeVivas:
    def __init__(self):
        self.docs = []
        self.last_query = None

    async def insert_one(self, doc):
        doc["_id"] = ObjectId()
        self.docs.append(doc)
        return SimpleNamespace(inserted_id=doc["_id"])

    async def find_one(self, query):
        return next((d for d in self.docs if all(d.get(k) == v for k, v in query.items())), None)

    def find(self, query):
        self.last_query = query
        return _Cursor([d for d in self.docs if all(d.get(k) == v for k, v in query.items())])


def _payload(**overrides):
    base = dict(
        name="ER Viva",
        subject_code="SE3040",
        subject_name="Software Testing",
        category="non_technical",
        year=2026,
        semester=2,
    )
    base.update(overrides)
    return vs.CreateVivaPayload(**base)


class VivaSessionTests(unittest.TestCase):
    def setUp(self):
        self.col = _FakeVivas()
        patcher = patch.object(vs, "_vivas_col", return_value=self.col)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _run(self, coro):
        return asyncio.run(coro)

    def test_create_builds_label_and_stamps_examiner(self):
        viva = self._run(vs.create_viva(_payload(), _request()))
        self.assertEqual(viva["label"], "SE3040-ER Viva - semester 2 - 2026")
        self.assertEqual(viva["subject_code"], "SE3040")
        self.assertEqual(viva["examiner_email"], "a@example.com")
        self.assertEqual(viva["assessment_mode"], "WITHOUT_TECHNICAL_ACCURACY")

    def test_technical_can_be_created_before_its_rubric_but_not_analyzed(self):
        viva = self._run(vs.create_viva(_payload(category="technical"), _request()))
        with patch(
            "Gradex_AI_Server.app.subject_rubric_service.get_subject_rubric", return_value=None
        ):
            with self.assertRaises(HTTPException) as ctx:
                self._run(vs.fetch_viva_for_analysis(viva["viva_id"], _request()))
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("subject content", ctx.exception.detail)
        with patch(
            "Gradex_AI_Server.app.subject_rubric_service.get_subject_rubric",
            return_value={"concepts": [{"id": "c1"}]},
        ):
            found = self._run(vs.fetch_viva_for_analysis(viva["viva_id"], _request()))
        self.assertEqual(found["category"], "technical")

    def test_technical_with_rubric_maps_to_technical_mode(self):
        with patch(
            "Gradex_AI_Server.app.subject_rubric_service.get_subject_rubric",
            return_value={"concepts": [{"id": "c1"}]},
        ):
            viva = self._run(vs.create_viva(_payload(category="technical"), _request()))
        self.assertEqual(viva["assessment_mode"], "WITH_TECHNICAL_ACCURACY")

    def test_list_defaults_to_own_vivas_and_all_toggle_shows_everyone(self):
        self._run(vs.create_viva(_payload(), _request("a@example.com")))
        self._run(vs.create_viva(_payload(name="Other"), _request("b@example.com")))
        with patch.object(vs.db_instance, "marks_col", None):
            mine = self._run(vs.list_vivas(_request("a@example.com")))
            everyone = self._run(vs.list_vivas(_request("a@example.com"), all=True))
        self.assertEqual([v["name"] for v in mine["items"]], ["ER Viva"])
        self.assertEqual(everyone["count"], 2)

    def test_analysis_requires_a_viva(self):
        with self.assertRaises(HTTPException) as ctx:
            self._run(vs.fetch_viva_for_analysis("", _request()))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_analysis_rejects_unknown_viva(self):
        with self.assertRaises(HTTPException) as ctx:
            self._run(vs.fetch_viva_for_analysis(str(ObjectId()), _request()))
        self.assertEqual(ctx.exception.status_code, 404)

    def test_analysis_rejects_another_lecturers_viva(self):
        viva = self._run(vs.create_viva(_payload(), _request("a@example.com")))
        with self.assertRaises(HTTPException) as ctx:
            self._run(vs.fetch_viva_for_analysis(viva["viva_id"], _request("b@example.com")))
        self.assertEqual(ctx.exception.status_code, 403)
        found = self._run(vs.fetch_viva_for_analysis(viva["viva_id"], _request("a@example.com")))
        self.assertEqual(vs.viva_extra_doc(found)["subject_code"], "SE3040")


if __name__ == "__main__":
    unittest.main()
