"""Stage-1 viva assessment scoring (scoring_version v1.3).

Authoritative pipeline:
  analysis JSON → canonical features → quality gates → AI performance /100
  → optional technical fusion → final_score /100 → official mark → grade resolver

Marks: the official mark is out of `MARKING_SCALE.mark_max` (20 by default; see
services/marking_scale.py, set with VIVA_MARK_MAX). The pipeline computes on a 0-100 percentage
(the families, the fusion and `final_score` are percentages), and the official mark is that
percentage scaled to the mark scale and rounded:  final_mark = final_score / 100 * mark_max.
The grade follows the rounded mark, i.e. the number the examiner sees.

Does NOT use: LLM criterion scores, UI sliders, engagement_score (diagnostic blend),
audio_grade, pitch_score (180 Hz), transcript_score, segment_score.

Families (equal weight, missing families dropped and renormalized):
  engagement       — equal mix of CNN average_engagement_score, facial_confidence
                     (confidence_score/100), facial emotion profile, on-camera gaze ratio,
                     head stability and blink-rate score (v1.2; unavailable parts dropped)
  audio_acoustics  — pitch stability from std, HNR clarity, jitter/shimmer, plus
                     speech-emotion tone at SER_TONE_WEIGHT (v1.2; real SER model only)
                     (not audio_grade; not 180 Hz pitch_score; rms excluded as recording-level)
  transcript       — WPM band, hedges, fillers, long pauses, sentence completion
                     (not word_count/80)

Raw emotion ratio bars remain UI evidence; the scored face-tone inputs are listed above.

Mode WITHOUT_TECHNICAL_ACCURACY: final = AI performance; technical_accuracy = null
Mode WITH_TECHNICAL_ACCURACY: final = w_ai * AI + w_tech * technical_0_100
  where the examiner enters technical accuracy out of `MARKING_SCALE.technical_max` and
  technical_0_100 = technical / technical_max * 100.
  Fusion weights are explicit below (v1: equal 0.5 / 0.5).

Grade bands are defined once, as percentages, in services/marking_scale.py; the web client reads
the scale and bands from the server (GET /api/viva-config) instead of keeping its own copy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.marking_scale import MARKING_SCALE, PERCENT_MAX
from services.canonical_features import (
    FEATURE_SCHEMA_VERSION,
    extract_canonical_features,
    flatten_canonical_features,
)


SCORING_VERSION = "v1.3"


# Technical vivas only: the smallest share of the subject's concept weight that the answer
# must touch. Below this the student almost certainly answered a different topic (or the
# wrong subject), so no official mark is given and the recording is held for review.
# Override with VIVA_MIN_TOPIC_COVERAGE (a fraction, e.g. 0.05 for 5%).
def _min_topic_coverage() -> float:
    import os

    try:
        value = float(os.getenv("VIVA_MIN_TOPIC_COVERAGE", "0.05"))
    except ValueError:
        return 0.05
    return value if 0.0 <= value <= 1.0 else 0.05


MIN_TOPIC_COVERAGE = _min_topic_coverage()

# Speech-emotion tone is scored inside audio_acoustics at reduced weight: the SER model
# is trained on acted speech (IEMOCAP) and over-predicts "angry" on real presentations.
# A weight of 1.0 would equal the other audio parts; change only by bumping SCORING_VERSION.
SER_TONE_WEIGHT = 0.5

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

# Same coverage floor as config.MIN_FACE_COVERAGE_RATIO. Kept local (no config
# import elsewhere in this module) — only used to tell "no face" apart from
# "face present but mostly non-frontal" when picking the INCOMPLETE message.
_MIN_FACE_COVERAGE_RATIO = 0.15

REASON_MESSAGES = {
    "insufficient_lip_motion": (
        "Speech was detected but almost no mouth movement was visible on camera. "
        "Face the webcam and speak so your lips can be seen."
    ),
    "lip_motion_unavailable": (
        "Speech was detected but mouth movement could not be measured on the face track. "
        "Point the webcam at the student and re-record with clear lip visibility."
    ),
    "no_speech_detected": (
        "The student is on camera but did not speak. Face engagement was measured; "
        "no official mark is given because there is no verbal presentation."
    ),
    "audio_pipeline_failed": (
        "Audio analysis failed, so we cannot tell whether the student spoke. "
        "No official mark — this is a pipeline issue, not a silent-student result."
    ),
    "video_insufficient": (
        "No usable face on camera. Emotion and engagement cannot be measured, "
        "so this recording is incomplete — point the webcam at the student and re-record."
    ),
    "video_non_frontal": (
        "A face was visible but mostly turned away from the camera, so emotion and "
        "engagement cannot be measured reliably. Ask the student to face the camera "
        "directly and re-record."
    ),
    "audio_insufficient": "Recorded audio is too short or empty to score.",
    "no_scorable_families": "No scorable evidence families were available.",
    "duration_below_engine_minimum": "Audio duration is below the engine minimum.",
    "insufficient_topic_coverage": (
        "The answer covered almost none of the subject's concepts. The student may have answered "
        "a different topic or the wrong subject. No official mark is given — review the recording "
        "or run the viva again."
    ),
    "multiple_faces_detected": (
        "More than one person was clearly visible on camera. "
        "Re-record with only the student in frame."
    ),
}

# Grade bands as percentages, derived from the marking scale (the single definition).
GRADE_BANDS: List[Tuple[str, float]] = list(MARKING_SCALE.grade_bands_percent)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _quality_score(raw: Optional[float], good: float, poor: float) -> Optional[float]:
    if raw is None:
        return None
    if poor == good:
        return 1.0 if raw <= good else 0.0
    return _clamp((poor - float(raw)) / (poor - good))


def resolve_grade(score: Optional[float]) -> Optional[str]:
    """Grade for a 0-100 percentage."""
    return MARKING_SCALE.resolve_grade_from_percent(score)


def percent_to_mark(percent: Optional[float]) -> Optional[float]:
    """Scale a 0-100 percentage to the official mark on the configured scale."""
    return MARKING_SCALE.percent_to_mark(percent)


def resolve_grade_from_mark(mark: Optional[float]) -> Optional[str]:
    """Grade for an official mark. Pass the ROUNDED mark so the grade matches what is shown."""
    return MARKING_SCALE.resolve_grade(mark)


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


def validate_features(
    features: Dict[str, Any],
    *,
    lip_reason: Optional[str] = None,
    multi_face_reason: Optional[str] = None,
) -> Dict[str, Any]:
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

    frames_sampled = quality.get("frames_sampled") or 0
    frames_with_face = quality.get("frames_with_face") or 0
    frames_non_frontal = quality.get("frames_rejected_non_frontal") or 0
    mostly_non_frontal = (
        not video_ok
        and frames_sampled > 0
        and frames_with_face == 0
        and frames_non_frontal > 0
        and frames_non_frontal >= frames_sampled * _MIN_FACE_COVERAGE_RATIO
    )

    if not video_ok:
        reasons.append("video_non_frontal" if mostly_non_frontal else "video_insufficient")
    if not audio_ok:
        reasons.append("audio_insufficient")

    speech_reason = classify_speech_evidence(features)
    if speech_reason:
        reasons.append(speech_reason)
    if lip_reason:
        reasons.append(lip_reason)
    if multi_face_reason:
        reasons.append(multi_face_reason)

    unique = list(dict.fromkeys(reasons))

    # Face is required: emotion/engagement cannot be inferred from audio alone.
    if not video_ok:
        video_reason = "video_non_frontal" if mostly_non_frontal else "video_insufficient"
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(video_reason),
        }

    if multi_face_reason:
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(multi_face_reason),
        }

    if lip_reason:
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(lip_reason),
        }

    if speech_reason:
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(speech_reason),
        }

    if not audio_ok:
        primary = unique[0] if unique else "audio_insufficient"
        return {
            "status": STATUS_INCOMPLETE,
            "reasons": unique,
            "message": REASON_MESSAGES.get(primary) or REASON_MESSAGES.get("audio_insufficient"),
        }

    return {"status": STATUS_VALID, "reasons": unique, "message": None}


def _engagement_family(features: Dict[str, Any]) -> Tuple[Optional[float], List[Dict[str, Any]]]:
    # CNN engagement + facial confidence (positivity). Not diagnostic engagement_score blend.
    video = features.get("video") or {}
    parts: Dict[str, Optional[float]] = {
        "average_engagement_score": (
            _clamp(float(video["average_engagement_score"]))
            if video.get("average_engagement_score") is not None
            else None
        ),
        "facial_confidence": (
            _clamp(float(video["facial_confidence"]))
            if video.get("facial_confidence") is not None
            else None
        ),
        # v1.2: facial behaviour signals count toward the mark.
        "emotion_profile": video.get("emotion_profile_score"),
        "gaze_on_camera_ratio": video.get("gaze_on_camera_ratio"),
        "head_stability": video.get("head_stability"),
        "blink_score": video.get("blink_score"),
    }
    available = {k: _clamp(float(v)) for k, v in parts.items() if v is not None}
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
            "family": "engagement",
            "weight_within_family": round(weight, 4),
        }
        for name, value in available.items()
    ]
    return family, components


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
    tone = (features.get("ser") or {}).get("tone_score")
    available = {k: v for k, v in parts.items() if v is not None}
    weights = {k: 1.0 for k in available}
    if tone is not None:
        available["speech_emotion_tone"] = _clamp(float(tone))
        weights["speech_emotion_tone"] = SER_TONE_WEIGHT
    if not available:
        return None, []
    total_w = sum(weights.values())
    family = sum(weights[k] * v for k, v in available.items()) / total_w
    components = [
        {
            "feature": name,
            "normalized": round(float(value), 4),
            "direction": "higher_better",
            "missing": False,
            "family": "audio_acoustics",
            "weight_within_family": round(weights[name] / total_w, 4),
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
    technical_accuracy: Optional[float],
) -> Dict[str, Any]:
    """Fuse the AI performance percentage with the examiner's technical score.

    The technical score is out of `MARKING_SCALE.technical_max`. `final_score` stays a 0-100
    percentage; `final_mark` is the official mark on the configured scale.
    """
    if ai_performance is None:
        return {
            "final_score": None,
            "final_mark": None,
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": None,
        }

    if mode == MODE_WITHOUT:
        return {
            "final_score": round(float(ai_performance), 2),
            "final_mark": percent_to_mark(ai_performance),
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": {
                "mode": mode,
                # What this assessment actually applied: AI performance only.
                "weight_ai": 1.0,
                "weight_technical": 0.0,
                # What a WITH_TECHNICAL_ACCURACY publish would apply. Exposed so
                # the examiner UI can preview a fused mark without duplicating
                # scorer constants on the client.
                "with_technical": {
                    "weight_ai": FUSION_WEIGHT_AI,
                    "weight_technical": FUSION_WEIGHT_TECHNICAL,
                },
            },
        }

    if technical_accuracy is None:
        return {
            "final_score": None,
            "final_mark": None,
            "technical_accuracy": None,
            "technical_accuracy_100": None,
            "fusion": {
                "mode": mode,
                "weight_ai": FUSION_WEIGHT_AI,
                "weight_technical": FUSION_WEIGHT_TECHNICAL,
                "pending": "technical_accuracy_required",
            },
        }

    technical_100 = MARKING_SCALE.technical_to_percent(technical_accuracy)
    final = FUSION_WEIGHT_AI * float(ai_performance) + FUSION_WEIGHT_TECHNICAL * technical_100
    final_percent = round(_clamp(final / PERCENT_MAX) * PERCENT_MAX, 2)
    return {
        "final_score": final_percent,
        "final_mark": percent_to_mark(final_percent),
        "technical_accuracy": MARKING_SCALE.clamp_technical(technical_accuracy),
        "technical_accuracy_100": round(technical_100, 2),
        "fusion": {
            "mode": mode,
            "weight_ai": FUSION_WEIGHT_AI,
            "weight_technical": FUSION_WEIGHT_TECHNICAL,
        },
    }


def summarize_topic_coverage(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Share of the subject rubric's concept weight the answer touched.

    Read from the AI technical-accuracy result. Returns None when that result is missing or
    unusable (no subject linked, scoring failed), because coverage cannot be judged then and
    the recording must not be penalised for it.
    """
    tech = result.get("technical_accuracy_ai")
    if not isinstance(tech, dict) or tech.get("status") not in {"success", "partial"}:
        return None
    concepts = [c for c in (tech.get("concepts") or []) if isinstance(c, dict)]
    if not concepts:
        return None

    def _weight(concept: Dict[str, Any]) -> float:
        try:
            weight = float(concept.get("weight"))
        except (TypeError, ValueError):
            return 1.0
        return weight if weight > 0 else 0.0

    total = sum(_weight(c) for c in concepts)
    if total <= 0:
        return None
    covered = [c for c in concepts if c.get("covered") is True]
    covered_weight = sum(_weight(c) for c in covered)
    return {
        "measured": True,
        "coverage_ratio": round(covered_weight / total, 4),
        "minimum": MIN_TOPIC_COVERAGE,
        "concepts_covered": len(covered),
        "concepts_total": len(concepts),
    }


