"""Speaker diarization + student-role assignment (no Whisper/video weights).

Run:
  python -m unittest VivaEvaluationEngine.tests.test_diarization -v
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

import numpy as np

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.diarization import (
    assign_student_speaker,
    assign_words_to_speakers,
    collapse_excluded_gaps,
    diarize_waveform,
    looks_like_same_voice_overcluster,
    words_and_text_for_speaker,
)


def _tone(freq: float, seconds: float, sr: int, amplitude: float) -> np.ndarray:
    t = np.arange(int(seconds * sr), dtype=np.float64) / sr
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class CollapseGapTests(unittest.TestCase):
    def test_examiner_gap_is_removed_from_word_timeline(self):
        words = [
            {"word": "hello", "start": 0.0, "end": 0.4},
            {"word": "world", "start": 5.0, "end": 5.4},
        ]
        remapped = collapse_excluded_gaps(
            words,
            [{"start": 0.5, "end": 4.5, "speaker": "SPEAKER_01"}],
        )
        self.assertAlmostEqual(remapped[0]["start"], 0.0, places=3)
        self.assertAlmostEqual(remapped[1]["start"], 1.0, places=3)
        gap = remapped[1]["start"] - remapped[0]["end"]
        self.assertLess(gap, 1.0)


class WordAssignmentTests(unittest.TestCase):
    def test_words_split_by_speaker_midpoint(self):
        segments = [
            {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00"},
            {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01"},
        ]
        words = [
            {"word": "student", "start": 0.2, "end": 0.6},
            {"word": "lecturer", "start": 2.4, "end": 2.9},
        ]
        labeled = assign_words_to_speakers(words, segments)
        self.assertEqual(labeled[0]["speaker"], "SPEAKER_00")
        self.assertEqual(labeled[1]["speaker"], "SPEAKER_01")

        student_text, student_words, _ = words_and_text_for_speaker(
            words,
            [
                {"start": 0.0, "end": 1.0, "text": "student"},
                {"start": 2.2, "end": 3.0, "text": "lecturer"},
            ],
            segments,
            "SPEAKER_00",
        )
        self.assertEqual(student_text.lower(), "student")
        self.assertEqual(len(student_words), 1)


class RoleAssignmentTests(unittest.TestCase):
    def test_quiet_on_camera_student_beats_loud_lecturer(self):
        speakers = [
            {"id": "SPEAKER_00", "speaking_seconds": 8.0, "rms_mean": 0.09},
            {"id": "SPEAKER_01", "speaking_seconds": 3.0, "rms_mean": 0.02},
        ]
        segments = [
            {"start": 0.0, "end": 3.0, "speaker": "SPEAKER_01"},
            {"start": 3.0, "end": 11.0, "speaker": "SPEAKER_00"},
        ]
        face_cues = [
            {"time": 0.5, "mouth_open": 0.55, "talking": True, "valid": True},
            {"time": 1.5, "mouth_open": 0.50, "talking": True, "valid": True},
            {"time": 2.5, "mouth_open": 0.48, "talking": True, "valid": True},
            {"time": 4.0, "mouth_open": 0.12, "talking": False, "valid": True},
            {"time": 6.0, "mouth_open": 0.10, "talking": False, "valid": True},
            {"time": 8.0, "mouth_open": 0.11, "talking": False, "valid": True},
            {"time": 10.0, "mouth_open": 0.09, "talking": False, "valid": True},
        ]
        student, method = assign_student_speaker(
            speakers, segments, face_cues=face_cues
        )
        self.assertEqual(student, "SPEAKER_01")
        self.assertEqual(method, "on_camera_mouth")

    def test_loudness_is_ignored_without_mouth_cues(self):
        speakers = [
            {"id": "SPEAKER_00", "speaking_seconds": 3.0, "rms_mean": 0.08},
            {"id": "SPEAKER_01", "speaking_seconds": 8.0, "rms_mean": 0.02},
        ]
        student, method = assign_student_speaker(speakers, [])
        self.assertEqual(student, "SPEAKER_01")
        self.assertEqual(method, "longest_speech")

    def test_manual_override(self):
        prev = os.environ.get("VIVA_STUDENT_SPEAKER")
        os.environ["VIVA_STUDENT_SPEAKER"] = "SPEAKER_01"
        try:
            speakers = [
                {"id": "SPEAKER_00", "speaking_seconds": 9.0, "rms_mean": 0.09},
                {"id": "SPEAKER_01", "speaking_seconds": 1.0, "rms_mean": 0.01},
            ]
            student, method = assign_student_speaker(speakers, [])
            self.assertEqual(student, "SPEAKER_01")
            self.assertEqual(method, "manual")
        finally:
            if prev is None:
                os.environ.pop("VIVA_STUDENT_SPEAKER", None)
            else:
                os.environ["VIVA_STUDENT_SPEAKER"] = prev


class TwoToneDiarizationTests(unittest.TestCase):
    def test_two_sequential_tones_become_two_speakers(self):
        sr = 16000
        student = _tone(180, 4.0, sr, amplitude=0.35)
        examiner = _tone(720, 4.0, sr, amplitude=0.12)
        y = np.concatenate([student, examiner])
        result = diarize_waveform(y, sr, max_speakers=2)
        self.assertGreaterEqual(result["speaker_count"], 2, result)
        speakers = {item["speaker"] for item in result["segments"]}
        self.assertGreaterEqual(len(speakers), 2)

        # First 1s should be speaker 00; last 1s a different speaker.
        early = next(item["speaker"] for item in result["segments"] if item["start"] < 1.0)
        late = next(item["speaker"] for item in reversed(result["segments"]) if item["end"] > 7.0)
        self.assertNotEqual(early, late)

    def test_single_tone_stays_one_speaker(self):
        sr = 16000
        y = _tone(180, 5.0, sr, amplitude=0.3)
        result = diarize_waveform(y, sr, max_speakers=2)
        self.assertEqual(result["speaker_count"], 1)

    def test_rapid_pingpong_segments_are_overcluster(self):
        segments = []
        t = 0.0
        for i in range(14):
            segments.append(
                {
                    "start": t,
                    "end": t + 1.2,
                    "speaker": "SPEAKER_00" if i % 2 == 0 else "SPEAKER_01",
                }
            )
            t += 1.2
        self.assertTrue(looks_like_same_voice_overcluster(segments))

    def test_two_long_blocks_are_not_overcluster(self):
        segments = [
            {"start": 0.0, "end": 8.0, "speaker": "SPEAKER_00"},
            {"start": 8.0, "end": 16.0, "speaker": "SPEAKER_01"},
        ]
        self.assertFalse(looks_like_same_voice_overcluster(segments))

    def test_same_face_talking_through_both_clusters_collapses(self):
        segments = [
            {"start": 0.0, "end": 8.0, "speaker": "SPEAKER_00"},
            {"start": 8.0, "end": 16.0, "speaker": "SPEAKER_01"},
        ]
        same_mouth = [{"time": float(t), "mouth_open": 0.44} for t in range(16)]
        self.assertTrue(looks_like_same_voice_overcluster(segments, face_cues=same_mouth))
        split_mouth = [
            {"time": float(t), "mouth_open": 0.52 if t < 8 else 0.11} for t in range(16)
        ]
        self.assertFalse(looks_like_same_voice_overcluster(segments, face_cues=split_mouth))


if __name__ == "__main__":
    unittest.main()
