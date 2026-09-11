"""Feature-complete baseline: extraction, sub-scores, gates, regression.

Does not require CNN/Whisper weights except optional MFCC (librosa).
"""
from __future__ import annotations

import math
import struct
import sys
import tempfile
import unittest
import wave
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from config import EMOTION_ENGAGEMENT_MAP, ENGAGEMENT_FEATURE_WEIGHTS
from extract_features import extract_acoustic_features
from services.assessment_scoring import (
    FAMILY_WEIGHTS,
    FUSION_WEIGHT_AI,
    FUSION_WEIGHT_TECHNICAL,
    GRADE_BANDS,
    MODE_WITH,
    MODE_WITHOUT,
    STATUS_INCOMPLETE,
    attach_assessment,
    build_assessment,
    resolve_grade,
)
from services.audio_scoring import AUDIO_FEATURE_WEIGHTS, compute_audio_score
from services.engagement_scoring import (
    aggregate_emotion,
    aggregate_gaze,
    aggregate_head_pose,
    compute_engagement_score,
)
from services.feature_complete import (
    ENGAGEMENT_METRIC_DIAGNOSTIC,
    ENGAGEMENT_METRIC_FEATURE_COMPLETE,
    ENGAGEMENT_METRIC_STAGE1_CNN,
    attach_feature_complete,
)
from services.gaze_head_analyser import classify_gaze_direction, gaze_metrics_from_landmarks
from services.normalization import blink_rate_score, head_pose_stability_score, speech_rate_score
from services.score_utils import weighted_mean_available
from services.temporal_engagement import TemporalEngagementModel
from services.transcript_features import extract_transcript_features
from services.transcript_scoring import NO_STUDENT_TRANSCRIPT, compute_transcript_score
from tests.test_assessment_scoring import _sample_result


class QualityGateRegressionTests(unittest.TestCase):
    def test_face_unavailable_final_null(self):
        result = _sample_result(video_status="insufficient_face_coverage")
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIsNone(assessment["final_score"])

    def test_no_speech_final_null(self):
        result = _sample_result()
        result["audio_analysis"]["transcript_word_count"] = 0
        result["audio_analysis"]["transcript_features"]["word_count"] = 0
        result["audio_analysis"]["acoustic_features"]["rms_mean"] = 0.0002
        result["audio_analysis"]["acoustic_features"]["pitch_mean_hz"] = 0.0
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIsNone(assessment["final_score"])

    def test_valid_recording_allows_score(self):
        assessment = build_assessment(_sample_result())
        self.assertNotEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIsNotNone(assessment["final_score"])


