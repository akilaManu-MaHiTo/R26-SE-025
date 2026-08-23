"""HTTP-layer tests for viva analyze, publish, auth, and copilot Ask this.

Does not load CNN/Whisper weights. Run from repo root:

  python -m unittest Gradex_AI_Server.app.tests.test_viva_http -v
"""
from __future__ import annotations

import asyncio
import os
import time
import unittest
from io import BytesIO
from unittest.mock import patch

from bson import ObjectId
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers
from starlette.requests import Request

from Gradex_AI_Server.app.auth import require_api_key
from Gradex_AI_Server.app.core.database import db_instance
from Gradex_AI_Server.app.main import (
    UPLOAD_DIR,
    PublishVivaMarkPayload,
    _analyze_timeout_seconds,
    publish_viva_mark,
    viva_analyze,
)
from Gradex_AI_Server.app.viva_copilot.router import AskPayload, ask
from Gradex_AI_Server.app.viva_copilot.session_store import store


def _video_upload(name: str = "clip.mp4", body: bytes = b"not-a-real-mp4") -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(body),
        headers=Headers({"content-type": "video/mp4"}),
    )


def _run(coro):
    return asyncio.run(coro)


class AnalyzeTimeoutHelperTests(unittest.TestCase):
    def test_default_timeout(self):
        with patch.dict(os.environ, {"VIVA_ANALYZE_TIMEOUT_SECONDS": ""}, clear=False):
            os.environ.pop("VIVA_ANALYZE_TIMEOUT_SECONDS", None)
            self.assertEqual(_analyze_timeout_seconds(), 600.0)

    def test_invalid_timeout_falls_back(self):
        with patch.dict(os.environ, {"VIVA_ANALYZE_TIMEOUT_SECONDS": "nope"}):
            self.assertEqual(_analyze_timeout_seconds(), 600.0)


class AuthTests(unittest.TestCase):
    def test_missing_key_is_401(self):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/viva-analyze",
            "raw_path": b"/api/viva-analyze",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
        request = Request(scope)
        with patch("Gradex_AI_Server.app.auth.configured_api_key", return_value="secret"):
            with self.assertRaises(HTTPException) as ctx:
                _run(require_api_key(request))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_matching_header_is_ok(self):
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/viva-analyze",
            "raw_path": b"/api/viva-analyze",
            "query_string": b"",
            "headers": [(b"x-api-key", b"secret")],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
        request = Request(scope)
        with patch("Gradex_AI_Server.app.auth.configured_api_key", return_value="secret"):
            _run(require_api_key(request))


