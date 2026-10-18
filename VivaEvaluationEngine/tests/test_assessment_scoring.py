"""Stage-1 assessment scoring: modes, gates, LLM independence, parent/child, grades."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[1]
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from services.assessment_scoring import (
    MARKING_SCALE,
    MODE_WITH,
    fuse_final_score,
    MODE_WITHOUT,
    STATUS_INCOMPLETE,
    STATUS_VALID,
    build_assessment,
    resolve_grade,
    resolve_grade_from_mark,
    percent_to_mark,
    score_ai_performance,
)
from services.canonical_features import extract_canonical_features


def _sample_result(**overrides):
    base = {
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
            "grade_breakdown": {
                "pitch_score": 0.8,
                "pitch_stability": 0.44,
                "clarity_score": 0.39,
                "articulation_score": 0.0,
                "energy_score": 0.33,
                "emotion_score": 0.83,
                "transcript_score": 0.28,
                "segment_score": 0.2,
            },
        },
        "llm_evaluation": {
            "communication_clarity": {"score": 8, "justification": "x"},
            "confidence": {"score": 9, "justification": "x"},
            "engagement": {"score": 9, "justification": "x"},
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
    }
    base.update(overrides)
    return base


class GradeResolverTests(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(resolve_grade(90), "A+")
        self.assertEqual(resolve_grade(89.9), "A")
        self.assertEqual(resolve_grade(80), "A")
        self.assertEqual(resolve_grade(79.9), "B+")
        self.assertEqual(resolve_grade(70), "B+")
        self.assertEqual(resolve_grade(60), "B")
        self.assertEqual(resolve_grade(50), "C+")
        self.assertEqual(resolve_grade(40), "C")
        self.assertEqual(resolve_grade(39.9), "F")
        self.assertIsNone(resolve_grade(None))


class CanonicalVectorTests(unittest.TestCase):
    def test_excludes_parents_and_llm(self):
        features = extract_canonical_features(_sample_result())
        blob = str(features)
        # Raw parent key name stays out; facial_confidence is the scored 0–1 form.
        self.assertNotIn("'confidence_score'", blob)
        self.assertNotIn("audio_grade", blob)
        self.assertNotIn("pitch_score", blob)
        self.assertNotIn("llm", blob.lower())
        self.assertIn("average_engagement_score", features["video"])
        self.assertAlmostEqual(features["video"]["facial_confidence"], 0.725)
        self.assertNotIn("engagement_score", features["video"])
        self.assertTrue(features["quality"]["duration_seconds"] >= 8)


class ModeAndFusionTests(unittest.TestCase):
    def test_mode_a_technical_is_null(self):
        assessment = build_assessment(_sample_result(), mode=MODE_WITHOUT, technical_accuracy=3)
        self.assertEqual(assessment["status"], STATUS_VALID)
        self.assertIsNone(assessment["technical_accuracy"])
        self.assertEqual(assessment["final_score"], assessment["ai_performance"]["score"])
        self.assertIsNotNone(assessment["grade"])
        self.assertEqual(assessment["grade"], resolve_grade_from_mark(assessment["final_mark"]))
        self.assertEqual(assessment["final_mark_max"], MARKING_SCALE.mark_max)
        self.assertEqual(assessment["final_mark"], percent_to_mark(assessment["final_score"]))
        self.assertEqual(assessment["ai_performance"]["mark"], percent_to_mark(assessment["ai_performance"]["score"]))

    def test_mode_b_requires_technical_for_final(self):
        pending = build_assessment(_sample_result(), mode=MODE_WITH, technical_accuracy=None)
        self.assertIsNotNone(pending["ai_performance"]["score"])
        self.assertIsNone(pending["final_score"])
        self.assertIsNone(pending["grade"])

        # Technical accuracy is entered out of technical_max: 30% of it is 30% of the technical share.
        entered = round(MARKING_SCALE.technical_max * 0.3, 2)
        done = build_assessment(_sample_result(), mode=MODE_WITH, technical_accuracy=entered)
        self.assertEqual(done["technical_accuracy"], entered)
        expected = 0.5 * done["ai_performance"]["score"] + 0.5 * 30.0
        self.assertAlmostEqual(done["final_score"], round(expected, 2))
        self.assertEqual(done["final_mark"], percent_to_mark(done["final_score"]))
        self.assertEqual(done["grade"], resolve_grade_from_mark(done["final_mark"]))

    def test_without_mode_publishes_with_technical_preview_weights(self):
        """Examiner UI previews a fused mark before publishing.

        Every analysis auto-publishes in WITHOUT mode, whose fusion block reports
        the weights it applied (1.0 / 0.0). Previewing with those would multiply
        technical accuracy by zero, so the block must also carry the weights a
        WITH publish would use. The client reads fusion.with_technical.
        """
        assessment = build_assessment(_sample_result(), mode=MODE_WITHOUT)
        fusion = assessment["fusion"]
        self.assertEqual(fusion["weight_ai"], 1.0)
        self.assertEqual(fusion["weight_technical"], 0.0)

        preview = fusion["with_technical"]
        self.assertGreater(preview["weight_technical"], 0.0)

        # Preview weights must reproduce what a real WITH publish computes.
        ai_score = assessment["ai_performance"]["score"]
        published = build_assessment(
            _sample_result(), mode=MODE_WITH, technical_accuracy=round(MARKING_SCALE.technical_max * 0.8, 2)
        )
        expected = preview["weight_ai"] * ai_score + preview["weight_technical"] * 80.0
        self.assertAlmostEqual(published["final_score"], round(expected, 2))

    def test_with_mode_fusion_reports_applied_weights(self):
        assessment = build_assessment(_sample_result(), mode=MODE_WITH, technical_accuracy=8)
        fusion = assessment["fusion"]
        self.assertEqual(fusion["mode"], MODE_WITH)
        self.assertGreater(fusion["weight_technical"], 0.0)

    def test_llm_scores_do_not_change_performance(self):
        a = build_assessment(_sample_result())
        b = build_assessment(
            _sample_result(
                llm_evaluation={
                    "communication_clarity": {"score": 2, "justification": "x"},
                    "confidence": {"score": 1, "justification": "x"},
                    "engagement": {"score": 1, "justification": "x"},
                }
            )
        )
        self.assertEqual(a["ai_performance"]["score"], b["ai_performance"]["score"])

    def test_parent_diagnostic_scores_do_not_change_performance(self):
        """UI diagnostic blends (engagement_score, audio_grade) stay out of Stage-1.

        facial confidence (confidence_score) DOES enter the engagement family.
        """
        a = build_assessment(_sample_result())
        b = build_assessment(
            _sample_result(
                engagement_score=10.0,
                audio_analysis={
                    **_sample_result()["audio_analysis"],
                    "audio_grade": 1.0,
                    "grade_breakdown": {
                        "pitch_score": 0.0,
                        "transcript_score": 1.0,
                        "segment_score": 1.0,
                    },
                },
            )
        )
        self.assertEqual(a["ai_performance"]["score"], b["ai_performance"]["score"])

    def test_facial_confidence_changes_engagement_family(self):
        high = build_assessment(_sample_result(confidence_score=90.0))
        low = build_assessment(_sample_result(confidence_score=10.0))
        self.assertGreater(high["ai_performance"]["score"], low["ai_performance"]["score"])
        high_eng = high["ai_performance"]["family_scores"]["engagement"]
        low_eng = low["ai_performance"]["family_scores"]["engagement"]
        self.assertGreater(high_eng, low_eng)
        features = high["ai_performance"]["components"]
        names = {c["feature"] for c in features}
        self.assertIn("facial_confidence", names)
        self.assertIn("average_engagement_score", names)


class IncompleteRecordingTests(unittest.TestCase):
    def test_face_required_even_when_audio_ok(self):
        result = _sample_result(
            video_status="insufficient_face_coverage",
            coverage={
                "frames_sampled": 8,
                "frames_with_face": 0,
                "face_coverage_ratio": 0.0,
                "blinks_measured": False,
                "scores_emitted": False,
            },
            engagement_summary={
                "average_engagement_score": None,
                "very_low_ratio": 0.0,
                "low_ratio": 0.0,
                "high_ratio": 0.0,
                "very_high_ratio": 0.0,
            },
        )
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIn("video_insufficient", assessment["validation"]["reasons"])
        self.assertIsNone(assessment["final_score"])
        self.assertIsNone(assessment["ai_performance"]["score"])
        self.assertIn("face", (assessment["validation"]["message"] or "").lower())

    def test_insufficient_video_and_audio(self):
        result = _sample_result(
            video_status="insufficient_face_coverage",
            coverage={
                "frames_sampled": 8,
                "frames_with_face": 0,
                "face_coverage_ratio": 0.0,
                "blinks_measured": False,
                "scores_emitted": False,
            },
        )
        result["audio_analysis"] = {
            **result["audio_analysis"],
            "status": "insufficient_audio",
            "acoustic_features": {
                **result["audio_analysis"]["acoustic_features"],
                "duration_seconds": 0.2,
            },
        }
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIsNone(assessment["final_score"])
        self.assertIsNone(assessment["grade"])

    def test_silent_student_no_mark_when_whisper_ran(self):
        result = _sample_result()
        result["audio_analysis"]["status"] = "insufficient_audio"
        result["audio_analysis"]["transcript_word_count"] = 0
        result["audio_analysis"]["whisper_available"] = True
        result["audio_analysis"]["transcript_features"]["word_count"] = 0
        result["audio_analysis"]["acoustic_features"]["rms_mean"] = 0.0002
        result["audio_analysis"]["acoustic_features"]["pitch_mean_hz"] = 0.0
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIn("no_speech_detected", assessment["validation"]["reasons"])
        self.assertNotIn("audio_pipeline_failed", assessment["validation"]["reasons"])
        self.assertIsNone(assessment["final_score"])
        self.assertIsNone(assessment["ai_performance"]["score"])
        self.assertIn("did not speak", assessment["validation"]["message"])

    def test_audio_pipeline_failure_is_not_called_silent_student(self):
        result = _sample_result()
        result["audio_analysis"]["status"] = "failed"
        result["audio_analysis"]["transcript_word_count"] = 0
        result["audio_analysis"]["whisper_available"] = False
        result["audio_analysis"]["degraded_reasons"] = ["transcript_unavailable"]
        result["audio_analysis"]["error"] = "ffmpeg missing"
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIn("audio_pipeline_failed", assessment["validation"]["reasons"])
        self.assertNotIn("no_speech_detected", assessment["validation"]["reasons"])
        self.assertIsNone(assessment["final_score"])
        self.assertIn("pipeline issue", assessment["validation"]["message"])

    def test_no_scorable_families(self):
        result = _sample_result(
            engagement_summary={"average_engagement_score": None},
            confidence_score=None,
            video_status="success",
        )
        result["engagement_summary"]["average_engagement_score"] = None
        result["confidence_score"] = None
        result["audio_analysis"]["acoustic_features"] = {
            "duration_seconds": 8.0,
            "voice_quality_measured": False,
            "pitch_std_hz": None,
            "hnr_mean_db": None,
            "jitter_local": None,
            "shimmer_local": None,
            "rms_mean": 0.0,
        }
        result["audio_analysis"]["transcript_features"] = {}
        assessment = build_assessment(result)
        self.assertEqual(assessment["status"], STATUS_INCOMPLETE)
        self.assertIsNone(assessment["ai_performance"]["score"])


class ScorerFamilyTests(unittest.TestCase):
    def test_does_not_list_parent_and_child(self):
        features = extract_canonical_features(_sample_result())
        scored = score_ai_performance(features)
        names = {c["feature"] for c in scored["components"]}
        self.assertNotIn("audio_grade", names)
        self.assertNotIn("confidence_score", names)
        self.assertNotIn("engagement_score", names)
        self.assertNotIn("pitch_score", names)
        self.assertIn("average_engagement_score", names)
        self.assertIn("facial_confidence", names)


class FacialAndSpeechEmotionScoringTests(unittest.TestCase):
    """v1.2: emotion/gaze/head/blink score inside Engagement; SER tone inside Audio."""

    def _video(self, emotion=0.9, gaze=0.85, head=0.8, blink_bpm=12.0):
        return {
            "emotion": {"status": "available", "score": emotion},
            "gaze": {"status": "available", "gaze_on_camera_ratio": gaze},
            "head_pose": {"status": "available", "stability_score": head},
            "blink": {"status": "available", "blink_rate_per_minute": blink_bpm},
        }

    def test_facial_signals_enter_engagement_family(self):
        result = _sample_result()
        result["video_features"] = self._video()
        scored = score_ai_performance(extract_canonical_features(result))
        names = {c["feature"] for c in scored["components"] if c["family"] == "engagement"}
        self.assertEqual(
            names,
            {"average_engagement_score", "facial_confidence", "emotion_profile",
             "gaze_on_camera_ratio", "head_stability", "blink_score"},
        )

    def test_worse_gaze_lowers_engagement_and_mark(self):
        good, bad = _sample_result(), _sample_result()
        good["video_features"] = self._video(gaze=0.95)
        bad["video_features"] = self._video(gaze=0.10)
        g = build_assessment(good)["ai_performance"]
        b = build_assessment(bad)["ai_performance"]
        self.assertGreater(g["family_scores"]["engagement"], b["family_scores"]["engagement"])
        self.assertGreater(g["score"], b["score"])

    def test_missing_facial_signals_are_dropped_not_penalised(self):
        plain = build_assessment(_sample_result())["ai_performance"]["family_scores"]["engagement"]
        result = _sample_result()
        result["video_features"] = {"gaze": {"status": "unavailable"}}
        self.assertEqual(
            build_assessment(result)["ai_performance"]["family_scores"]["engagement"], plain
        )

    def test_speech_emotion_counts_only_from_real_model(self):
        model, heuristic = _sample_result(), _sample_result()
        model["audio_analysis"]["audio_emotion"] = {"source": "model", "predicted_emotion": "angry", "confidence": 0.9}
        heuristic["audio_analysis"]["audio_emotion"] = {"source": "heuristic", "predicted_emotion": "angry", "confidence": 0.9}
        m = build_assessment(model)["ai_performance"]
        h = build_assessment(heuristic)["ai_performance"]
        self.assertIn("speech_emotion_tone", {c["feature"] for c in m["components"]})
        self.assertNotIn("speech_emotion_tone", {c["feature"] for c in h["components"]})
        self.assertLess(m["family_scores"]["audio_acoustics"], h["family_scores"]["audio_acoustics"])



def _technical_result(covered, weights):
    """A technical_accuracy_ai block: `covered` flags aligned with `weights`."""
    return {
        "status": "success",
        "overall_score": 5.0,
        "concepts": [
            {
                "concept_id": f"c{i}",
                "name": f"Concept {i}",
                "covered": bool(flag),
                "score": 0.9 if flag else 0.0,
                "weight": float(weight),
            }
            for i, (flag, weight) in enumerate(zip(covered, weights))
        ],
    }


class TopicCoverageGateTests(unittest.TestCase):
    """Technical vivas: an answer that touches almost none of the rubric is held, not graded."""

    def _assess(self, technical, mode=MODE_WITH, **overrides):
        result = _sample_result(**overrides)
        if technical is not None:
            result["technical_accuracy_ai"] = technical
        return build_assessment(result, mode=mode, technical_accuracy=7.0)

    def test_off_topic_answer_is_held_with_no_mark(self):
        weights = [5, 5, 5, 4, 4, 3, 3, 4, 4, 3, 3, 4]
        out = self._assess(_technical_result([False] * 12, weights))
        self.assertEqual(out["status"], STATUS_INCOMPLETE)
        self.assertIn("insufficient_topic_coverage", out["validation"]["reasons"])
        self.assertIsNone(out["final_score"])
        self.assertIsNone(out["grade"])
        self.assertIsNone(out["ai_performance"]["score"])
        self.assertEqual(out["topic_coverage"]["coverage_ratio"], 0.0)
        self.assertEqual(out["topic_coverage"]["concepts_covered"], 0)
        self.assertIn("0.0%", out["validation"]["message"])

    def test_coverage_is_by_weight_not_by_count(self):
        # one concept covered, but it carries 4 of the 25 weight = 16%
        out = self._assess(_technical_result([True, False, False, False], [4, 7, 7, 7]))
        self.assertEqual(out["status"], STATUS_VALID)
        self.assertAlmostEqual(out["topic_coverage"]["coverage_ratio"], 0.16, places=4)
        self.assertIsNotNone(out["final_score"])

    def test_just_below_the_minimum_is_held_and_just_above_passes(self):
        weights = [1] + [24]          # covering only the weight-1 concept = 1 / 25 = 4%
        below = self._assess(_technical_result([True, False], weights))
        self.assertEqual(below["status"], STATUS_INCOMPLETE)
        weights = [2] + [23]          # covering the weight-2 concept = 2 / 25 = 8%
        above = self._assess(_technical_result([True, False], weights))
        self.assertEqual(above["status"], STATUS_VALID)

    def test_not_applied_to_non_technical_vivas(self):
        out = self._assess(_technical_result([False] * 3, [5, 5, 5]), mode=MODE_WITHOUT)
        self.assertEqual(out["status"], STATUS_VALID)
        self.assertIsNone(out["topic_coverage"])

    def test_no_rubric_or_failed_scoring_is_not_a_reason_to_hold(self):
        no_rubric = self._assess(None)
        self.assertEqual(no_rubric["status"], STATUS_VALID)
        self.assertIsNone(no_rubric["topic_coverage"])
        failed = self._assess({"status": "unavailable", "overall_score": None, "concepts": []})
        self.assertEqual(failed["status"], STATUS_VALID)
        self.assertIsNone(failed["topic_coverage"])

    def test_other_incomplete_reasons_still_win(self):
        out = self._assess(
            _technical_result([False] * 2, [5, 5]),
            video_status="insufficient_face_coverage",
        )
        self.assertEqual(out["status"], STATUS_INCOMPLETE)
        self.assertNotIn("insufficient_topic_coverage", out["validation"]["reasons"])


class MarkOnDefaultScaleTests(unittest.TestCase):
    """Marks on the default scale (out of 20); other scales are covered in test_marking_scale.py."""

    def setUp(self):
        from unittest.mock import patch

        from services import assessment_scoring
        from services.marking_scale import MarkingScale

        patcher = patch.object(assessment_scoring, "MARKING_SCALE", MarkingScale())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_percent_to_mark_scales_and_rounds(self):
        self.assertEqual(percent_to_mark(100), 20.0)
        self.assertEqual(percent_to_mark(0), 0.0)
        self.assertEqual(percent_to_mark(69.44), 13.89)
        self.assertEqual(percent_to_mark(79.06), 15.81)
        self.assertIsNone(percent_to_mark(None))
        self.assertEqual(percent_to_mark(150), 20.0)  # clamped

    def test_grade_bands_out_of_20(self):
        cases = {
            20: "A+", 18: "A+", 17.99: "A", 16: "A", 15.99: "B+", 14: "B+",
            13.99: "B", 12: "B", 11.99: "C+", 10: "C+", 9.99: "C", 8: "C", 7.99: "F", 0: "F",
        }
        for mark, grade in cases.items():
            self.assertEqual(resolve_grade_from_mark(mark), grade, mark)
        self.assertIsNone(resolve_grade_from_mark(None))

    def test_bands_match_the_percentage_bands(self):
        for percent in (0, 39.9, 40, 49.9, 50, 59.9, 60, 69.9, 70, 79.9, 80, 89.9, 90, 100):
            self.assertEqual(
                resolve_grade_from_mark(percent_to_mark(percent)), resolve_grade(percent), percent
            )

    def test_grade_follows_the_rounded_displayed_mark(self):
        """69.98% is 13.996/20, which displays as 14.00, so it grades as B+ (not B)."""
        mark = percent_to_mark(69.98)
        self.assertEqual(mark, 14.0)
        self.assertEqual(resolve_grade_from_mark(mark), "B+")
        self.assertEqual(resolve_grade(69.98), "B")  # the raw percentage would say B

    def test_technical_fusion_out_of_20(self):
        fused = fuse_final_score(mode=MODE_WITH, ai_performance=60.0, technical_accuracy=16.0)
        self.assertEqual(fused["technical_accuracy"], 16.0)
        self.assertEqual(fused["technical_accuracy_100"], 80.0)
        self.assertEqual(fused["final_score"], 70.0)  # 0.5*60 + 0.5*80
        self.assertEqual(fused["final_mark"], 14.0)
        # The technical score is clamped to its 20-mark scale.
        over = fuse_final_score(mode=MODE_WITH, ai_performance=60.0, technical_accuracy=25.0)
        self.assertEqual(over["technical_accuracy"], 20.0)
        self.assertEqual(over["final_mark"], 16.0)  # 0.5*60 + 0.5*100 = 80% -> 16/20

    def test_pending_without_technical_has_no_mark(self):
        pending = fuse_final_score(mode=MODE_WITH, ai_performance=60.0, technical_accuracy=None)
        self.assertIsNone(pending["final_mark"])
        self.assertIsNone(pending["final_score"])


if __name__ == "__main__":
    unittest.main()