class EmotionGazeHeadBlinkTests(unittest.TestCase):
    def test_emotion_aggregate_neutral_happy_surprise(self):
        timeline = [
            {"valid": True, "emotion": "neutral", "emotion_confidence": 0.9},
            {"valid": True, "emotion": "happy", "emotion_confidence": 0.8},
            {"valid": True, "emotion": "surprise", "emotion_confidence": 0.7},
        ]
        expected = (
            EMOTION_ENGAGEMENT_MAP["neutral"]
            + EMOTION_ENGAGEMENT_MAP["happy"]
            + EMOTION_ENGAGEMENT_MAP["surprise"]
        ) / 3
        got = aggregate_emotion(timeline)
        self.assertEqual(got["status"], "available")
        self.assertAlmostEqual(got["score"], expected, places=4)

    def test_gaze_on_camera_ratio_monotonic(self):
        high = aggregate_gaze([{"gaze_ok": True}] * 9 + [{"gaze_ok": False}])
        low = aggregate_gaze([{"gaze_ok": True}] * 3 + [{"gaze_ok": False}] * 7)
        self.assertGreater(high["gaze_on_camera_ratio"], low["gaze_on_camera_ratio"])
        self.assertAlmostEqual(high["gaze_on_camera_ratio"], 0.9, places=4)

    def test_head_stable_beats_extreme(self):
        stable = head_pose_stability_score(0.001, 0.001, 0.001)
        moderate = head_pose_stability_score(0.04, 0.04, 0.03)
        extreme = head_pose_stability_score(0.2, 0.2, 0.2)
        self.assertGreater(stable, moderate)
        self.assertGreater(moderate, extreme)

    def test_head_aggregate_uses_proxy_names(self):
        signals = [
            {"yaw_proxy": 0.10, "pitch_proxy": 0.20, "roll_proxy": 0.01},
            {"yaw_proxy": 0.12, "pitch_proxy": 0.22, "roll_proxy": 0.02},
        ]
        got = aggregate_head_pose(signals)
        self.assertEqual(got["status"], "available")
        self.assertIn("yaw_proxy_std", got)
        self.assertTrue(got["not_euler_degrees"])
        self.assertEqual(got["unit"], "normalized_landmark_distance")
        self.assertEqual(got["head_stability"], got["stability_score"])
        legacy = aggregate_head_pose(
            [{"yaw": 0.10, "pitch": 0.20, "roll": 0.01}, {"yaw": 0.12, "pitch": 0.22, "roll": 0.02}]
        )
        self.assertAlmostEqual(got["yaw_proxy_std"], legacy["yaw_proxy_std"])

    def test_blink_rate_mapping(self):
        self.assertAlmostEqual(blink_rate_score(0.0), 1.0)
        self.assertAlmostEqual(blink_rate_score(10.0), 1.0)
        self.assertAlmostEqual(blink_rate_score(25.0), 1.0)
        self.assertAlmostEqual(blink_rate_score(40.0), 0.85)
        self.assertIsNone(blink_rate_score(None))

    def test_gaze_direction_center_and_left(self):
        self.assertEqual(classify_gaze_direction(0.0, 0.0), "center")
        self.assertEqual(classify_gaze_direction(-0.05, 0.0), "left")

    def test_gaze_metrics_exposes_xy(self):
        class _P:
            def __init__(self, x, y):
                self.x = x
                self.y = y

        lm = [_P(0.5, 0.5) for _ in range(478)]
        metrics = gaze_metrics_from_landmarks(lm)
        self.assertIn("gaze_x", metrics)
        self.assertIn("gaze_y", metrics)
        self.assertIn("gaze_direction", metrics)
        self.assertIn("yaw_proxy", metrics)
        self.assertIn("pitch_proxy", metrics)
        self.assertIn("roll_proxy", metrics)
        self.assertEqual(metrics["yaw_proxy"], metrics["yaw"])
        self.assertIn("roll", metrics)
        self.assertTrue(metrics["gaze_ok"])
        self.assertFalse(aggregate_gaze([metrics])["validated"])


