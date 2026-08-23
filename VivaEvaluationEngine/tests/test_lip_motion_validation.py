"""Tests for proportional lip-motion validation (1 lip event per 5 words)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.assessment_scoring import STATUS_INCOMPLETE, build_assessment
from services.lip_motion_validation import summarize_lip_motion


def _talking_cues(count: int, *, talking: bool = True) -> list[dict]:
    return [
        {
            "time": float(index),
            "valid": True,
            "mouth_open": 0.45 if talking else 0.08,
            "talking": talking,
        }
        for index in range(count)
    ]


def _speech_result(*, words: int = 24, lip_events: int = 16, talking: bool = True, **overrides):
    base = {
        "video_status": "success",
        "face_cues": _talking_cues(lip_events, talking=talking),
        "audio_analysis": {
            "status": "degraded",
            "transcript_word_count": words,
            "transcript_features": {"word_count": words},
            "acoustic_features": {"duration_seconds": 30.0, "rms_mean": 0.05},
        },
        "coverage": {
            "frames_sampled": lip_events,
            "frames_with_face": lip_events,
            "face_coverage_ratio": 1.0,
            "blinks_measured": True,
            "blinks_per_minute": 10.0,
        },
        "engagement_summary": {"average_engagement_score": 0.7},
        "summary": {"positive_ratio": 0.6, "neutral_ratio": 0.4, "negative_ratio": 0.0},
    }
    base.update(overrides)
    return base


class LipMotionSummaryTests(unittest.TestCase):
    def test_twenty_words_need_four_lip_events(self):
        summary = summarize_lip_motion(_speech_result(words=20, lip_events=4))
        self.assertEqual(summary["minimum_required"], 4)
        self.assertEqual(summary["lip_ratio"], "1/5")
        self.assertTrue(summary["passed"])

    def test_twenty_words_fail_with_three_lip_events(self):
        summary = summarize_lip_motion(_speech_result(words=20, lip_events=3))
        self.assertEqual(summary["minimum_required"], 4)
        self.assertFalse(summary["passed"])

    def test_fails_when_mouth_stays_closed_during_speech(self):
        summary = summarize_lip_motion(_speech_result(words=20, lip_events=20, talking=False))
        self.assertFalse(summary["passed"])
        self.assertEqual(summary["motion_events"], 0)

    def test_skipped_when_no_speech(self):
        summary = summarize_lip_motion(
            _speech_result(
                words=0,
                lip_events=0,
                audio_analysis={
                    "status": "degraded",
                    "transcript_word_count": 0,
                    "transcript_features": {"word_count": 0},
                    "acoustic_features": {"duration_seconds": 8.0, "rms_mean": 0.001},
                },
            )
        )
        self.assertTrue(summary["passed"])
        self.assertFalse(summary["speech_requires_lips"])


class LipMotionAssessmentTests(unittest.TestCase):
    def test_still_face_with_speech_is_incomplete(self):
        assessment = build_assessment(_speech_result(words=20, lip_events=20, talking=False))
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIn("insufficient_lip_motion", assessment["validation"]["reasons"])

    def test_visible_lip_motion_with_speech_can_score(self):
        assessment = build_assessment(_speech_result(words=24, lip_events=16))
        self.assertNotEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertTrue(assessment["lip_motion"]["passed"])


if __name__ == "__main__":
    unittest.main()
