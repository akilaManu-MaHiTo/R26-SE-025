"""Canonical feature vector for viva Stage-1 scoring and future ML (schema v1).

One representation per evidence family. Excludes LLM scores, UI sliders, parent
aggregates (confidence_score, engagement_score, audio_grade), 180 Hz pitch_score,
length-as-skill (transcript_score / segment_score), raw timeline, and transcript text.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


FEATURE_SCHEMA_VERSION = "v1"


def _f(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number in (float("inf"), float("-inf")):
        return None
    return number


def _clamp01(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))


def _i(value: Any) -> Optional[int]:
    number = _f(value)
    if number is None:
        return None
    return int(number)


def extract_canonical_features(result: Dict[str, Any]) -> Dict[str, Any]:
    coverage = result.get("coverage") or {}
    summary = result.get("summary") or {}
    engagement_summary = result.get("engagement_summary") or {}
    audio = result.get("audio_analysis") or {}
    acoustics = audio.get("acoustic_features") or {}
    transcript_features = audio.get("transcript_features") or {}
    audio_emotion = audio.get("audio_emotion") or {}
    ser_source = str(audio_emotion.get("source") or "").strip().lower()

    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "quality": {
            "duration_seconds": _f(acoustics.get("duration_seconds")),
            "face_coverage_ratio": _f(coverage.get("face_coverage_ratio")),
            "frames_with_face": _i(coverage.get("frames_with_face")),
            "frames_sampled": _i(coverage.get("frames_sampled")),
            "frames_rejected_non_frontal": _i(coverage.get("frames_rejected_non_frontal")),
            "video_status": result.get("video_status"),
            "audio_status": audio.get("status"),
            "transcript_word_count": _i(
                audio.get("transcript_word_count")
                if audio.get("transcript_word_count") is not None
                else transcript_features.get("word_count")
            ),
            "voice_quality_measured": bool(acoustics.get("voice_quality_measured")),
            "ser_source_is_model": ser_source == "model",
            "whisper_available": (
                bool(audio.get("whisper_available"))
                if audio.get("whisper_available") is not None
                else ("transcript_unavailable" not in list(audio.get("degraded_reasons") or []))
                and str(audio.get("status") or "") != "failed"
            ),
            "whisper_reason": audio.get("whisper_reason"),
            "pause_detection_granularity": transcript_features.get("pause_detection_granularity"),
            "blinks_measured": bool(coverage.get("blinks_measured")),
            "degraded_reasons": list(audio.get("degraded_reasons") or []),
        },
        "video": {
            "emotion_ratios": {
                "positive": _f(summary.get("positive_ratio")),
                "neutral": _f(summary.get("neutral_ratio")),
                "negative": _f(summary.get("negative_ratio")),
            },
            # stage1_cnn_engagement: per-frame CNN mean (0–1).
            # Not engagement_score (diagnostic_engagement) and not feature_complete_engagement.
            "average_engagement_score": _f(engagement_summary.get("average_engagement_score")),
            # Facial confidence / positivity (result.confidence_score is 0–100).
            # Emotion-weighted face tone; used inside the engagement family of Stage-1.
            "facial_confidence": (
                _clamp01(_f(result.get("confidence_score")) / 100.0)
                if _f(result.get("confidence_score")) is not None
                else None
            ),
            "blinks_per_minute": _f(coverage.get("blinks_per_minute"))
            if coverage.get("blinks_measured")
            else None,
        },
        "audio": {
            "pitch_std_hz": _f(acoustics.get("pitch_std_hz")),
            "pitch_mean_hz": _f(acoustics.get("pitch_mean_hz")),
            "hnr_mean_db": _f(acoustics.get("hnr_mean_db")),
            "jitter_local": _f(acoustics.get("jitter_local")),
            "shimmer_local": _f(acoustics.get("shimmer_local")),
            "rms_mean": _f(acoustics.get("rms_mean")),
            "rms_std": _f(acoustics.get("rms_std")),
            "energy_consistency": _f(acoustics.get("energy_consistency")),
            "pitch_range_hz": _f(acoustics.get("pitch_range_hz")),
        },
        "transcript": {
            "speech_rate_wpm": _f(transcript_features.get("speech_rate_wpm")),
            "speech_rate_band": transcript_features.get("speech_rate_band"),
            "hedge_count": _i(transcript_features.get("hedge_count")),
            "filler_count": _i(transcript_features.get("filler_count")),
            "pause_count": _i(transcript_features.get("pause_count")),
            "long_pause_count": _i(transcript_features.get("long_pause_count")),
            "total_pause_duration": _f(transcript_features.get("total_pause_duration")),
            "max_pause_duration": _f(transcript_features.get("max_pause_duration")),
            "sentence_completion_ratio": _f(transcript_features.get("sentence_completion_ratio")),
            "fragmented_sentence_count": _i(transcript_features.get("fragmented_sentence_count")),
        },
        "ser": {
            "source": audio_emotion.get("source"),
            "emotion": audio_emotion.get("predicted_emotion"),
            "confidence": _f(audio_emotion.get("confidence")),
            "backend": audio_emotion.get("backend"),
            "model": audio_emotion.get("model"),
        },
    }


def flatten_canonical_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Tabular row of X for export / future training. No labels."""
    quality = features.get("quality") or {}
    video = features.get("video") or {}
    ratios = video.get("emotion_ratios") or {}
    audio = features.get("audio") or {}
    transcript = features.get("transcript") or {}
    ser = features.get("ser") or {}
    return {
        "feature_schema_version": features.get("feature_schema_version"),
        "duration_seconds": quality.get("duration_seconds"),
        "face_coverage_ratio": quality.get("face_coverage_ratio"),
        "frames_with_face": quality.get("frames_with_face"),
        "frames_sampled": quality.get("frames_sampled"),
        "frames_rejected_non_frontal": quality.get("frames_rejected_non_frontal"),
        "video_status": quality.get("video_status"),
        "audio_status": quality.get("audio_status"),
        "transcript_word_count": quality.get("transcript_word_count"),
        "voice_quality_measured": quality.get("voice_quality_measured"),
        "ser_source_is_model": quality.get("ser_source_is_model"),
        "pause_detection_granularity": quality.get("pause_detection_granularity"),
        "blinks_measured": quality.get("blinks_measured"),
        "emotion_positive_ratio": ratios.get("positive"),
        "emotion_neutral_ratio": ratios.get("neutral"),
        "emotion_negative_ratio": ratios.get("negative"),
        "average_engagement_score": video.get("average_engagement_score"),
        "facial_confidence": video.get("facial_confidence"),
        "blinks_per_minute": video.get("blinks_per_minute"),
        "pitch_std_hz": audio.get("pitch_std_hz"),
        "hnr_mean_db": audio.get("hnr_mean_db"),
        "jitter_local": audio.get("jitter_local"),
        "shimmer_local": audio.get("shimmer_local"),
        "rms_mean": audio.get("rms_mean"),
        "speech_rate_wpm": transcript.get("speech_rate_wpm"),
        "speech_rate_band": transcript.get("speech_rate_band"),
        "hedge_count": transcript.get("hedge_count"),
        "filler_count": transcript.get("filler_count"),
        "pause_count": transcript.get("pause_count"),
        "long_pause_count": transcript.get("long_pause_count"),
        "sentence_completion_ratio": transcript.get("sentence_completion_ratio"),
        "ser_source": ser.get("source"),
        "ser_backend": ser.get("backend"),
        "ser_model": ser.get("model"),
        "ser_emotion": ser.get("emotion") if quality.get("ser_source_is_model") else None,
        "ser_confidence": ser.get("confidence") if quality.get("ser_source_is_model") else None,
    }