class EngagementMixTests(unittest.TestCase):
    def _bundle(self, emotion=1.0, gaze=1.0, head=1.0, blink=1.0, temporal=None, temporal_status="unavailable"):
        blink_raw = None if blink is None else 25.0
        return {
            "video_features": {
                "emotion": {"status": "unavailable" if emotion is None else "available", "score": emotion},
                "gaze": {
                    "status": "unavailable" if gaze is None else "available",
                    "gaze_on_camera_ratio": gaze,
                },
                "head_pose": {
                    "status": "unavailable" if head is None else "available",
                    "stability_score": head,
                },
                "blink": {
                    "status": "unavailable" if blink is None else "available",
                    "blink_rate_per_minute": blink_raw,
                },
                "temporal_engagement": {"status": temporal_status, "score": temporal},
            }
        }

    def test_all_ones(self):
        result = compute_engagement_score(self._bundle(temporal=1.0, temporal_status="ready"))
        self.assertAlmostEqual(result["score"], 1.0)
        self.assertTrue(result["available"])

    def test_all_zeros_measured(self):
        forced = self._bundle(0, 0, 0, blink=0.0, temporal=0.0, temporal_status="ready")
        forced["video_features"]["blink"]["blink_rate_per_minute"] = 125.0
        result = compute_engagement_score(forced)
        self.assertAlmostEqual(result["score"], 0.0)

    def test_documented_mix(self):
        parts = {"emotion": 0.8, "gaze": 0.9, "head": 0.7, "blink": 0.8, "temporal": 0.5}
        expected, _ = weighted_mean_available(parts, ENGAGEMENT_FEATURE_WEIGHTS)
        bundle = self._bundle(0.8, 0.9, 0.7, blink=0.8, temporal=0.5, temporal_status="ready")
        # blink 0.8 corresponds to 25 + (1-0.8)/0.01 = 45 bpm
        bundle["video_features"]["blink"]["blink_rate_per_minute"] = 45.0
        result = compute_engagement_score(bundle)
        self.assertAlmostEqual(result["score"], expected, places=3)

    def test_lstm_missing_renormalizes_to_one(self):
        result = compute_engagement_score(self._bundle(1, 1, 1, blink=1.0))
        self.assertAlmostEqual(result["score"], 1.0)
        self.assertNotIn("temporal", result["family_weights_applied"])

    def test_gaze_missing_renormalizes(self):
        result = compute_engagement_score(self._bundle(1, None, 1, blink=1.0))
        self.assertAlmostEqual(result["score"], 1.0)
        self.assertNotIn("gaze", result["family_weights_applied"])

    def test_blink_missing(self):
        result = compute_engagement_score(self._bundle(1, 1, 1, blink=None))
        self.assertAlmostEqual(result["score"], 1.0)

    def test_only_one_signal(self):
        result = compute_engagement_score(self._bundle(0.4, None, None, blink=None))
        self.assertAlmostEqual(result["score"], 0.4)
        self.assertEqual(list(result["family_weights_applied"].keys()), ["emotion"])

    def test_no_usable_facial_signals(self):
        result = compute_engagement_score(self._bundle(None, None, None, blink=None))
        self.assertIsNone(result["score"])
        self.assertFalse(result["available"])


