"""Stage-1 viva assessment scoring (scoring_version v1).

Authoritative pipeline:
  analysis JSON → canonical features → quality gates → AI performance /100
  → optional technical fusion → final_score /100 → grade resolver

Does NOT use: LLM criterion scores, UI sliders, confidence_score, engagement_score,
audio_grade, pitch_score (180 Hz), transcript_score, segment_score.

Families (equal weight, missing families dropped and renormalized):
  engagement       — average_engagement_score only (CNN mean, 0–1)
  audio_acoustics  — pitch stability from std, HNR clarity, jitter/shimmer
                     (not audio_grade; not 180 Hz pitch_score; rms excluded as recording-level)
  transcript       — WPM band, hedges, fillers, long pauses, sentence completion
                     (not word_count/80)

SER / facial emotion ratios are stored on the canonical vector as evidence only.
They do not enter the Stage-1 performance mark (emotion ≠ achievement).

Mode WITHOUT_TECHNICAL_ACCURACY: final = AI performance; technical_accuracy = null
Mode WITH_TECHNICAL_ACCURACY: final = w_ai * AI + w_tech * technical_0_100
  Fusion weights are explicit below (v1: equal 0.5 / 0.5).

Grade bands match Gradex_AI_Client viva/types.ts GRADE_BANDS (unchanged).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.canonical_features import (
    FEATURE_SCHEMA_VERSION,
    extract_canonical_features,
    flatten_canonical_features,
)


SCORING_VERSION = "v1"

MODE_WITHOUT = "WITHOUT_TECHNICAL_ACCURACY"
MODE_WITH = "WITH_TECHNICAL_ACCURACY"
STATUS_VALID = "VALID"
STATUS_INCOMPLETE = "INCOMPLETE"

# Equal family weights. Absent families are omitted; remaining weights renormalize.
FAMILY_WEIGHTS: Dict[str, float] = {
    "engagement": 1.0,
    "audio_acoustics": 1.0,
    "transcript": 1.0,
}

# Mode-B fusion. Documented v1 choice: equal contribution. Change only by bumping SCORING_VERSION.
FUSION_WEIGHT_AI = 0.5
FUSION_WEIGHT_TECHNICAL = 0.5

# Same numeric anchors as viva_analysis._score_audio_grade (Praat local jitter/shimmer).
_JITTER_GOOD = 0.005
_JITTER_POOR = 0.030
_SHIMMER_GOOD = 0.030
_SHIMMER_POOR = 0.150

# Whisper ran but produced almost no student speech.
_NO_SPEECH_MAX_WORDS = 2
_NO_SPEECH_MAX_RMS = 0.008
_MIN_AUDIO_DURATION_S = 1.0

REASON_MESSAGES = {
    "no_speech_detected": (
        "The student is on camera but did not speak. Face engagement was measured; "
        "no official mark is given because there is no verbal presentation."
    ),
    "audio_pipeline_failed": (
        "Audio analysis failed, so we cannot tell whether the student spoke. "
        "No official mark — this is a pipeline issue, not a silent-student result."
    ),
    "video_insufficient": "Face coverage is too low to score the video.",
    "audio_insufficient": "Recorded audio is too short or empty to score.",
    "no_scorable_families": "No scorable evidence families were available.",
    "duration_below_engine_minimum": "Audio duration is below the engine minimum.",
}

GRADE_BANDS: List[Tuple[str, float]] = [
    ("A+", 90.0),
    ("A", 80.0),
    ("B+", 70.0),
    ("B", 60.0),
    ("C+", 50.0),
    ("C", 40.0),
    ("F", 0.0),
]


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _quality_score(raw: Optional[float], good: float, poor: float) -> Optional[float]:
    if raw is None:
        return None
    if poor == good:
        return 1.0 if raw <= good else 0.0
    return _clamp((poor - float(raw)) / (poor - good))


def resolve_grade(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    percent = max(0.0, min(100.0, float(score)))
    for grade, minimum in GRADE_BANDS:
        if percent >= minimum:
            return grade
    return "F"


def _whisper_available(quality: Dict[str, Any]) -> bool:
    if quality.get("whisper_available") is False:
        return False
    reasons = [str(item) for item in (quality.get("degraded_reasons") or [])]
    if "transcript_unavailable" in reasons:
        return False
    if str(quality.get("audio_status") or "") == "failed":
        return False
    return True


def classify_speech_evidence(features: Dict[str, Any]) -> Optional[str]:
    """Distinguish silent student vs audio-pipeline failure.

    Returns a validation reason or None if speech evidence is sufficient.
    """
    quality = features.get("quality") or {}
    audio = features.get("audio") or {}
    status = str(quality.get("audio_status") or "")
    duration = quality.get("duration_seconds")
    words = quality.get("transcript_word_count")
    word_count = int(words) if words is not None else 0
    rms = audio.get("rms_mean")
    pitch = audio.get("pitch_mean_hz")
    try:
        duration_s = float(duration) if duration is not None else 0.0
    except (TypeError, ValueError):
        duration_s = 0.0
    try:
        rms_v = float(rms) if rms is not None else None
    except (TypeError, ValueError):
        rms_v = None
    try:
        pitch_v = float(pitch) if pitch is not None else None
    except (TypeError, ValueError):
        pitch_v = None

    if not _whisper_available(quality) or status == "failed":
        return "audio_pipeline_failed"

    if duration_s < _MIN_AUDIO_DURATION_S:
        return None

    silent_track = status == "insufficient_audio" or (
        rms_v is not None and rms_v < _NO_SPEECH_MAX_RMS and (pitch_v is None or pitch_v <= 0.0)
    )
    if word_count == 0:
        return "no_speech_detected"
    if word_count <= _NO_SPEECH_MAX_WORDS and silent_track:
        return "no_speech_detected"
    return None


def validate_features(features: Dict[str, Any]) -> Dict[str, Any]:
    quality = features.get("quality") or {}
    video_status = str(quality.get("video_status") or "")
    audio_status = str(quality.get("audio_status") or "")
    duration = quality.get("duration_seconds")
    reasons: List[str] = []

    video_ok = video_status == "success"
    audio_ok = audio_status in {"success", "degraded"}
    if duration is not None and float(duration) < _MIN_AUDIO_DURATION_S:
        audio_ok = False
        reasons.append("duration_below_engine_minimum")

    if not video_ok:
        reasons.append("video_insufficient")
    if not audio_ok:
        reasons.append("audio_insufficient")

    speech_reason = classify_speech_evidence(features)
    if speech_reason:
        reasons.append(speech_reason)
        unique = list(dict.fromkeys(reasons))
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(speech_reason),
        }

    if not video_ok and not audio_ok:
        unique = list(dict.fromkeys(reasons))
        primary = unique[0] if unique else "no_scorable_families"
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(primary),
        }

    return {"status": STATUS_VALID, "reasons": reasons, "message": None}


def _engagement_family(features: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    value = (features.get("video") or {}).get("average_engagement_score")
    if value is None:
        return None, []
    score = _clamp(float(value))
    return score, [
        {
            "feature": "average_engagement_score",
            "normalized": round(score, 4),
            "direction": "higher_better",
            "missing": False,
            "family": "engagement",
            "weight_within_family": 1.0,
        }
    ]


def _audio_family(features: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    audio = features.get("audio") or {}
    quality = features.get("quality") or {}
    voice_ok = bool(quality.get("voice_quality_measured"))

    pitch_std = audio.get("pitch_std_hz")
    pitch_stability = _clamp(1.0 - (float(pitch_std) / 120.0)) if pitch_std is not None else None

    clarity = None
    articulation = None
    if voice_ok:
        hnr = audio.get("hnr_mean_db")
        clarity = _clamp(float(hnr) / 30.0) if hnr is not None else None
        jitter_part = _quality_score(audio.get("jitter_local"), _JITTER_GOOD, _JITTER_POOR)
        shimmer_part = _quality_score(audio.get("shimmer_local"), _SHIMMER_GOOD, _SHIMMER_POOR)
        if jitter_part is None and shimmer_part is None:
            articulation = None
        elif jitter_part is None:
            articulation = shimmer_part
        elif shimmer_part is None:
            articulation = jitter_part
        else:
            articulation = 0.5 * jitter_part + 0.5 * shimmer_part

    parts = {
        "pitch_stability_from_std": pitch_stability,
        "clarity_from_hnr": clarity,
        "articulation_from_jitter_shimmer": articulation,
    }
    available = {k: v for k, v in parts.items() if v is not None}
    if not available:
        return None, []
    weight = 1.0 / len(available)
    family = sum(available.values()) / len(available)
    components = [
        {
            "feature": name,
            "normalized": round(float(value), 4),
            "direction": "higher_better",
            "missing": False,
            "family": "audio_acoustics",
            "weight_within_family": round(weight, 4),
        }
        for name, value in available.items()
    ]
    return family, components


def _transcript_family(features: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    transcript = features.get("transcript") or {}
    parts: Dict[str, Optional[float]] = {}

    band = transcript.get("speech_rate_band")
    if band == "optimal":
        parts["speech_rate_band"] = 1.0
    elif band in {"too_slow", "too_fast"}:
        parts["speech_rate_band"] = 0.65
    # missing band → omit

    hedge = transcript.get("hedge_count")
    if hedge is not None:
        parts["hedge_count"] = 1.0 - min(1.0, float(hedge) / 8.0)

    filler = transcript.get("filler_count")
    if filler is not None:
        parts["filler_count"] = 1.0 - min(1.0, float(filler) / 12.0)

    long_pauses = transcript.get("long_pause_count")
    if long_pauses is not None:
        parts["long_pause_count"] = 1.0 - min(1.0, float(long_pauses) / 6.0)

    completion = transcript.get("sentence_completion_ratio")
    if completion is not None:
        parts["sentence_completion_ratio"] = _clamp(float(completion))

    available = {k: v for k, v in parts.items() if v is not None}
    if not available:
        return None, []
    weight = 1.0 / len(available)
    family = sum(available.values()) / len(available)
    directions = {
        "speech_rate_band": "optimal_best",
        "hedge_count": "lower_better",
        "filler_count": "lower_better",
        "long_pause_count": "lower_better",
        "sentence_completion_ratio": "higher_better",
    }
    components = [
        {
            "feature": name,
            "normalized": round(float(value), 4),
            "direction": directions.get(name, "higher_better"),
            "missing": False,
            "family": "transcript",
            "weight_within_family": round(weight, 4),
        }
        for name, value in available.items()
    ]
    return family, components


def score_ai_performance(features: Dict[str, Any]) -> Dict[str, Any]:
    families = {
        "engagement": _engagement_family(features),
        "audio_acoustics": _audio_family(features),
        "transcript": _transcript_family(features),
    }
    available: Dict[str, float] = {}
    components: List[Dict[str, Any]] = []
    family_scores: Dict[str, Optional[float]] = {}
    for name, (score, comps) in families.items():
        family_scores[name] = round(score, 4) if score is not None else None
        if score is None:
            continue
        available[name] = score
        components.extend(comps)

    if not available:
        return {
            "score": None,
            "family_scores": family_scores,
            "family_weights_applied": {},
            "components": components,
        }

    weight_sum = sum(FAMILY_WEIGHTS[name] for name in available)
    applied = {name: round(FAMILY_WEIGHTS[name] / weight_sum, 4) for name in available}
    blended = sum(applied[name] * available[name] for name in available)
    return {
        "score": round(_clamp(blended) * 100.0, 2),
        "family_scores": family_scores,
        "family_weights_applied": applied,
        "components": components,
    }


def fuse_final_score(
    *,
    mode: str,
    ai_performance: Optional[float],
    technical_accuracy_0_10: Optional[float],
) -> Dict[str, Any]:
    if ai_performance is None:
        return {
            "final_score": None,
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": None,
        }

    if mode == MODE_WITHOUT:
        return {
            "final_score": round(float(ai_performance), 2),
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": {
                "mode": mode,
                "weight_ai": 1.0,
                "weight_technical": 0.0,
            },
        }

    if technical_accuracy_0_10 is None:
        return {
            "final_score": None,
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": {
                "mode": mode,
                "weight_ai": FUSION_WEIGHT_AI,
                "weight_technical": FUSION_WEIGHT_TECHNICAL,
                "pending": "technical_accuracy_required",
            },
        }

    technical_100 = _clamp(float(technical_accuracy_0_10) / 10.0) * 100.0
    final = FUSION_WEIGHT_AI * float(ai_performance) + FUSION_WEIGHT_TECHNICAL * technical_100
    return {
        "final_score": round(_clamp(final / 100.0) * 100.0, 2),
        "technical_accuracy": round(float(technical_accuracy_0_10), 2),
        "technical_accuracy_100": round(technical_100, 2),
        "fusion": {
            "mode": mode,
            "weight_ai": FUSION_WEIGHT_AI,
            "weight_technical": FUSION_WEIGHT_TECHNICAL,
        },
    }


def build_assessment(
    result: Dict[str, Any],
    *,
    mode: str = MODE_WITHOUT,
    technical_accuracy: Optional[float] = None,
) -> Dict[str, Any]:
    if mode not in {MODE_WITHOUT, MODE_WITH}:
        mode = MODE_WITHOUT

    features = extract_canonical_features(result)
    validation = validate_features(features)
    performance = score_ai_performance(features)

    if validation["status"] == STATUS_INCOMPLETE:
        performance = {**performance, "score": None}
    elif performance.get("score") is None:
        reasons = list(validation.get("reasons") or []) + ["no_scorable_families"]
        validation = {
            "status": STATUS_INCOMPLETE,
            "reasons": reasons,
            "message": REASON_MESSAGES.get("no_scorable_families"),
        }

    tech_input = None if mode == MODE_WITHOUT else technical_accuracy
    fused = fuse_final_score(
        mode=mode,
        ai_performance=performance.get("score"),
        technical_accuracy_0_10=tech_input,
    )
    final_score = fused["final_score"] if validation["status"] == STATUS_VALID else None
    if validation["status"] == STATUS_INCOMPLETE:
        fused = {
            **fused,
            "final_score": None,
            "technical_accuracy": None if mode == MODE_WITHOUT else fused.get("technical_accuracy"),
        }

    return {
        "scoring_version": SCORING_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "assessment_mode": mode,
        "status": validation["status"],
        "quality": features["quality"],
        "features": features,
        "validation": validation,
        "ai_performance": {
            "score": performance.get("score"),
            "family_scores": performance.get("family_scores"),
            "family_weights_applied": performance.get("family_weights_applied"),
            "components": performance.get("components"),
        },
        "technical_accuracy": fused.get("technical_accuracy"),
        "fusion": fused.get("fusion"),
        "final_score": final_score,
        "grade": resolve_grade(final_score),
        "training_features": flatten_canonical_features(features),
    }


def attach_assessment(
    result: Dict[str, Any],
    *,
    mode: str = MODE_WITHOUT,
    technical_accuracy: Optional[float] = None,
) -> Dict[str, Any]:
    enriched = dict(result)
    enriched["assessment"] = build_assessment(
        enriched,
        mode=mode,
        technical_accuracy=technical_accuracy,
    )
    return enriched
