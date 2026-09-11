"""Publish-path tests for the two assessment modes, with the emphasis on
WITH_TECHNICAL_ACCURACY (the human-in-the-loop mode).

Covers the seam the scoring-level tests in VivaEvaluationEngine/tests do not:
`PATCH /api/viva-marks/{id}/publish` -> viva_marks.apply_publish_to_mark ->
assessment_scoring.build_assessment, and what actually lands in Mongo.

Offline: Mongo is a hand-rolled double, and the stored engine result is a fixture,
so no CNN/Whisper weights and no Atlas connection are needed. Run from repo root:

  python -m unittest Gradex_AI_Server.app.tests.test_viva_publish_technical -v
"""
from __future__ import annotations

import asyncio
import unittest
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import HTTPException

from Gradex_AI_Server.app.main import PublishVivaMarkPayload, publish_viva_mark
from Gradex_AI_Server.app.core.database import db_instance
from Gradex_AI_Server.app.viva_marks import (
    apply_publish_to_mark,
    assessment_is_publishable,
    auto_publish_without_technical,
)
from VivaEvaluationEngine.services.assessment_scoring import (
    MODE_WITH,
    MODE_WITHOUT,
    STATUS_INCOMPLETE,
    build_assessment,
    resolve_grade,
)


def _run(coro):
    return asyncio.run(coro)


def _engine_result(**overrides) -> Dict[str, Any]:
    """A VALID recording: face present, audible speech, measurable voice quality.

    Mirrors the shape viva_service.analyze_video_file returns, trimmed to the
    keys canonical_features actually reads.
    """
    base: Dict[str, Any] = {
        "confidence_score": 72.5,
        "engagement_score": 65.75,
        "video_status": "success",
        "summary": {"positive_ratio": 0.625, "neutral_ratio": 0.375, "negative_ratio": 0.0},
        "engagement_summary": {
            "very_low_ratio": 0.0,
            "low_ratio": 0.0,
            "high_ratio": 0.625,
            "very_high_ratio": 0.375,
            "average_engagement_score": 0.825,
        },
        "coverage": {
            "frames_sampled": 8,
            "frames_with_face": 8,
            "face_coverage_ratio": 1.0,
            "blinks_measured": True,
            "blinks_per_minute": 12.0,
            "scores_emitted": True,
        },
        "audio_analysis": {
            "status": "degraded",
            "transcript_word_count": 23,
            "segment_count": 4,
            "audio_grade": 4.71,
            "acoustic_features": {
                "duration_seconds": 8.0,
                "rms_mean": 0.056,
                "pitch_std_hz": 67.02,
                "jitter_local": 0.0219,
                "shimmer_local": 0.110,
                "hnr_mean_db": 11.81,
                "voice_quality_measured": True,
            },
            "transcript_features": {
                "speech_rate_wpm": 135.0,
                "speech_rate_band": "optimal",
                "hedge_count": 0,
                "filler_count": 0,
                "pause_count": 1,
                "long_pause_count": 0,
                "sentence_completion_ratio": 1.0,
                "word_count": 23,
            },
            "audio_emotion": {
                "predicted_emotion": "happy",
                "confidence": 0.9,
                "source": "heuristic",
            },
        },
        "face_cues": [
            {"time": float(i), "valid": True, "mouth_open": 0.42, "talking": True}
            for i in range(16)
        ],
    }
    base.update(overrides)
    return base


class FakeMarksCollection:
    """Minimal async stand-in for the motor collection used by viva_marks."""

    def __init__(self, doc: Optional[Dict[str, Any]] = None):
        self.doc = doc
        self.updates: list[Dict[str, Any]] = []

    async def find_one(self, query):
        if self.doc is None:
            return None
        if query.get("_id") != self.doc["_id"]:
            return None
        return self.doc

    async def update_one(self, query, update):
        if self.doc is None or query.get("_id") != self.doc["_id"]:
            return type("R", (), {"matched_count": 0, "modified_count": 0})()
        changes = update["$set"]
        self.updates.append(changes)
        self.doc.update(changes)
        return type("R", (), {"matched_count": 1, "modified_count": 1})()


def _stored_mark(mode: str = MODE_WITH) -> Dict[str, Any]:
    """A draft mark as persist_and_autopublish would have written it."""
    result = _engine_result()
    result["assessment"] = build_assessment(result, mode=mode)
    return {
        "_id": ObjectId(),
        "result": result,
        "assessment": result["assessment"],
        "assessment_mode": mode,
        "published": False,
        "human_published": False,
        "student_id": None,
    }