class AudioFeatureTests(unittest.TestCase):
    def test_speech_rate_60_words_30s(self):
        self.assertAlmostEqual(speech_rate_score(120.0, word_count=60), 1.0)
        features = extract_transcript_features(
            " ".join(["word"] * 60),
            duration_seconds=30.0,
        )
        self.assertEqual(features["speech_rate_wpm"], 120.0)
        self.assertEqual(features["speech_rate_band"], "optimal")

    def test_speech_rate_normalization_grid(self):
        self.assertIsNone(speech_rate_score(0.0, word_count=0))
        self.assertAlmostEqual(speech_rate_score(0.0, word_count=1), 0.0)
        self.assertAlmostEqual(speech_rate_score(60.0), 0.5)
        self.assertLess(speech_rate_score(119.0), 1.0)
        self.assertAlmostEqual(speech_rate_score(120.0), 1.0)
        self.assertAlmostEqual(speech_rate_score(140.0), 1.0)
        self.assertAlmostEqual(speech_rate_score(160.0), 1.0)
        self.assertLess(speech_rate_score(161.0), 1.0)
        self.assertGreater(speech_rate_score(161.0), speech_rate_score(250.0))

    def test_energy_consistency_is_not_loudness(self):
        from services.normalization import energy_consistency_score

        quiet = energy_consistency_score(0.02, 0.004)
        loud = energy_consistency_score(0.20, 0.040)
        self.assertAlmostEqual(quiet, loud)
        self.assertGreater(energy_consistency_score(0.05, 0.005), energy_consistency_score(0.05, 0.05))

    def test_audio_family_does_not_score_energy_or_mfcc_or_ser(self):
        payload = compute_audio_score(
            {
                "audio_features": {
                    "pitch_std_hz": 20.0,
                    "pitch_measured": True,
                    "hnr_mean_db": 18.0,
                    "jitter_local": 0.006,
                    "shimmer_local": 0.04,
                    "voice_quality_measured": True,
                    "rms_mean": 0.05,
                    "rms_std": 0.01,
                    "mfcc_mean": [0.0] * 13,
                },
                "ser": {"source": "model", "emotion": "angry", "confidence": 0.99},
            }
        )
        self.assertNotIn("energy_consistency", payload["family_weights_applied"])
        self.assertNotIn("ser", payload["family_weights_applied"])
        self.assertEqual(payload["components"]["energy_consistency"]["status"], "available")
        self.assertEqual(payload["components"]["ser"]["normalized"], None)

    def test_empty_transcript_not_slow(self):
        features = extract_transcript_features("", duration_seconds=30.0)
        self.assertEqual(features["speech_rate_band"], "unknown")
        self.assertIsNone(features["speech_rate_wpm"])
        self.assertIsNone(speech_rate_score(0.0, word_count=0))
        scored = compute_transcript_score({"transcript_features": features})
        self.assertIsNone(scored["score"])
        self.assertFalse(scored["available"])
        self.assertEqual(scored["reason"], NO_STUDENT_TRANSCRIPT)
        self.assertNotEqual(scored["score"], 1.0)

    def test_audio_score_excludes_speech_rate(self):
        payload = compute_audio_score(
            {
                "audio_features": {
                    "pitch_std_hz": 20.0,
                    "pitch_measured": True,
                    "hnr_mean_db": 18.0,
                    "jitter_local": 0.006,
                    "shimmer_local": 0.04,
                    "voice_quality_measured": True,
                    "rms_mean": 0.05,
                    "rms_std": 0.01,
                },
                "transcript_features": {"speech_rate_wpm": 140, "word_count": 40},
                "ser": {"source": "heuristic", "emotion": "neutral", "confidence": 0.3},
            }
        )
        self.assertNotIn("speech_rate", AUDIO_FEATURE_WEIGHTS)
        self.assertNotIn("speech_rate", payload["family_weights_applied"])
        self.assertEqual(set(payload["family_weights_applied"]), {"pitch_stability", "clarity_hnr", "articulation"})
        self.assertEqual(payload["components"]["speech_rate"]["status"], "diagnostic_only")
        self.assertFalse(payload["components"]["speech_rate"]["available"])
        tx = compute_transcript_score(
            {
                "transcript_features": extract_transcript_features(
                    "We use JWT tokens in NestJS for authentication.",
                    duration_seconds=20,
                )
            }
        )
        self.assertIn("speech_rate", tx["family_weights_applied"])

    def test_mfcc_shape_on_sine(self):
        handle = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        handle.close()
        path = handle.name
        try:
            with wave.open(path, "w") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                frames = []
                for i in range(16000):
                    sample = int(16000 * math.sin(2 * math.pi * 220 * i / 16000))
                    frames.append(struct.pack("<h", max(-32767, min(32767, sample))))
                wav.writeframes(b"".join(frames))
            acoustics = extract_acoustic_features(path)
            self.assertEqual(len(acoustics["mfcc_mean"]), 13)
            self.assertEqual(len(acoustics["mfcc_std"]), 13)
            self.assertEqual(acoustics["mfcc_n_coefficients"], 13)
            self.assertEqual(acoustics["mfcc_sample_rate"], 16000)
            self.assertEqual(acoustics["mfcc_role"], "feature_representation")
            self.assertIn("rms_std", acoustics)
            self.assertIn("pitch_std", acoustics)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_audio_score_schema_mocked_ser(self):
        payload = compute_audio_score(
            {
                "audio_features": {
                    "pitch_std_hz": 20.0,
                    "pitch_measured": True,
                    "hnr_mean_db": 18.0,
                    "jitter_local": 0.006,
                    "shimmer_local": 0.04,
                    "voice_quality_measured": True,
                    "rms_mean": 0.05,
                    "rms_std": 0.01,
                },
                "transcript_features": {"speech_rate_wpm": 140, "word_count": 40},
                "ser": {"source": "heuristic", "emotion": "neutral", "confidence": 0.3},
            }
        )
        self.assertTrue(payload["available"])
        self.assertGreaterEqual(payload["score"], 0.0)
        self.assertLessEqual(payload["score"], 1.0)
        self.assertFalse(payload["components"]["ser"]["available"])
        self.assertNotIn("speech_rate", payload["family_weights_applied"])


