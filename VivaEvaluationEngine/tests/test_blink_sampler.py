"""Blink EAR counting and FaceMesh/Tasks fallback behaviour.

Does not require the 37s fixture except one optional integration test.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.blink_sampler import (
    LEFT_EYE,
    RIGHT_EYE,
    BlinkSampler,
    _finalize_report,
    count_blinks_from_ears,
    eye_aspect_ratio,
)


class _LM:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y


def _mesh(open_eye: bool = True):
    pts = [_LM(0.5, 0.5) for _ in range(478)]
    # Left: 33--133 horizontal, 160/158 top, 153/144 bottom.
    pts[33] = _LM(0.30, 0.40)
    pts[133] = _LM(0.40, 0.40)
    pts[160] = _LM(0.33, 0.34 if open_eye else 0.395)
    pts[158] = _LM(0.37, 0.34 if open_eye else 0.395)
    pts[153] = _LM(0.37, 0.46 if open_eye else 0.405)
    pts[144] = _LM(0.33, 0.46 if open_eye else 0.405)
    # Right
    pts[362] = _LM(0.60, 0.40)
    pts[263] = _LM(0.70, 0.40)
    pts[387] = _LM(0.63, 0.34 if open_eye else 0.395)
    pts[385] = _LM(0.67, 0.34 if open_eye else 0.395)
    pts[380] = _LM(0.67, 0.46 if open_eye else 0.405)
    pts[373] = _LM(0.63, 0.46 if open_eye else 0.405)
    return pts


class LandmarkIndexTests(unittest.TestCase):
    def test_eye_indices_fit_478_mesh(self):
        self.assertLess(max(LEFT_EYE), 478)
        self.assertLess(max(RIGHT_EYE), 478)

    def test_open_eye_ear_above_closed(self):
        open_ear = eye_aspect_ratio(_mesh(True))
        closed_ear = eye_aspect_ratio(_mesh(False))
        self.assertIsNotNone(open_ear)
        self.assertIsNotNone(closed_ear)
        self.assertGreater(open_ear, closed_ear)
        self.assertGreater(open_ear, 0.15)
        self.assertLess(closed_ear, 0.15)

    def test_short_mesh_is_none(self):
        self.assertIsNone(eye_aspect_ratio([_LM(0, 0)] * 10))


class EarToBlinkTests(unittest.TestCase):
    def test_zero_blinks_open_eyes(self):
        ears = [0.22] * 40
        self.assertEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 0)
        report = _finalize_report(
            ears=ears,
            sample_fps=10,
            threshold=0.15,
            min_consec=2,
            detector="unit",
            duration_seconds=40.0,
        )
        self.assertEqual(report["status"], "available")
        self.assertEqual(report["blink_count"], 0)
        self.assertEqual(report["blink_rate_per_minute"], 0.0)
        self.assertEqual(report["measurement_quality"], "adequate")

    def test_short_window_measurement_quality_low(self):
        ears = [0.22] * 40
        report = _finalize_report(
            ears=ears,
            sample_fps=10,
            threshold=0.15,
            min_consec=2,
            detector="unit",
            duration_seconds=8.0,
        )
        self.assertEqual(report["status"], "available")
        self.assertEqual(report["measurement_quality"], "low")

    def test_one_blink_trough(self):
        ears = [0.22] * 10 + [0.04, 0.03] + [0.22] * 10
        self.assertEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 1)

    def test_two_blinks(self):
        ears = [0.22, 0.04, 0.03, 0.22, 0.22, 0.05, 0.04, 0.22]
        self.assertEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 2)

    def test_isolated_deep_trough_counts(self):
        ears = [0.22, 0.04, 0.22]
        self.assertEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 1)

    def test_isolated_shallow_noise_does_not_count(self):
        ears = [0.16, 0.149, 0.16]
        self.assertEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 0)

    def test_high_ear_camera_relative_close(self):
        # video_check-02 style: open median ~0.57, trough 0.14 for one sample.
        ears = [0.57] * 20 + [0.136] + [0.57] * 20
        self.assertGreaterEqual(count_blinks_from_ears(ears, threshold=0.15, min_consec=2), 1)

    def test_missing_landmarks_do_not_count_as_zero_blink_score_path(self):
        ears = [None] * 40
        report = _finalize_report(
            ears=ears,
            sample_fps=10,
            threshold=0.15,
            min_consec=2,
            detector="unit",
        )
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["reason"], "insufficient_eye_frames")
        self.assertIsNone(report["blink_count"])
        self.assertIsNone(report["blink_rate_per_minute"])

    def test_short_valid_recording_unavailable(self):
        ears = [0.22] * 20  # 2.0s at 10 fps; minimum is 3s
        report = _finalize_report(
            ears=ears,
            sample_fps=10,
            threshold=0.15,
            min_consec=2,
            detector="unit",
        )
        self.assertEqual(report["reason"], "recording_too_short")
        self.assertEqual(report["valid_eye_frames"], 20)
        self.assertIsNone(report["blink_count"])


class NoFaceVideoTests(unittest.TestCase):
    def test_unreadable_path(self):
        report = BlinkSampler().measure_blinks(str(ENGINE_ROOT / "does-not-exist.mp4"))
        self.assertEqual(report["status"], "unavailable")
        self.assertIn(report["reason"], {"video_unreadable", "insufficient_eye_frames", "face_mesh_unavailable"})


class RealVideoIntegrationTests(unittest.TestCase):
    def test_only_boy_talking_has_available_blinks(self):
        video = ENGINE_ROOT / "videos" / "only boy talking.mp4"
        if not video.is_file():
            self.skipTest("37s fixture video is not present")
        report = BlinkSampler().measure_blinks(str(video))
        self.assertEqual(report["status"], "available", report)
        self.assertGreaterEqual(report["valid_eye_frames"], 8)
        self.assertIsNotNone(report["blink_count"])
        self.assertGreaterEqual(report["blink_count"], 0)
        self.assertIsNotNone(report["blink_rate_per_minute"])
        self.assertIn(report["detector"], {"tasks_face_landmarker", "solutions_face_mesh"})
        self.assertGreater(report["blink_count"], 0)


class Check02BlinkRegressionTests(unittest.TestCase):
    def test_check02_no_longer_reports_zero_when_troughs_exist(self):
        video = ENGINE_ROOT / "videos" / "video_check-02.mp4"
        if not video.is_file():
            self.skipTest("video_check-02.mp4 is not present")
        report = BlinkSampler().measure_blinks(str(video))
        self.assertEqual(report["status"], "available", report)
        self.assertGreater(report["blink_count"], 0, report)


if __name__ == "__main__":
    unittest.main()