class TechnicalPublishTests(unittest.TestCase):
    """WITH_TECHNICAL_ACCURACY: the examiner supplies the technical score."""

    def test_draft_before_publish_has_no_final_score(self):
        """A technical viva is analysed but deliberately unscored until a human acts."""
        doc = _stored_mark(MODE_WITH)
        assessment = doc["assessment"]
        self.assertIsNotNone(assessment["ai_performance"]["score"])
        self.assertIsNone(assessment["final_score"])
        self.assertIsNone(assessment["grade"])
        self.assertEqual(assessment["fusion"]["pending"], "technical_accuracy_required")
        self.assertFalse(doc["published"])

    def test_publish_fuses_ai_and_technical_50_50(self):
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        ai = doc["assessment"]["ai_performance"]["score"]

        payload = _run(
            apply_publish_to_mark(
                col,
                doc["_id"],
                mode=MODE_WITH,
                technical_accuracy=8.0,
                student_id="IT21001",
            )
        )

        expected = round(0.5 * ai + 0.5 * 80.0, 2)
        self.assertAlmostEqual(payload["final_score"], expected, places=2)
        self.assertEqual(payload["final_grade"], resolve_grade(expected))
        # The mark actually stored must match what was returned to the client.
        self.assertAlmostEqual(col.doc["final_score"], expected, places=2)
        self.assertEqual(col.doc["technical_accuracy"], 8.0)
        self.assertEqual(col.doc["student_id"], "IT21001")
        self.assertTrue(col.doc["published"])
        self.assertTrue(col.doc["human_published"])

    def test_technical_scale_is_out_of_ten(self):
        """technical_accuracy is /10 and is scaled x10 onto the /100 mark."""
        for technical, expected_component in ((0.0, 0.0), (5.0, 50.0), (10.0, 100.0)):
            doc = _stored_mark(MODE_WITH)
            col = FakeMarksCollection(doc)
            ai = doc["assessment"]["ai_performance"]["score"]
            payload = _run(
                apply_publish_to_mark(
                    col,
                    doc["_id"],
                    mode=MODE_WITH,
                    technical_accuracy=technical,
                    student_id=None,
                )
            )
            self.assertAlmostEqual(
                payload["final_score"],
                round(0.5 * ai + 0.5 * expected_component, 2),
                places=2,
                msg=f"technical={technical}",
            )

    def test_higher_technical_never_lowers_the_mark(self):
        """Monotonic in the examiner's score — a sanity property for a grade."""
        finals = []
        for technical in (2.0, 5.0, 9.0):
            doc = _stored_mark(MODE_WITH)
            col = FakeMarksCollection(doc)
            payload = _run(
                apply_publish_to_mark(
                    col,
                    doc["_id"],
                    mode=MODE_WITH,
                    technical_accuracy=technical,
                    student_id=None,
                )
            )
            finals.append(payload["final_score"])
        self.assertEqual(finals, sorted(finals))
        self.assertLess(finals[0], finals[-1])

    def test_publish_without_technical_is_rejected(self):
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        with self.assertRaises(ValueError):
            _run(
                apply_publish_to_mark(
                    col,
                    doc["_id"],
                    mode=MODE_WITH,
                    technical_accuracy=None,
                    student_id=None,
                )
            )
        self.assertFalse(col.doc["published"])

    def test_endpoint_rejects_missing_technical_with_400(self):
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        prev = db_instance.marks_col
        db_instance.marks_col = col
        try:
            payload = PublishVivaMarkPayload(
                assessment_mode=MODE_WITH, technical_accuracy=None
            )
            with self.assertRaises(HTTPException) as ctx:
                _run(publish_viva_mark(str(doc["_id"]), payload))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            db_instance.marks_col = prev

    def test_endpoint_rejects_unknown_mode_with_400(self):
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        prev = db_instance.marks_col
        db_instance.marks_col = col
        try:
            payload = PublishVivaMarkPayload(
                assessment_mode="SOMETHING_ELSE", technical_accuracy=5.0
            )
            with self.assertRaises(HTTPException) as ctx:
                _run(publish_viva_mark(str(doc["_id"]), payload))
            self.assertEqual(ctx.exception.status_code, 400)
        finally:
            db_instance.marks_col = prev

    def test_endpoint_publishes_technical_end_to_end(self):
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        ai = doc["assessment"]["ai_performance"]["score"]
        prev = db_instance.marks_col
        db_instance.marks_col = col
        try:
            payload = PublishVivaMarkPayload(
                assessment_mode=MODE_WITH,
                technical_accuracy=7.5,
                student_id="IT21002",
            )
            response = _run(publish_viva_mark(str(doc["_id"]), payload))
        finally:
            db_instance.marks_col = prev

        expected = round(0.5 * ai + 0.5 * 75.0, 2)
        self.assertAlmostEqual(response["final_score"], expected, places=2)
        self.assertTrue(col.doc["published"])
        self.assertEqual(col.doc["student_id"], "IT21002")


