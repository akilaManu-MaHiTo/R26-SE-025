"""Tests for single-student multi-face gate."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.assessment_scoring import STATUS_INCOMPLETE, STATUS_VALID, build_assessment
from services.multi_face_validation import classify_multi_face_evidence, summarize_multi_face


def _multi_face_coverage(
    *,
    sampled: int = 20,
    significant: int = 0,
    consecutive: int = 0,
) -> dict:
    ratio = round(significant / sampled, 4) if sampled else 0.0
    passed = sampled <= 0 or (ratio < 0.12 and consecutive < 3)
    return {
        "frames_sampled": sampled,
        "frames_with_significant_second_face": significant,
        "significant_second_face_ratio": ratio,
        "max_consecutive_frames": consecutive,
        "min_secondary_area_ratio": 0.20,
        "min_frame_ratio_threshold": 0.12,
        "min_consecutive_frames_threshold": 3,
        "passed": passed,
    }


def _viva_result(**overrides):
    base = {
        "video_status": "success",
        "coverage": {
            "frames_sampled": 20,
            "frames_with_face": 20,
            "face_coverage_ratio": 1.0,
            "multi_face": _multi_face_coverage(),
        },
        "face_cues": [
            {
                "time": float(i),
                "valid": True,
                "mouth_open": 0.42,
                "talking": True,
            }
            for i in range(16)
        ],
        "audio_analysis": {
            "status": "degraded",
            "transcript_word_count": 24,
            "transcript_features": {"word_count": 24},
            "acoustic_features": {"duration_seconds": 30.0, "rms_mean": 0.05},
        },
        "engagement_summary": {"average_engagement_score": 0.7},
        "summary": {"positive_ratio": 0.6, "neutral_ratio": 0.4, "negative_ratio": 0.0},
    }
    base.update(overrides)
    return base


class MultiFaceSummaryTests(unittest.TestCase):
    def test_single_student_passes(self):
        summary = summarize_multi_face(_viva_result())
        self.assertTrue(summary["passed"])
        self.assertIsNone(classify_multi_face_evidence(_viva_result()))

    def test_brief_partial_face_passes(self):
        result = _viva_result(
            coverage={
                "frames_sampled": 100,
                "frames_with_face": 100,
                "face_coverage_ratio": 1.0,
                "multi_face": _multi_face_coverage(sampled=100, significant=5, consecutive=2),
            }
        )
        summary = summarize_multi_face(result)
        self.assertTrue(summary["passed"])
        self.assertIsNone(classify_multi_face_evidence(result))

    def test_sustained_second_face_fails(self):
        result = _viva_result(
            coverage={
                "frames_sampled": 20,
                "frames_with_face": 20,
                "face_coverage_ratio": 1.0,
                "multi_face": _multi_face_coverage(sampled=20, significant=3, consecutive=3),
            }
        )
        summary = summarize_multi_face(result)
        self.assertFalse(summary["passed"])
        self.assertEqual(classify_multi_face_evidence(result), "multiple_faces_detected")

    def test_frequent_second_face_fails(self):
        result = _viva_result(
            coverage={
                "frames_sampled": 20,
                "frames_with_face": 20,
                "face_coverage_ratio": 1.0,
                "multi_face": _multi_face_coverage(sampled=20, significant=4, consecutive=1),
            }
        )
        summary = summarize_multi_face(result)
        self.assertFalse(summary["passed"])
        self.assertEqual(classify_multi_face_evidence(result), "multiple_faces_detected")


class MultiFaceAssessmentTests(unittest.TestCase):
    def test_two_students_marked_incomplete(self):
        result = _viva_result(
            coverage={
                "frames_sampled": 20,
                "frames_with_face": 20,
                "face_coverage_ratio": 1.0,
                "multi_face": _multi_face_coverage(sampled=20, significant=8, consecutive=4),
            }
        )
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIn("multiple_faces_detected", assessment["validation"]["reasons"])
        self.assertIsNone(assessment["final_score"])

    def test_one_student_can_score(self):
        assessment = build_assessment(_viva_result())
        self.assertEqual(assessment["status"], STATUS_VALID)
        self.assertIsNotNone(assessment["final_score"])


if __name__ == "__main__":
    unittest.main()