class TranscriptSignalTests(unittest.TestCase):
    def test_hedges(self):
        features = extract_transcript_features("I think maybe this is probably the design.")
        self.assertGreaterEqual(features["hedge_count"], 3)

    def test_fillers_without_like(self):
        features = extract_transcript_features("um uh like hmm the database")
        self.assertGreaterEqual(features["filler_count"], 3)
        words = [hit["word"] for hit in features["filler_words"]]
        self.assertNotIn("like", words)

    def test_sentence_completion(self):
        complete = extract_transcript_features("This is a full sentence. Another one!")
        incomplete = extract_transcript_features("This is a fragment")
        self.assertEqual(complete["sentence_completion_ratio"], 1.0)
        self.assertEqual(complete["fragmented_sentence_count"], 0)
        self.assertEqual(incomplete["fragmented_sentence_count"], 1)
        self.assertFalse(complete["response_structure"]["scored"])
        self.assertEqual(complete["response_structure"]["status"], "diagnostic_only")
        empty = extract_transcript_features("")
        self.assertEqual(empty["response_structure"]["reason"], "no_student_transcript")

    def test_pauses_threshold(self):
        words = [
            {"word": "a", "start": 0.0, "end": 0.2},
            {"word": "b", "start": 0.4, "end": 0.5},  # 0.2s gap
            {"word": "c", "start": 1.1, "end": 1.2},  # 0.6s
            {"word": "d", "start": 2.5, "end": 2.6},  # 1.3s
        ]
        features = extract_transcript_features(
            "a b c d",
            words_with_times=words,
            duration_seconds=3.0,
        )
        self.assertEqual(features["pause_count"], 2)
        self.assertEqual(features["long_pause_count"], 0)
        self.assertGreater(features["total_pause_duration"], 1.8)

    def test_transcript_score_bounded(self):
        score = compute_transcript_score(
            {
                "transcript_features": extract_transcript_features(
                    "I think the module uses JWT. We store tokens in httpOnly cookies.",
                    duration_seconds=20,
                )
            }
        )
        self.assertTrue(score["available"])
        self.assertGreaterEqual(score["score"], 0.0)
        self.assertLessEqual(score["score"], 1.0)