def build_assessment(
    result: Dict[str, Any],
    *,
    mode: str = MODE_WITHOUT,
    technical_accuracy: Optional[float] = None,
) -> Dict[str, Any]:
    if mode not in {MODE_WITHOUT, MODE_WITH}:
        mode = MODE_WITHOUT

    from services.pipeline_progress import emit
    from services.lip_motion_validation import classify_lip_motion_evidence, summarize_lip_motion

    emit("assessment", "Computing official mark")
    from services.multi_face_validation import classify_multi_face_evidence, summarize_multi_face

    lip_motion = summarize_lip_motion(result)
    lip_reason = classify_lip_motion_evidence(result)
    multi_face = summarize_multi_face(result)
    multi_face_reason = classify_multi_face_evidence(result)
    features = extract_canonical_features(result)
    validation = validate_features(
        features,
        lip_reason=lip_reason,
        multi_face_reason=multi_face_reason,
    )
    topic_coverage = summarize_topic_coverage(result) if mode == MODE_WITH else None
    if (
        topic_coverage is not None
        and validation["status"] == STATUS_VALID
        and topic_coverage["coverage_ratio"] < MIN_TOPIC_COVERAGE
    ):
        validation = {
            "status": STATUS_INCOMPLETE,
            "reasons": list(validation.get("reasons") or []) + ["insufficient_topic_coverage"],
            "message": (
                f"Only {topic_coverage['coverage_ratio'] * 100:.1f}% of the subject's concepts "
                f"({topic_coverage['concepts_covered']} of {topic_coverage['concepts_total']}) were "
                f"covered, below the {MIN_TOPIC_COVERAGE * 100:.0f}% minimum. "
                + REASON_MESSAGES["insufficient_topic_coverage"]
            ),
        }
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
        technical_accuracy=tech_input,
    )
    final_score = fused["final_score"] if validation["status"] == STATUS_VALID else None
    final_mark = fused.get("final_mark") if validation["status"] == STATUS_VALID else None
    if validation["status"] == STATUS_INCOMPLETE:
        fused = {
            **fused,
            "final_score": None,
            "final_mark": None,
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
        "topic_coverage": topic_coverage,
        "lip_motion": lip_motion,
        "multi_face": multi_face,
        "ai_performance": {
            "score": performance.get("score"),
            "mark": percent_to_mark(performance.get("score")),
            "family_scores": performance.get("family_scores"),
            "family_weights_applied": performance.get("family_weights_applied"),
            "components": performance.get("components"),
        },
        "technical_accuracy": fused.get("technical_accuracy"),
        "fusion": fused.get("fusion"),
        "final_score": final_score,
        "final_mark": final_mark,
        "final_mark_max": MARKING_SCALE.mark_max,
        "technical_max": MARKING_SCALE.technical_max,
        "grade": resolve_grade_from_mark(final_mark),
        "training_features": flatten_canonical_features(features),
    }


def attach_assessment(
    result: Dict[str, Any],
    *,
    mode: str = MODE_WITHOUT,
    technical_accuracy: Optional[float] = None,
) -> Dict[str, Any]:
    enriched = dict(result)
    assessment = build_assessment(
        enriched,
        mode=mode,
        technical_accuracy=technical_accuracy,
    )
    enriched["assessment"] = assessment
    if isinstance(assessment.get("lip_motion"), dict):
        enriched["lip_motion"] = assessment["lip_motion"]
    if isinstance(assessment.get("multi_face"), dict):
        enriched["multi_face"] = assessment["multi_face"]
    from services.feature_complete import attach_feature_complete

    return attach_feature_complete(enriched)
