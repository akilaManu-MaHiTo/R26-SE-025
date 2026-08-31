"""Feature-complete audio sub-score. Does not replace audio_grade or Stage-1 /100.

Speech rate is a transcript signal and is stored here only as a diagnostic.
It is not mixed into audio_feature_score.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from services.normalization import (
    energy_consistency_score,
    jitter_shimmer_quality,
    pitch_stability_score,
    speech_rate_score,
)
from services.score_utils import measured_value, weighted_mean_available

# Acoustics only. Relative 35/25/25; missing parts are omitted and renormalized.
AUDIO_FEATURE_WEIGHTS = {
    "pitch_stability": 0.35,
    "clarity_hnr": 0.25,
    "articulation": 0.25,
}


def _hnr_clarity(hnr_mean_db: Optional[float], voice_ok: bool) -> Optional[float]:
    if not voice_ok or hnr_mean_db is None:
        return None
    return max(0.0, min(1.0, float(hnr_mean_db) / 30.0))


def _articulation(jitter: Optional[float], shimmer: Optional[float], voice_ok: bool) -> Optional[float]:
    if not voice_ok:
        return None
    jitter_part = jitter_shimmer_quality(jitter, 0.005, 0.030)
    shimmer_part = jitter_shimmer_quality(shimmer, 0.030, 0.150)
    if jitter_part is None and shimmer_part is None:
        return None
    if jitter_part is None:
        return shimmer_part
    if shimmer_part is None:
        return jitter_part
    return 0.5 * jitter_part + 0.5 * shimmer_part


def compute_audio_score(features: Dict[str, Any]) -> Dict[str, Any]:
    audio = features.get("audio_features") or features.get("audio") or {}
    quality = features.get("quality") or {}
    transcript = features.get("transcript_features") or features.get("transcript") or {}
    voice_ok = bool(audio.get("voice_quality_measured") or quality.get("voice_quality_measured"))

    pitch_s = pitch_stability_score(audio.get("pitch_std_hz") if audio.get("pitch_measured", True) else None)
    if audio.get("pitch_measured") is False:
        pitch_s = None
    clarity = _hnr_clarity(audio.get("hnr_mean_db") or audio.get("hnr_mean"), voice_ok)
    articulation = _articulation(audio.get("jitter_local"), audio.get("shimmer_local"), voice_ok)
    rate = speech_rate_score(
        transcript.get("speech_rate_wpm"),
        word_count=transcript.get("word_count"),
    )
    energy = energy_consistency_score(audio.get("rms_mean"), audio.get("rms_std"))

    score, applied = weighted_mean_available(
        {
            "pitch_stability": pitch_s,
            "clarity_hnr": clarity,
            "articulation": articulation,
        },
        AUDIO_FEATURE_WEIGHTS,
    )
    warnings: List[str] = []
    if energy is not None:
        warnings.append("RMS stored as energy_consistency; not treated as louder=better.")
    warnings.append("Speech rate is scored only in the transcript family, not in audio.")
    ser = features.get("ser") or {}
    if ser.get("source") and ser.get("source") != "model":
        warnings.append("SER is heuristic or unavailable; not used as a confidence diagnosis.")

    components = {
        "pitch_stability": measured_value(
            raw=audio.get("pitch_std_hz"),
            normalized=pitch_s,
            available=pitch_s is not None,
            method="1 - clamp(std_hz/120)",
        ),
        "clarity_hnr": measured_value(
            raw=audio.get("hnr_mean_db") or audio.get("hnr_mean"),
            normalized=clarity,
            available=clarity is not None,
            method="clamp(hnr_db/30)",
        ),
        "articulation": measured_value(
            raw={"jitter_local": audio.get("jitter_local"), "shimmer_local": audio.get("shimmer_local")},
            normalized=articulation,
            available=articulation is not None,
            method="parselmouth jitter/shimmer quality map",
        ),
        "speech_rate": measured_value(
            raw=transcript.get("speech_rate_wpm"),
            normalized=rate,
            available=False,
            method="stored diagnostic — scored in transcript family only",
            status="diagnostic_only",
        ),
        "energy_consistency": measured_value(
            raw={"rms_mean": audio.get("rms_mean"), "rms_std": audio.get("rms_std")},
            normalized=energy,
            available=energy is not None,
            method="1/(1+rms_std/rms_mean) — stored, not in family mix",
            status="available" if energy is not None else "unavailable",
        ),
        "ser": measured_value(
            raw=ser.get("emotion") or ser.get("predicted_emotion"),
            normalized=None,
            available=str(ser.get("source") or "") == "model",
            method="wav2vec2/speechbrain supporting feature",
            status="available" if str(ser.get("source") or "") == "model" else "unavailable",
        ),
    }
    return {
        "metric_id": "feature_complete_audio",
        "score": None if score is None else round(float(score), 4),
        "available": score is not None,
        "status": "available" if score is not None else "unavailable",
        "components": components,
        "family_weights_applied": applied,
        "warnings": warnings,
    }
