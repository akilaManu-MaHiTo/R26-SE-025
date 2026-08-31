"""Face-crop quality gate tests (no ML weights).

Run:
  python -m unittest VivaEvaluationEngine.tests.test_face_quality -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.face_quality import assess_face_crop, enhance_face_crop, prepare_face_for_emotion
from services.scoring import compute_confidence_score


def _checkerboard(size: int = 128) -> np.ndarray:
    tile = size // 8
    img = np.zeros((size, size), dtype=np.uint8)
    for row in range(0, size, tile):
        for col in range(0, size, tile):
            if ((row // tile) + (col // tile)) % 2 == 0:
                img[row : row + tile, col : col + tile] = 220
            else:
                img[row : row + tile, col : col + tile] = 40
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


class FaceQualityTests(unittest.TestCase):
    def test_sharp_crop_passes(self):
        result = assess_face_crop(_checkerboard())
        self.assertTrue(result["ok"], result)
        self.assertIsNone(result["reason"])

    def test_blurry_crop_rejected(self):
        sharp = _checkerboard()
        blurry = cv2.GaussianBlur(sharp, (31, 31), 12)
        result = assess_face_crop(blurry)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "blurry")

    def test_dark_crop_rejected(self):
        dark = np.full((96, 96, 3), 8, dtype=np.uint8)
        result = assess_face_crop(dark)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "dark")

    def test_tiny_crop_rejected(self):
        tiny = _checkerboard(32)
        result = assess_face_crop(tiny)
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "too_small")

    def test_empty_rejected(self):
        result = assess_face_crop(np.zeros((0, 0, 3), dtype=np.uint8))
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "empty")

    def test_enhance_lifts_dark_crop(self):
        dark = np.full((96, 96, 3), 18, dtype=np.uint8)
        dark[:, 40:56] = 40
        enhanced, steps = enhance_face_crop(dark)
        self.assertIn("clahe", steps)
        self.assertGreater(assess_face_crop(enhanced)["brightness"], assess_face_crop(dark)["brightness"])

    def test_prepare_scores_blurry_webcam_crop(self):
        blurry = cv2.GaussianBlur(_checkerboard(), (15, 15), 4)
        prepared = prepare_face_for_emotion(blurry)
        self.assertTrue(prepared["scored"])
        self.assertIsNotNone(prepared["crop"])
        self.assertTrue(prepared["enhanced"])
        self.assertIn("denoise", prepared["steps"])
        self.assertIn("clahe", prepared["steps"])

    def test_prepare_skips_only_tiny_crops(self):
        prepared = prepare_face_for_emotion(_checkerboard(32))
        self.assertFalse(prepared["scored"])
        self.assertIsNone(prepared["crop"])
        self.assertEqual(prepared["warning"], "too_small")

    def test_low_quality_frames_do_not_pollute_positivity(self):
        happy = [{"emotion": "happy", "emotion_confidence": 0.9}] * 5
        junk = [{"emotion": "LowQuality", "emotion_confidence": 0.0}] * 20
        mixed = compute_confidence_score(happy + junk)
        clean = compute_confidence_score(happy)
        self.assertEqual(mixed, clean)


if __name__ == "__main__":
    unittest.main()
