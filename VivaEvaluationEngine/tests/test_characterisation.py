"""Characterisation tests for viva scoring integrity + transcript/LLM layers.

Run from repo (no ML weights required):
  python -m unittest VivaEvaluationEngine.tests.test_characterisation -v
or from VivaEvaluationEngine:
  python -m unittest tests.test_characterisation -v
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from config import assert_emotion_classes_covered, canonical_emotion_label
from services.llm_judge import (
    _validate_judge_payload,
    assemble_judge_input,
    build_formula_judge_scores,
    run_llm_judge,
)
from services.scoring import compute_confidence_score, compute_engagement_score
from services.transcript_features import extract_transcript_features
from services.viva_analysis import _audio_is_sufficient, _score_audio_grade


class TaxonomyTests(unittest.TestCase):
    def test_anger_aliases_to_angry(self):
        self.assertEqual(canonical_emotion_label("anger"), "angry")
        assert_emotion_classes_covered(
            ["neutral", "happy", "sad", "surprise", "fear", "disgust", "anger", "contempt"]
        )

    def test_anger_and_sad_share_confidence_penalty_path(self):
        anger = [{"emotion": "anger", "emotion_confidence": 0.9}] * 10
        sad = [{"emotion": "sad", "emotion_confidence": 0.9}] * 10
        self.assertEqual(compute_confidence_score(anger), compute_confidence_score(sad))


class ScoringIntegrityTests(unittest.TestCase):
    def test_unmeasured_blinks_excluded(self):
        timeline = [
            {
                "emotion": "neutral",
                "engagement_label": "high",
                "engagement_model_score": 0.75,
            }
        ] * 5
        gaze = [{"gaze_ok": True, "yaw": 0.1}] * 5
        with_none = compute_engagement_score(timeline, gaze, None)
        with_zero = compute_engagement_score(timeline, gaze, 0.0)
        with_high = compute_engagement_score(timeline, gaze, 40.0)
        self.assertLess(with_high, with_zero)
        self.assertNotEqual(with_none, with_zero)

    def test_articulation_none_when_voice_quality_missing(self):
        _grade, breakdown = _score_audio_grade(
            {
                "pitch_mean": 180,
                "pitch_std": 20,
                "rms_mean": 0.05,
                "jitter_local": None,
                "shimmer_local": None,
                "hnr_mean": None,
                "voice_quality_measured": False,
                "duration_seconds": 30,
            },
            {"predicted_emotion": "neutral", "confidence": 0.35, "source": "heuristic"},
            "hello world this is a short transcript with enough words maybe",
            3,
        )
        self.assertIsNone(breakdown.get("articulation_score"))
        self.assertIn("articulation_score", breakdown.get("excluded_components"))

    def test_healthy_voice_quality_not_floored(self):
        _grade, breakdown = _score_audio_grade(
            {
                "pitch_mean": 180,
                "pitch_std": 20,
                "rms_mean": 0.05,
                "jitter_local": 0.01,
                "shimmer_local": 0.05,
                "hnr_mean": 15.0,
                "voice_quality_measured": True,
                "duration_seconds": 30,
            },
            {"predicted_emotion": "neutral", "confidence": 0.35, "source": "heuristic"},
            "hello world this is a short transcript with enough words maybe",
            3,
        )
        self.assertIsNotNone(breakdown.get("articulation_score"))
        self.assertGreater(breakdown["articulation_score"], 0.3)

    def test_heuristic_emotion_excluded_from_grade(self):
        _grade, breakdown = _score_audio_grade(
            {
                "pitch_mean": 180,
                "pitch_std": 20,
                "rms_mean": 0.05,
                "jitter_local": 0.01,
                "shimmer_local": 0.05,
                "hnr_mean": 15.0,
                "voice_quality_measured": True,
                "duration_seconds": 30,
            },
            {"predicted_emotion": "happy", "confidence": 0.9, "source": "heuristic"},
            "hello world this is a short transcript with enough words maybe",
            3,
        )
        self.assertIsNone(breakdown.get("emotion_score"))
        self.assertIn("emotion_score", breakdown.get("excluded_components"))
        self.assertTrue(breakdown.get("emotion_excluded"))

    def test_model_emotion_included_in_grade(self):
        _grade, breakdown = _score_audio_grade(
            {
                "pitch_mean": 180,
                "pitch_std": 20,
                "rms_mean": 0.05,
                "jitter_local": 0.01,
                "shimmer_local": 0.05,
                "hnr_mean": 15.0,
                "voice_quality_measured": True,
                "duration_seconds": 30,
            },
            {"predicted_emotion": "happy", "confidence": 0.9, "source": "model"},
            "hello world this is a short transcript with enough words maybe",
            3,
        )
        self.assertIsNotNone(breakdown.get("emotion_score"))
        self.assertNotIn("emotion_score", breakdown.get("excluded_components"))
        self.assertFalse(breakdown.get("emotion_excluded"))

    def test_silent_audio_insufficient(self):
        self.assertFalse(_audio_is_sufficient({"duration_seconds": 10, "rms_mean": 0, "pitch_mean": 0}, ""))
        self.assertTrue(_audio_is_sufficient({"duration_seconds": 10, "rms_mean": 0.02, "pitch_mean": 160}, "hello"))


class TranscriptFeatureTests(unittest.TestCase):
    def test_hedge_filler_and_rate(self):
        transcript = "I think maybe um I believe the answer is sort of clear."
        features = extract_transcript_features(
            transcript,
            segments=[
                {
                    "start": 0.0,
                    "end": 4.0,
                    "words": [
                        {"word": "I", "start": 0.0, "end": 0.2},
                        {"word": "think", "start": 0.2, "end": 0.5},
                        {"word": "maybe", "start": 0.6, "end": 0.9},
                        {"word": "um", "start": 1.5, "end": 1.7},
                        {"word": "I", "start": 1.8, "end": 1.9},
                        {"word": "believe", "start": 1.9, "end": 2.3},
                    ],
                }
            ],
            duration_seconds=60.0,
        )
        self.assertGreaterEqual(features["hedge_count"], 3)
        self.assertGreaterEqual(features["filler_count"], 1)
        self.assertEqual(features["pause_detection_granularity"], "word")
        self.assertGreater(features["pause_count"], 0)
        self.assertIsNotNone(features["speech_rate_wpm"])
        self.assertIn(features["speech_rate_band"], {"too_slow", "optimal", "too_fast"})


class LlmJudgeTests(unittest.TestCase):
    def test_schema_validation(self):
        ok = _validate_judge_payload(
            {
                "communication_clarity": {"score": 7, "justification": "Clear pacing."},
                "confidence": {"score": 6.5, "justification": "Stable pitch."},
                "engagement": {"score": 8, "justification": "High engagement ratio."},
            }
        )
        self.assertIsNotNone(ok)
        self.assertEqual(ok["communication_clarity"]["score"], 7.0)

        bad = _validate_judge_payload({"communication_clarity": {"score": 7}})
        self.assertIsNone(bad)

    def test_formula_fallback_and_attach_without_api_key(self):
        fallback = build_formula_judge_scores(
            confidence_score=70.0,
            engagement_score=80.0,
            audio_grade=6.5,
            transcript_features={"hedge_count": 2, "filler_count": 1, "speech_rate_band": "optimal"},
            grade_breakdown={"clarity_score": 0.7, "articulation_score": 0.8, "transcript_score": 0.5},
        )
        self.assertEqual(fallback["source"], "formula_fallback")
        self.assertTrue(0 <= fallback["communication_clarity"]["score"] <= 10)

        result = {
            "confidence_score": 70.0,
            "engagement_score": 80.0,
            "summary": {"positive_ratio": 0.5, "neutral_ratio": 0.4, "negative_ratio": 0.1},
            "engagement_summary": {"high_ratio": 0.6, "very_high_ratio": 0.2},
            "audio_analysis": {
                "audio_grade": 6.5,
                "transcript_excerpt": "I think this is the answer.",
                "transcript_features": {"hedge_count": 1, "filler_count": 0, "speech_rate_wpm": 140},
                "acoustic_features": {"duration_seconds": 30},
                "pitch_profile": {"level": "balanced"},
                "audio_emotion": {"predicted_emotion": "neutral", "source": "heuristic"},
                "grade_breakdown": {"clarity_score": 0.7},
            },
        }
        payload = assemble_judge_input(result)
        self.assertIn("transcript_features", payload)
        self.assertIn("video_summary", payload)

        # Force no API key path.
        import services.llm_judge as llm_judge

        original = llm_judge._api_key
        llm_judge._api_key = lambda: None
        try:
            evaluation = run_llm_judge(result)
        finally:
            llm_judge._api_key = original
        self.assertEqual(evaluation["status"], "fallback")
        self.assertEqual(evaluation["source"], "formula_fallback")


if __name__ == "__main__":
    unittest.main()
