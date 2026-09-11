"""Unit tests for significant-second-face detection helper."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.analysis_service import _build_multi_face_summary, _has_significant_second_face
from services.face_detector import FaceDetector


class SignificantSecondFaceTests(unittest.TestCase):
    def test_one_face_is_not_significant_second(self):
        self.assertFalse(_has_significant_second_face([(0, 0, 100, 100)]))

    def test_tiny_second_face_is_ignored(self):
        faces = [(0, 0, 100, 100), (0, 0, 10, 10)]
        self.assertFalse(_has_significant_second_face(faces))

    def test_large_second_face_counts(self):
        faces = [(0, 0, 100, 100), (0, 0, 80, 80)]
        self.assertTrue(_has_significant_second_face(faces))

    def test_bbox_area(self):
        self.assertEqual(FaceDetector._bbox_area((0, 0, 10, 20)), 200)


class MultiFaceSummaryBuilderTests(unittest.TestCase):
    def test_passes_when_below_thresholds(self):
        summary = _build_multi_face_summary(
            frames_sampled=100,
            significant_frames=5,
            max_consecutive=2,
        )
        self.assertTrue(summary["passed"])

    def test_fails_on_ratio(self):
        summary = _build_multi_face_summary(
            frames_sampled=20,
            significant_frames=4,
            max_consecutive=1,
        )
        self.assertFalse(summary["passed"])

    def test_fails_on_consecutive_frames(self):
        summary = _build_multi_face_summary(
            frames_sampled=20,
            significant_frames=3,
            max_consecutive=3,
        )
        self.assertFalse(summary["passed"])


if __name__ == "__main__":
    unittest.main()