class IntegrationAndRegressionTests(unittest.TestCase):
    def test_pipeline_preserves_stage1_and_adds_feature_complete(self):
        result = _sample_result()
        result["video_features"] = {
            "emotion": {"status": "available", "score": 0.9},
            "gaze": {"status": "available", "gaze_on_camera_ratio": 0.85},
            "head_pose": {"status": "available", "stability_score": 0.8},
            "blink": {"status": "available", "blink_rate_per_minute": 12.0},
            "temporal_engagement": {"status": "unavailable", "score": None},
        }
        baseline = build_assessment(result)
        attached = attach_assessment(result)
        fc = attached["feature_complete"]
        self.assertEqual(attached["assessment"]["final_score"], baseline["final_score"])
        self.assertEqual(baseline["final_score"], 72.09)
        self.assertEqual(baseline["grade"], "B+")
        self.assertIn("derived_features", fc)
        self.assertIn("raw_measurements", fc["layers"])
        self.assertEqual(fc["layers"]["final_score"], baseline["final_score"])
        self.assertEqual(fc["layers"]["current_stage1_score"], baseline["final_score"])
        self.assertEqual(attached["assessment"]["ai_performance"]["score"], baseline["ai_performance"]["score"])
        self.assertIn("feature_complete", attached)
        self.assertIn("scoring", attached)
        self.assertIsNotNone(fc["engagement_feature_score"])
        self.assertIsNotNone(fc["audio_feature_score"])
        self.assertIsNotNone(fc["transcript_feature_score"])
        for key in ("engagement_feature_score", "audio_feature_score", "transcript_feature_score"):
            value = fc[key]
            self.assertGreaterEqual(value, 0.0)
            self.assertLessEqual(value, 1.0)
        self.assertEqual(fc["current_stage1"]["ai_performance"], baseline["ai_performance"]["score"])
        self.assertIn("raw_measurements", fc)
        self.assertIn("layers", fc)
        metrics = attached["engagement_metrics"]
        self.assertEqual(metrics[ENGAGEMENT_METRIC_STAGE1_CNN]["metric_id"], ENGAGEMENT_METRIC_STAGE1_CNN)
        self.assertEqual(metrics[ENGAGEMENT_METRIC_DIAGNOSTIC]["metric_id"], ENGAGEMENT_METRIC_DIAGNOSTIC)
        self.assertEqual(metrics[ENGAGEMENT_METRIC_FEATURE_COMPLETE]["metric_id"], ENGAGEMENT_METRIC_FEATURE_COMPLETE)
        self.assertEqual(
            metrics[ENGAGEMENT_METRIC_FEATURE_COMPLETE]["value"],
            fc["engagement_feature_score"],
        )
        self.assertEqual(
            metrics[ENGAGEMENT_METRIC_STAGE1_CNN]["value"],
            attached["assessment"]["features"]["video"]["average_engagement_score"],
        )
        self.assertNotEqual(
            ENGAGEMENT_METRIC_STAGE1_CNN,
            ENGAGEMENT_METRIC_FEATURE_COMPLETE,
        )

    def test_incomplete_recording_nulls_feature_complete_scores_keeps_raw(self):
        result = _sample_result(video_status="insufficient_face_coverage")
        result["video_features"] = {
            "emotion": {"status": "available", "score": 0.9},
            "gaze": {"status": "available", "gaze_on_camera_ratio": 0.85},
            "head_pose": {"status": "available", "stability_score": 0.8},
            "blink": {"status": "available", "blink_rate_per_minute": 12.0},
            "temporal_engagement": {"status": "unavailable", "score": None},
        }
        attached = attach_assessment(result)
        self.assertEqual(attached["assessment"]["status"], STATUS_INCOMPLETE)
        self.assertIsNone(attached["assessment"]["final_score"])
        fc = attached["feature_complete"]
        self.assertIsNone(fc["engagement_feature_score"])
        self.assertIsNone(fc["audio_feature_score"])
        self.assertIsNone(fc["transcript_feature_score"])
        self.assertIsNone(attached["scoring"]["feature_complete"]["engagement"])
        self.assertIsNone(attached["scoring"]["feature_complete"]["audio"])
        self.assertIsNone(attached["scoring"]["feature_complete"]["transcript"])
        self.assertIsNotNone(fc["audio_features"]["pitch_std_hz"])
        self.assertGreaterEqual(fc["transcript_features"]["word_count"], 0)
        self.assertEqual(fc["raw_measurements"]["audio_features"]["pitch_std_hz"], fc["audio_features"]["pitch_std_hz"])

    def test_no_speech_feature_complete_scores_null(self):
        result = _sample_result()
        result["audio_analysis"]["transcript"] = ""
        result["audio_analysis"]["transcript_word_count"] = 0
        result["audio_analysis"]["transcript_features"] = extract_transcript_features("", duration_seconds=8.0)
        result["audio_analysis"]["acoustic_features"]["rms_mean"] = 0.0002
        result["audio_analysis"]["acoustic_features"]["pitch_mean_hz"] = 0.0
        attached = attach_assessment(result)
        self.assertEqual(attached["assessment"]["status"], STATUS_INCOMPLETE)
        self.assertIsNone(attached["feature_complete"]["transcript_feature_score"])
        self.assertEqual(attached["feature_complete"]["transcript"]["reason"], NO_STUDENT_TRANSCRIPT)

    def test_empty_transcript_family_score_is_null_not_perfect(self):
        empty = compute_transcript_score(
            {"transcript_features": extract_transcript_features("", duration_seconds=30.0)}
        )
        self.assertIsNone(empty["score"])
        self.assertEqual(empty["reason"], NO_STUDENT_TRANSCRIPT)
        self.assertEqual(empty["family_weights_applied"], {})
        one_word = compute_transcript_score(
            {"transcript_features": extract_transcript_features("Yes", duration_seconds=30.0)}
        )
        self.assertIsNotNone(one_word["score"])
        normal = compute_transcript_score(
            {
                "transcript_features": extract_transcript_features(
                    "We use JWT tokens in NestJS for authentication.",
                    duration_seconds=20,
                )
            }
        )
        self.assertTrue(normal["available"])
        self.assertGreaterEqual(normal["score"], 0.0)
        self.assertLessEqual(normal["score"], 1.0)

    def test_old_mongodb_shape_does_not_crash(self):
        old = {
            "confidence_score": 70.0,
            "engagement_score": 65.0,
            "timeline": [],
            "audio_analysis": {"status": "success", "transcript": "hello"},
        }
        attached = attach_assessment(old)
        self.assertIn("assessment", attached)
        self.assertIn("feature_complete", attached)
        self.assertIsNone(attached["assessment"]["final_score"])
        self.assertIsNone(attached["feature_complete"]["engagement_feature_score"])
        self.assertIsNone(attached["feature_complete"]["audio_feature_score"])
        self.assertIsNone(attached["feature_complete"]["transcript_feature_score"])

    def test_partial_document_missing_audio(self):
        attached = attach_feature_complete({"video_status": "success", "assessment": {"status": "INCOMPLETE"}})
        self.assertIn("feature_complete", attached)
        self.assertFalse(attached["feature_complete"]["audio"]["available"])
        self.assertIsNone(attached["feature_complete"]["audio_feature_score"])

    def test_temporal_model_unavailable_without_checkpoint(self):
        model = TemporalEngagementModel(checkpoint_path="models/does-not-exist.pt")
        self.assertEqual(model.status, "unavailable")
        self.assertIsNone(model.predict([{"emotion": "neutral"}]))
        self.assertFalse(model.describe()["trained"])

    def test_stage1_formulas_and_gates_unchanged(self):
        self.assertEqual(FAMILY_WEIGHTS, {"engagement": 1.0, "audio_acoustics": 1.0, "transcript": 1.0})
        self.assertEqual(FUSION_WEIGHT_AI, 0.5)
        self.assertEqual(FUSION_WEIGHT_TECHNICAL, 0.5)
        self.assertEqual(GRADE_BANDS[0], ("A+", 90.0))
        self.assertEqual(resolve_grade(90), "A+")
        self.assertEqual(resolve_grade(39.9), "F")
        self.assertIsNone(resolve_grade(None))
        mode_a = build_assessment(_sample_result(), mode=MODE_WITHOUT, technical_accuracy=9)
        self.assertEqual(mode_a["final_score"], mode_a["ai_performance"]["score"])
        self.assertIsNone(mode_a["technical_accuracy"])
        mode_b = build_assessment(_sample_result(), mode=MODE_WITH, technical_accuracy=3)
        expected = 0.5 * mode_b["ai_performance"]["score"] + 0.5 * 30.0
        self.assertAlmostEqual(mode_b["final_score"], round(expected, 2))

    def test_qa_groq_schema_unchanged(self):
        from services.qa_relevance import (
            ANSWER_TYPES,
            RELEVANCE_VALUES,
            _SYSTEM_PROMPT,
            validate_relevance_payload,
        )

        self.assertIn("addresses_question", _SYSTEM_PROMPT)
        self.assertIn("relevance", _SYSTEM_PROMPT)
        self.assertIn("answer_type", _SYSTEM_PROMPT)
        self.assertIn("explanation", _SYSTEM_PROMPT)
        self.assertIn("confidence", _SYSTEM_PROMPT)
        self.assertEqual(RELEVANCE_VALUES, frozenset({"high", "medium", "low", "irrelevant"}))
        self.assertIn("direct", ANSWER_TYPES)
        payload = validate_relevance_payload(
            {
                "addresses_question": True,
                "relevance": "high",
                "answer_type": "direct",
                "explanation": "The answer names the asked concept.",
                "confidence": 0.8,
            }
        )
        self.assertEqual(
            set(payload),
            {"addresses_question", "relevance", "answer_type", "explanation", "confidence"},
        )

    def test_ser_provenance_model_passthrough(self):
        result = _sample_result()
        result["audio_analysis"]["audio_emotion"] = {
            "predicted_emotion": "neutral",
            "confidence": 0.91,
            "source": "model",
            "backend": "huggingface",
            "model": "superb/wav2vec2-base-superb-er",
            "probabilities": {"neutral": 0.91},
        }
        attached = attach_assessment(result)
        ser = attached["feature_complete"]["ser"]
        self.assertEqual(ser["source"], "model")
        self.assertEqual(ser["backend"], "huggingface")
        self.assertEqual(ser["model"], "superb/wav2vec2-base-superb-er")
        self.assertIsNone(ser["fallback_reason"])
        packed = attached["audio_analysis"]["audio_emotion"]
        self.assertEqual(packed.get("backend") or ser["backend"], "huggingface")

    def test_ser_close_call_is_low_confidence_not_relabelled(self):
        from extract_emotion import _normalize_ranked, _ser_diagnostics

        extra = _ser_diagnostics(
            {
                "source": "model",
                "confidence": 0.41,
                "emotion_probabilities": {"angry": 0.41, "neutral": 0.38, "happy": 0.21},
            }
        )
        self.assertEqual(extra["interpretation"], "low_confidence")
        self.assertEqual(extra["taxonomy"], "iemocap_er_4class")

        ranked = _normalize_ranked([("angry", 0.98), ("neutral", 0.01), ("hap", 0.01)])
        self.assertEqual(ranked["predicted_emotion"], "angry")
        self.assertEqual(ranked["interpretation"], "majority_label")
        self.assertGreater(ranked["confidence"], 0.9)

    def test_transcript_coverage_categories_do_not_change_score(self):
        from services.transcript_scoring import transcript_coverage

        insufficient = transcript_coverage(word_count=7, duration_seconds=30)
        limited_words = transcript_coverage(word_count=18, duration_seconds=8)
        limited_duration = transcript_coverage(word_count=80, duration_seconds=10)
        adequate = transcript_coverage(word_count=80, duration_seconds=30)
        self.assertEqual(insufficient["status"], "insufficient")
        self.assertEqual(limited_words["status"], "limited")
        self.assertEqual(limited_words["reason"], "short_transcript")
        self.assertEqual(limited_duration["status"], "limited")
        self.assertEqual(limited_duration["reason"], "short_duration")
        self.assertEqual(adequate["status"], "adequate")
        self.assertIsNone(adequate["reason"])

        shared = {
            "speech_rate_wpm": 140.0,
            "hedge_count": 0,
            "filler_count": 0,
            "long_pause_count": 0,
            "sentence_completion_ratio": 1.0,
            "fragmented_sentence_count": 0,
        }
        short = compute_transcript_score(
            {"transcript_features": {**shared, "word_count": 18, "duration_seconds": 8}}
        )
        long = compute_transcript_score(
            {"transcript_features": {**shared, "word_count": 80, "duration_seconds": 30}}
        )
        self.assertEqual(short["score"], long["score"])
        self.assertEqual(short["coverage"]["status"], "limited")
        self.assertEqual(long["coverage"]["status"], "adequate")

        attached = attach_assessment(_sample_result())
        self.assertEqual(attached["assessment"]["status"], "VALID")
        self.assertEqual(attached["feature_complete"]["transcript_coverage"]["status"], "limited")
        self.assertEqual(attached["feature_complete"]["transcript"]["coverage"]["status"], "limited")

    def test_ser_provenance_heuristic_null_model(self):
        result = _sample_result()
        result["audio_analysis"]["audio_emotion"] = {
            "predicted_emotion": "happy",
            "confidence": 0.4,
            "source": "heuristic",
            "backend": None,
            "model": None,
            "fallback_reason": "backend_forced_heuristic",
        }
        attached = attach_assessment(result)
        ser = attached["feature_complete"]["ser"]
        self.assertEqual(ser["source"], "heuristic")
        self.assertIsNone(ser["backend"])
        self.assertIsNone(ser["model"])
        self.assertEqual(ser["fallback_reason"], "backend_forced_heuristic")


if __name__ == "__main__":
    unittest.main()
