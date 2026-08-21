"""Attach a feature-complete baseline alongside Stage-1 assessment.

Does not overwrite ai_performance / final_score / grade.
Family scores are unavailable when the official assessment is INCOMPLETE;
raw diagnostic measurements are still attached.
"""
from __future__ import annotations

from typing import Any, Dict

from services.audio_scoring import compute_audio_score
from services.engagement_scoring import compute_engagement_score as compute_engagement_feature_score
from services.transcript_scoring import compute_transcript_score

STATUS_INCOMPLETE = "INCOMPLETE"

ENGAGEMENT_METRIC_STAGE1_CNN = "stage1_cnn_engagement"
ENGAGEMENT_METRIC_DIAGNOSTIC = "diagnostic_engagement"
ENGAGEMENT_METRIC_FEATURE_COMPLETE = "feature_complete_engagement"


def _finite(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


def _sanitize_tree(node: Any) -> Any:
    if isinstance(node, dict):
        return {key: _sanitize_tree(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_sanitize_tree(item) for item in node]
    if isinstance(node, float) and not _finite(node):
        return None
    return node


def _ser_view(emotion: Dict[str, Any]) -> Dict[str, Any]:
    source = str(emotion.get("source") or "").strip().lower()
    is_model = source == "model"
    view = {
        "source": emotion.get("source"),
        "emotion": emotion.get("predicted_emotion"),
        "confidence": emotion.get("confidence"),
        "probabilities": emotion.get("probabilities") or emotion.get("emotion_probabilities"),
        "backend": emotion.get("backend") if is_model else None,
        "model": emotion.get("model") if is_model else None,
        "fallback_reason": None
        if is_model
        else (emotion.get("fallback_reason") or emotion.get("model_error")),
        "interpretation": emotion.get("interpretation"),
        "label_margin": emotion.get("label_margin"),
        "taxonomy": emotion.get("taxonomy"),
        "domain_note": emotion.get("domain_note"),
        "analyzed_duration_seconds": emotion.get("analyzed_duration_seconds"),
        "sample_rate": emotion.get("sample_rate"),
        "input_track": emotion.get("input_track"),
    }
    if emotion.get("requested_backend") and not is_model:
        view["requested_backend"] = emotion.get("requested_backend")
    return view


def _audio_feature_view(result: Dict[str, Any]) -> Dict[str, Any]:
    audio = result.get("audio_analysis") or {}
    acoustics = audio.get("acoustic_features") or {}
    emotion = audio.get("audio_emotion") or {}
    return {
        "quality": {
            "duration_seconds": acoustics.get("duration_seconds"),
            "voice_quality_measured": acoustics.get("voice_quality_measured"),
        },
        "audio_features": {
            "duration_seconds": acoustics.get("duration_seconds"),
            "pitch_mean_hz": acoustics.get("pitch_mean_hz"),
            "pitch_min_hz": acoustics.get("pitch_min_hz"),
            "pitch_max_hz": acoustics.get("pitch_max_hz"),
            "pitch_std_hz": acoustics.get("pitch_std_hz"),
            "pitch_measured": acoustics.get("pitch_measured", True),
            "rms_mean": acoustics.get("rms_mean"),
            "rms_std": acoustics.get("rms_std"),
            "jitter_local": acoustics.get("jitter_local"),
            "shimmer_local": acoustics.get("shimmer_local"),
            "hnr_mean_db": acoustics.get("hnr_mean_db"),
            "voice_quality_measured": acoustics.get("voice_quality_measured"),
            "energy_consistency": acoustics.get("energy_consistency"),
            "energy_consistency_not_loudness": True,
            "mfcc_mean": acoustics.get("mfcc_mean"),
            "mfcc_std": acoustics.get("mfcc_std"),
            "mfcc_n_coefficients": acoustics.get("mfcc_n_coefficients"),
            "mfcc_sample_rate": acoustics.get("mfcc_sample_rate"),
            "mfcc_role": acoustics.get("mfcc_role") or "feature_representation",
            "pitch_range_hz": acoustics.get("pitch_range_hz"),
            "pitch_stability": acoustics.get("pitch_stability"),
        },
        "transcript_features": audio.get("transcript_features") or {},
        "ser": _ser_view(emotion),
    }


def _unavailable_family(family: Dict[str, Any], reason: str) -> Dict[str, Any]:
    """Keep component diagnostics; hide the family score."""
    updated = dict(family)
    updated["score"] = None
    updated["available"] = False
    updated["status"] = "unavailable"
    updated["reason"] = reason
    updated["family_weights_applied"] = {}
    return updated


def build_feature_complete(result: Dict[str, Any]) -> Dict[str, Any]:
    video_features = result.get("video_features") or {}
    audio_view = _audio_feature_view(result)
    engagement = compute_engagement_feature_score({"video_features": video_features})
    audio = compute_audio_score(audio_view)
    transcript = compute_transcript_score(audio_view)

    assessment = result.get("assessment") or {}
    incomplete = str(assessment.get("status") or "") == STATUS_INCOMPLETE
    if incomplete:
        engagement = _unavailable_family(engagement, "assessment_incomplete")
        audio = _unavailable_family(audio, "assessment_incomplete")
        transcript_reason = transcript.get("reason") or "assessment_incomplete"
        transcript = _unavailable_family(transcript, str(transcript_reason))

    derived = {
        "pitch_range_hz": (audio_view.get("audio_features") or {}).get("pitch_range_hz"),
        "pitch_stability": (audio_view.get("audio_features") or {}).get("pitch_stability")
        or (audio.get("components") or {}).get("pitch_stability", {}).get("normalized"),
        "energy_consistency": (audio_view.get("audio_features") or {}).get("energy_consistency")
        or (audio.get("components") or {}).get("energy_consistency", {}).get("normalized"),
        "transcript_coverage": transcript.get("coverage"),
        "blink_measurement_quality": (video_features.get("blink") or {}).get("measurement_quality"),
        "gaze_validated": (video_features.get("gaze") or {}).get("validated"),
        "head_validated": (video_features.get("head_pose") or {}).get("validated"),
        "response_structure": (audio_view.get("transcript_features") or {}).get("response_structure"),
    }
    ai = (assessment.get("ai_performance") or {}).get("score")
    return _sanitize_tree(
        {
            "engagement_feature_score": engagement.get("score"),
            "audio_feature_score": audio.get("score"),
            "transcript_feature_score": transcript.get("score"),
            "engagement": engagement,
            "audio": audio,
            "transcript": transcript,
            "transcript_coverage": transcript.get("coverage"),
            "raw_measurements": {
                "video_features": video_features,
                "audio_features": audio_view.get("audio_features"),
                "transcript_features": audio_view.get("transcript_features"),
                "ser": audio_view.get("ser"),
            },
            "derived_features": derived,
            "video_features": video_features,
            "audio_features": audio_view.get("audio_features"),
            "transcript_features": audio_view.get("transcript_features"),
            "ser": audio_view.get("ser"),
            "layers": {
                "raw_measurements": "see raw_measurements",
                "derived_features": derived,
                "normalized_features": {
                    "engagement": (engagement.get("components") or {}),
                    "audio": (audio.get("components") or {}),
                    "transcript": (transcript.get("components") or {}),
                },
                "feature_complete_family_scores": {
                    "engagement": engagement.get("score"),
                    "audio": audio.get("score"),
                    "transcript": transcript.get("score"),
                },
                "current_stage1_score": assessment.get("final_score"),
                "final_score": assessment.get("final_score"),
            },
            "current_stage1": {
                "ai_performance": ai,
                "final_score": assessment.get("final_score"),
                "status": assessment.get("status"),
                "scoring_version": assessment.get("scoring_version"),
            },
            "scoring_validity": {
                "official_status": assessment.get("status"),
                "family_scores_emitted": not incomplete,
                "reason": "assessment_incomplete" if incomplete else None,
            },
        }
    )


def _engagement_metrics(result: Dict[str, Any], feature_complete: Dict[str, Any]) -> Dict[str, Any]:
    assessment = result.get("assessment") or {}
    features = assessment.get("features") or {}
    video = features.get("video") or {}
    summary = result.get("engagement_summary") or {}
    stage1_value = video.get("average_engagement_score")
    if stage1_value is None:
        stage1_value = summary.get("average_engagement_score")
    return {
        ENGAGEMENT_METRIC_STAGE1_CNN: {
            "metric_id": ENGAGEMENT_METRIC_STAGE1_CNN,
            "value": stage1_value,
            "scale": "0_1",
            "used_by": "official_stage1_engagement_family",
            "source": "per_frame_engagement_cnn",
            "result_field": "assessment.features.video.average_engagement_score",
        },
        ENGAGEMENT_METRIC_DIAGNOSTIC: {
            "metric_id": ENGAGEMENT_METRIC_DIAGNOSTIC,
            "value": result.get("engagement_score"),
            "scale": "0_100",
            "used_by": "ui_parent_engagement_score",
            "source": "services.scoring.compute_engagement_score",
            "result_field": "engagement_score",
            "not_official": True,
        },
        ENGAGEMENT_METRIC_FEATURE_COMPLETE: {
            "metric_id": ENGAGEMENT_METRIC_FEATURE_COMPLETE,
            "value": feature_complete.get("engagement_feature_score"),
            "scale": "0_1",
            "used_by": "feature_complete",
            "source": "services.engagement_scoring.compute_engagement_score",
            "result_field": "feature_complete.engagement_feature_score",
            "not_official": True,
        },
    }


def attach_feature_complete(result: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(result)
    feature_complete = build_feature_complete(enriched)
    enriched["feature_complete"] = feature_complete
    enriched["scoring"] = {
        "current_stage1": feature_complete.get("current_stage1"),
        "feature_complete": {
            "engagement": feature_complete.get("engagement_feature_score"),
            "audio": feature_complete.get("audio_feature_score"),
            "transcript": feature_complete.get("transcript_feature_score"),
        },
    }
    enriched["engagement_metrics"] = _engagement_metrics(enriched, feature_complete)
    return enriched
