"""Gaze and head-pose landmarks on the Tasks 478-pt mesh."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.engagement_scoring import aggregate_gaze, aggregate_head_pose
from services.face_landmarker import has_iris
from services.gaze_head_analyser import (
    GazeHeadAnalyser,
    classify_gaze_direction,
    gaze_metrics_from_landmarks,
    metrics_from_landmarks,
)


class _P:
    def __init__(self, x, y):
        self.x = x
        self.y = y


def _base_mesh():
    lm = [_P(0.5, 0.5) for _ in range(478)]
    lm[33] = _P(0.30, 0.40)
    lm[133] = _P(0.40, 0.40)
    lm[362] = _P(0.60, 0.40)
    lm[263] = _P(0.70, 0.40)
    # Iris rings centred on eye corners.
    for idx in range(468, 473):
        lm[idx] = _P(0.35, 0.40)
    for idx in range(473, 478):
        lm[idx] = _P(0.65, 0.40)
    lm[234] = _P(0.20, 0.50)
    lm[454] = _P(0.80, 0.50)
    lm[1] = _P(0.50, 0.35)
    lm[152] = _P(0.50, 0.70)
    lm[13] = _P(0.50, 0.55)
    lm[14] = _P(0.50, 0.57)
    lm[78] = _P(0.45, 0.56)
    lm[308] = _P(0.55, 0.56)
    return lm


class LandmarkPresenceTests(unittest.TestCase):
    def test_iris_required(self):
        self.assertTrue(has_iris(_base_mesh()))
        self.assertFalse(has_iris(_base_mesh()[:468]))
        self.assertIsNone(metrics_from_landmarks(_base_mesh()[:468]))
        self.assertIsNone(metrics_from_landmarks(None))


class GazeFixtureTests(unittest.TestCase):
    def test_camera_facing(self):
        metrics = gaze_metrics_from_landmarks(_base_mesh())
        self.assertTrue(metrics["gaze_ok"])
        self.assertEqual(metrics["gaze_direction"], "center")
        self.assertLess(metrics["sum_abs_dx"], 0.04)

    def test_looking_away(self):
        lm = _base_mesh()
        for idx in range(468, 473):
            lm[idx] = _P(0.48, 0.40)
        for idx in range(473, 478):
            lm[idx] = _P(0.78, 0.40)
        metrics = gaze_metrics_from_landmarks(lm)
        self.assertFalse(metrics["gaze_ok"])
        self.assertGreaterEqual(metrics["sum_abs_dx"], 0.04)
        self.assertEqual(metrics["gaze_direction"], "right")

    def test_analyser_from_landmarks(self):
        analyser = GazeHeadAnalyser()
        self.assertIsNotNone(analyser.from_landmarks(_base_mesh()))
        self.assertIsNone(analyser.from_landmarks(None))
        self.assertEqual(classify_gaze_direction(0.0, 0.0), "center")


class HeadFixtureTests(unittest.TestCase):
    def test_stable_vs_turn(self):
        center = gaze_metrics_from_landmarks(_base_mesh())
        left = _base_mesh()
        left[234] = _P(0.35, 0.50)
        left[454] = _P(0.72, 0.50)
        right = _base_mesh()
        right[234] = _P(0.28, 0.50)
        right[454] = _P(0.90, 0.50)
        tilt = _base_mesh()
        tilt[33] = _P(0.30, 0.35)
        tilt[133] = _P(0.40, 0.35)
        turned_left = gaze_metrics_from_landmarks(left)
        turned_right = gaze_metrics_from_landmarks(right)
        tilted = gaze_metrics_from_landmarks(tilt)
        self.assertNotAlmostEqual(center["yaw_proxy"], turned_left["yaw_proxy"], places=3)
        self.assertNotAlmostEqual(center["yaw_proxy"], turned_right["yaw_proxy"], places=3)
        self.assertNotAlmostEqual(center["roll_proxy"], tilted["roll_proxy"], places=3)

        stable = aggregate_head_pose([center, center, dict(center)])
        moving = aggregate_head_pose([center, turned_left, turned_right])
        self.assertEqual(stable["status"], "available")
        self.assertGreater(stable["stability_score"], moving["stability_score"])
        self.assertTrue(stable["not_euler_degrees"])

    def test_missing_landmarks_unavailable(self):
        self.assertEqual(aggregate_gaze([None, None])["status"], "unavailable")
        self.assertEqual(aggregate_head_pose([None, None])["status"], "unavailable")
        self.assertIsNone(aggregate_gaze([None, None])["gaze_on_camera_ratio"])


class RealVideoGazeTests(unittest.TestCase):
    def test_tasks_gaze_available_on_only_boy(self):
        from services.face_landmarker import iter_landmark_samples, nearest_landmarks

        video = ENGINE_ROOT / "videos" / "only boy talking.mp4"
        if not video.is_file():
            self.skipTest("37s fixture video is not present")
        samples = list(iter_landmark_samples(str(video), sample_fps=10))
        valid = [s for s in samples if s.landmarks is not None]
        self.assertGreater(len(valid), 0)
        self.assertTrue(has_iris(valid[0].landmarks))
        metrics = metrics_from_landmarks(valid[0].landmarks)
        self.assertIsNotNone(metrics)
        self.assertIn("gaze_ok", metrics)
        self.assertIn("yaw_proxy", metrics)
        # One-pass lookup used by analyze_video.
        self.assertIsNotNone(nearest_landmarks(samples, valid[0].time_sec))


if __name__ == "__main__":
    unittest.main()