class NonTechnicalPublishTests(unittest.TestCase):
    def test_auto_publish_uses_ai_only(self):
        result = _engine_result()
        result["assessment"] = build_assessment(result, mode=MODE_WITHOUT)
        doc = {
            "_id": ObjectId(),
            "result": result,
            "assessment": result["assessment"],
            "published": False,
        }
        col = FakeMarksCollection(doc)

        payload = _run(auto_publish_without_technical(col, doc["_id"], result))

        self.assertIsNotNone(payload)
        self.assertAlmostEqual(
            payload["final_score"], result["assessment"]["ai_performance"]["score"], places=2
        )
        self.assertIsNone(col.doc["technical_accuracy"])
        self.assertTrue(col.doc["published"])
        # Auto-publish is the machine acting, not a human sign-off.
        self.assertFalse(col.doc["human_published"])

    def test_technical_value_ignored_in_non_technical_mode(self):
        doc = _stored_mark(MODE_WITHOUT)
        col = FakeMarksCollection(doc)
        ai = build_assessment(doc["result"], mode=MODE_WITHOUT)["ai_performance"]["score"]

        payload = _run(
            apply_publish_to_mark(
                col,
                doc["_id"],
                mode=MODE_WITHOUT,
                technical_accuracy=9.0,
                student_id=None,
            )
        )
        self.assertIsNone(payload["technical_accuracy"])
        self.assertAlmostEqual(payload["final_score"], ai, places=2)


class IncompletePublishTests(unittest.TestCase):
    """A recording that failed the quality gates must never become a grade."""

    def _no_face_result(self) -> Dict[str, Any]:
        result = _engine_result(video_status="insufficient_face_coverage")
        result["coverage"] = {
            "frames_sampled": 8,
            "frames_with_face": 0,
            "face_coverage_ratio": 0.0,
            "scores_emitted": False,
        }
        result["confidence_score"] = None
        result["engagement_summary"] = {"average_engagement_score": None}
        return result

    def test_incomplete_is_not_publishable(self):
        result = self._no_face_result()
        assessment = build_assessment(result, mode=MODE_WITHOUT)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertFalse(assessment_is_publishable(assessment))

    def test_incomplete_is_not_auto_published(self):
        result = self._no_face_result()
        result["assessment"] = build_assessment(result, mode=MODE_WITHOUT)
        doc = {"_id": ObjectId(), "result": result, "published": False}
        col = FakeMarksCollection(doc)

        payload = _run(auto_publish_without_technical(col, doc["_id"], result))

        self.assertIsNone(payload)
        self.assertFalse(col.doc["published"])
        self.assertEqual(col.updates, [])


class PublishRoundTripTests(unittest.TestCase):
    def test_stored_assessment_matches_recomputed(self):
        """Publishing recomputes from the stored engine result; the persisted
        assessment must equal a fresh build_assessment with the same inputs, so
        a mark can always be re-derived and defended."""
        doc = _stored_mark(MODE_WITH)
        col = FakeMarksCollection(doc)
        _run(
            apply_publish_to_mark(
                col,
                doc["_id"],
                mode=MODE_WITH,
                technical_accuracy=6.0,
                student_id=None,
            )
        )
        recomputed = build_assessment(doc["result"], mode=MODE_WITH, technical_accuracy=6.0)
        self.assertAlmostEqual(
            col.doc["assessment"]["final_score"], recomputed["final_score"], places=2
        )
        self.assertEqual(col.doc["assessment"]["grade"], recomputed["grade"])
        self.assertEqual(
            col.doc["scoring_version"], recomputed["scoring_version"]
        )


if __name__ == "__main__":
    unittest.main()