class AnalyzeHttpTests(unittest.TestCase):
    """viva_analyze() persistence paths, pinned offline.

    viva_analyze calls ensure_marks_collection() before writing. With
    allow_autoconnect left on, that dials the real Atlas cluster, replaces any
    injected marks_col, and inserts live rows into vivamark.marks — so these
    tests must disable it and clear the client for the ping guard.
    """

    def setUp(self):
        self._prev_autoconnect = db_instance.allow_autoconnect
        self._prev_client = db_instance.client
        self._prev_marks_col = db_instance.marks_col
        db_instance.allow_autoconnect = False
        db_instance.client = None

    def tearDown(self):
        db_instance.allow_autoconnect = self._prev_autoconnect
        db_instance.client = self._prev_client
        db_instance.marks_col = self._prev_marks_col

    def test_non_video_is_400(self):
        upload = UploadFile(
            filename="notes.txt",
            file=BytesIO(b"hello"),
            headers=Headers({"content-type": "text/plain"}),
        )
        with self.assertRaises(HTTPException) as ctx:
            _run(viva_analyze(upload))
        self.assertEqual(ctx.exception.status_code, 400)

    def test_unreadable_video_is_400_and_upload_deleted(self):
        class VideoUnreadableError(ValueError):
            pass

        def boom(_path: str, _debug: bool = False):
            raise VideoUnreadableError("This file could not be opened as a video.")

        before = {p.name for p in UPLOAD_DIR.glob("*")}
        with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", side_effect=boom):
            with self.assertRaises(HTTPException) as ctx:
                _run(viva_analyze(_video_upload()))
        self.assertEqual(ctx.exception.status_code, 400)
        after = {p.name for p in UPLOAD_DIR.glob("*")}
        self.assertEqual(after, before)

    def test_pipeline_failure_still_deletes_upload(self):
        def boom(_path: str, _debug: bool = False):
            raise RuntimeError("cnn exploded")

        before = {p.name for p in UPLOAD_DIR.glob("*")}
        with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", side_effect=boom):
            with self.assertRaises(HTTPException) as ctx:
                _run(viva_analyze(_video_upload()))
        self.assertEqual(ctx.exception.status_code, 500)
        after = {p.name for p in UPLOAD_DIR.glob("*")}
        self.assertEqual(after, before)

    def test_timeout_is_504_and_upload_deleted(self):
        def slow(_path: str, _debug: bool = False):
            time.sleep(1.5)
            return {}

        before = {p.name for p in UPLOAD_DIR.glob("*")}
        with patch.dict(os.environ, {"VIVA_ANALYZE_TIMEOUT_SECONDS": "0.05"}):
            with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", side_effect=slow):
                with self.assertRaises(HTTPException) as ctx:
                    _run(viva_analyze(_video_upload()))
        self.assertEqual(ctx.exception.status_code, 504)
        after = {p.name for p in UPLOAD_DIR.glob("*")}
        self.assertEqual(after, before)

    def test_success_without_mongo_sets_persistence_error(self):
        fake = {
            "video_status": "success",
            "assessment": {"status": "VALID", "final_score": 70},
        }
        previous = db_instance.marks_col
        db_instance.marks_col = None
        try:
            with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", return_value=dict(fake)):
                result = _run(viva_analyze(_video_upload()))
        finally:
            db_instance.marks_col = previous
        self.assertNotIn("mark_id", result)
        self.assertIn("persistence_error", result)

    def test_success_with_mongo_returns_mark_id(self):
        fake = {
            "video_status": "success",
            "assessment": {"status": "VALID", "final_score": 70, "scoring_version": "v1", "ai_performance": {"score": 70}},
        }
        inserted: dict = {}
        stored: dict = {}

        class FakeCol:
            async def insert_one(self, doc):
                inserted.update(doc)
                oid = ObjectId("507f1f77bcf86cd799439011")
                stored[oid] = dict(doc)
                stored[oid]["_id"] = oid
                stored[oid]["result"] = dict(fake)

                class Result:
                    inserted_id = oid

                return Result()

            async def find_one(self, query):
                return stored.get(query.get("_id"))

            async def update_one(self, query, update):
                doc = stored.get(query.get("_id"))
                if doc is None:
                    class Result:
                        matched_count = 0

                    return Result()
                doc.update(update.get("$set", {}))
                class Result:
                    matched_count = 1

                return Result()

            async def create_index(self, *_args, **_kwargs):
                return None

        previous = db_instance.marks_col
        db_instance.marks_col = FakeCol()
        try:
            with patch("Gradex_AI_Server.app.viva_service.analyze_video_file", return_value=dict(fake)):
                result = _run(viva_analyze(_video_upload()))
        finally:
            db_instance.marks_col = previous
        self.assertEqual(result["mark_id"], "507f1f77bcf86cd799439011")
        self.assertTrue(result["published"])
        self.assertTrue(result["auto_published"])
        self.assertNotIn("persistence_error", result)
        self.assertFalse(inserted["published"])


class PublishHttpTests(unittest.TestCase):
    def test_invalid_id_is_400(self):
        with self.assertRaises(HTTPException) as ctx:
            _run(
                publish_viva_mark(
                    "not-an-oid",
                    PublishVivaMarkPayload(assessment_mode="WITHOUT_TECHNICAL_ACCURACY"),
                )
            )
        self.assertEqual(ctx.exception.status_code, 400)

    def test_disconnected_mongo_is_503(self):
        previous = db_instance.marks_col
        db_instance.marks_col = None
        try:
            with self.assertRaises(HTTPException) as ctx:
                _run(
                    publish_viva_mark(
                        "507f1f77bcf86cd799439011",
                        PublishVivaMarkPayload(assessment_mode="WITHOUT_TECHNICAL_ACCURACY"),
                    )
                )
        finally:
            db_instance.marks_col = previous
        self.assertEqual(ctx.exception.status_code, 503)

    def test_unknown_id_when_connected_is_404(self):
        class FakeCol:
            async def find_one(self, _query):
                return None

        previous = db_instance.marks_col
        db_instance.marks_col = FakeCol()
        try:
            with self.assertRaises(HTTPException) as ctx:
                _run(
                    publish_viva_mark(
                        "507f1f77bcf86cd799439011",
                        PublishVivaMarkPayload(assessment_mode="WITHOUT_TECHNICAL_ACCURACY"),
                    )
                )
        finally:
            db_instance.marks_col = previous
        self.assertEqual(ctx.exception.status_code, 404)


class CopilotAskPhaseTests(unittest.TestCase):
    def test_ask_during_presentation_is_409(self):
        session = store.create({})
        session.phase = "presentation"
        with self.assertRaises(HTTPException) as ctx:
            _run(ask(session.session_id, AskPayload(question="What is a primary key?")))
        self.assertEqual(ctx.exception.status_code, 409)
        store.delete(session.session_id)

    def test_ask_during_viva_sets_current_question(self):
        session = store.create({})
        session.phase = "viva"
        result = _run(ask(session.session_id, AskPayload(question="What is a primary key?")))
        self.assertEqual(result["currentQuestion"], "What is a primary key?")
        store.delete(session.session_id)


if __name__ == "__main__":
    unittest.main()
