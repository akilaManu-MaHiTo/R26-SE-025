from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config import HEURISTIC_EMOTION_CONFIDENCE_CAP, canonical_emotion_label
from extract_audio import extract_audio
from extract_emotion import extract_speech_emotion
from extract_features import extract_acoustic_features
from services.transcript_features import extract_transcript_features
from transcribe import transcribe_audio


ENGINE_ROOT = Path(__file__).resolve().parents[1]
WHISPER_MODEL_SIZE = os.getenv("VIVA_WHISPER_MODEL", "base")

# Healthy-ish voice-quality anchors (Praat local jitter/shimmer as fractions).
# Below low → near-perfect; above high → near-zero. Tuned to published adult norms.
_JITTER_GOOD = 0.005
_JITTER_POOR = 0.030
_SHIMMER_GOOD = 0.030
_SHIMMER_POOR = 0.150


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    if value is None:
        return default
    try:
        converted = float(value)
        if converted != converted or converted in (float("inf"), float("-inf")):
            return default
        return converted
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> Optional[float]:
    """Preserve None for unmeasured features; do not coerce missing → 0."""
    if value is None:
        return None
    return _safe_float(value, default=None)


def _pitch_level(pitch_mean: float) -> str:
    if pitch_mean <= 0:
        return "unknown"
    if pitch_mean < 140:
        return "low"
    if pitch_mean > 220:
        return "high"
    return "balanced"


def _emotion_valence(emotion: str) -> str:
    normalized = canonical_emotion_label(emotion)
    if normalized in {"happy", "surprise"}:
        return "positive"
    if normalized in {"sad", "angry", "fear", "disgust", "contempt"}:
        return "negative"
    if normalized:
        return "neutral"
    return "unknown"


def _cap_heuristic_emotion(emotion_features: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(emotion_features)
    source = str(result.get("source", "heuristic")).strip().lower() or "heuristic"
    result["source"] = source
    if source != "model":
        confidence = _clamp(_safe_float(result.get("confidence"), 0.0) or 0.0, 0.0, HEURISTIC_EMOTION_CONFIDENCE_CAP)
        result["confidence"] = round(confidence, 4)
    return result


def _fallback_audio_emotion(acoustic_features: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    pitch_mean = _safe_float(acoustic_features.get("pitch_mean"), 0.0) or 0.0
    pitch_std = _safe_float(acoustic_features.get("pitch_std"), 0.0) or 0.0
    rms_mean = _safe_float(acoustic_features.get("rms_mean"), 0.0) or 0.0
    hnr_mean = _optional_float(acoustic_features.get("hnr_mean")) or 0.0
    transcript_text = transcript.strip().lower()

    positive_hint_words = {"excited", "great", "happy", "confident", "exciting", "good"}
    negative_hint_words = {"sad", "sorry", "worried", "nervous", "concerned", "bad"}
    positive_hint = any(word in transcript_text for word in positive_hint_words)
    negative_hint = any(word in transcript_text for word in negative_hint_words)

    if negative_hint or pitch_mean < 145:
        emotion = "sad"
    elif positive_hint or pitch_mean >= 225:
        emotion = "surprise" if pitch_std > 45 or rms_mean > 0.05 else "happy"
    else:
        emotion = "neutral"

    confidence = 0.35
    confidence += min(0.25, abs(pitch_mean - 180.0) / 200.0)
    confidence += min(0.15, pitch_std / 180.0)
    confidence += min(0.15, rms_mean * 2.5)
    confidence += min(0.10, hnr_mean / 80.0)
    confidence = _clamp(confidence, 0.0, HEURISTIC_EMOTION_CONFIDENCE_CAP)

    probabilities = {
        "happy": 0.0,
        "surprise": 0.0,
        "neutral": 0.0,
        "sad": 0.0,
    }
    if emotion == "happy":
        probabilities["happy"] = round(confidence, 4)
        probabilities["neutral"] = round(1.0 - confidence, 4)
    elif emotion == "surprise":
        probabilities["surprise"] = round(confidence, 4)
        probabilities["happy"] = round(max(0.0, confidence - 0.15), 4)
    elif emotion == "sad":
        probabilities["sad"] = round(confidence, 4)
        probabilities["neutral"] = round(max(0.0, 1.0 - confidence), 4)
    else:
        probabilities["neutral"] = round(confidence, 4)
        probabilities["happy"] = round((1.0 - confidence) * 0.35, 4)

    return {
        "predicted_emotion": emotion,
        "valence": _emotion_valence(emotion),
        "confidence": round(confidence, 4),
        "source": "heuristic",
        "probabilities": probabilities,
    }


def _quality_score(value: Optional[float], good: float, poor: float) -> Optional[float]:
    """Map measured metric onto [0,1] using good/poor anchors. None stays None."""
    if value is None:
        return None
    if poor <= good:
        return 0.5
    return _clamp(1.0 - (float(value) - good) / (poor - good))


def _audio_is_sufficient(acoustic_features: Dict[str, Any], transcript: str) -> bool:
    duration = _safe_float(acoustic_features.get("duration_seconds"), 0.0) or 0.0
    rms_mean = _safe_float(acoustic_features.get("rms_mean"), 0.0) or 0.0
    pitch_mean = _safe_float(acoustic_features.get("pitch_mean"), 0.0) or 0.0
    word_count = len(transcript.split()) if transcript.strip() else 0

    if duration < 1.0:
        return False
    # Completely silent / empty: refuse to invent a grade.
    if rms_mean < 0.001 and pitch_mean <= 0.0 and word_count == 0:
        return False
    return True


def _score_audio_grade(
    acoustic_features: Dict[str, Any],
    emotion_features: Dict[str, Any],
    transcript: str,
    segment_count: int,
) -> Tuple[Optional[float], Dict[str, Any]]:
    pitch_mean = _safe_float(acoustic_features.get("pitch_mean"), 0.0) or 0.0
    pitch_std = _safe_float(acoustic_features.get("pitch_std"), 0.0) or 0.0
    rms_mean = _safe_float(acoustic_features.get("rms_mean"), 0.0) or 0.0

    jitter_local = _optional_float(acoustic_features.get("jitter_local"))
    shimmer_local = _optional_float(acoustic_features.get("shimmer_local"))
    hnr_mean = _optional_float(acoustic_features.get("hnr_mean"))
    voice_quality_measured = bool(acoustic_features.get("voice_quality_measured"))

    # Unmeasured pitch: exclude pitch terms rather than scoring against 180 Hz.
    if pitch_mean > 0.0:
        pitch_score: Optional[float] = _clamp(1.0 - abs(_clamp((pitch_mean - 180.0) / 140.0, -1.0, 1.0)))
        pitch_stability: Optional[float] = 1.0 - _clamp(pitch_std / 120.0)
    else:
        pitch_score = None
        pitch_stability = None

    clarity_score = _clamp(hnr_mean / 30.0) if hnr_mean is not None and voice_quality_measured else None

    jitter_part = _quality_score(jitter_local, _JITTER_GOOD, _JITTER_POOR) if voice_quality_measured else None
    shimmer_part = _quality_score(shimmer_local, _SHIMMER_GOOD, _SHIMMER_POOR) if voice_quality_measured else None
    if jitter_part is None and shimmer_part is None:
        articulation_score: Optional[float] = None
    elif jitter_part is None:
        articulation_score = shimmer_part
    elif shimmer_part is None:
        articulation_score = jitter_part
    else:
        articulation_score = 0.5 * jitter_part + 0.5 * shimmer_part

    energy_score: Optional[float] = _clamp(rms_mean * 6.0) if rms_mean > 0.0 else None

    emotion_source = str(emotion_features.get("source", "heuristic")).strip().lower() or "heuristic"
    predicted_emotion = canonical_emotion_label(str(emotion_features.get("predicted_emotion", "")))
    emotion_confidence = _clamp(_safe_float(emotion_features.get("confidence"), 0.0) or 0.0)

    # Heuristic SER must not move the grade — only a real model source participates.
    emotion_score: Optional[float] = None
    if emotion_source == "model":
        emotion_confidence = min(emotion_confidence, 1.0)
        emotion_valence = _emotion_valence(predicted_emotion)
        if emotion_valence == "positive":
            emotion_raw = 0.9 * emotion_confidence + 0.1
        elif emotion_valence == "neutral":
            emotion_raw = 0.75 * emotion_confidence + 0.15
        elif emotion_valence == "negative":
            emotion_raw = 0.45 * emotion_confidence + 0.05
        else:
            emotion_raw = 0.4 * emotion_confidence
        emotion_score = _clamp(emotion_raw)
    else:
        emotion_confidence = min(emotion_confidence, HEURISTIC_EMOTION_CONFIDENCE_CAP)

    transcript_text = transcript.strip()
    transcript_words = len(transcript_text.split()) if transcript_text else 0
    transcript_score: Optional[float] = _clamp(transcript_words / 80.0) if transcript_words > 0 else None
    segment_score: Optional[float] = _clamp(segment_count / 20.0) if segment_count > 0 else None

    weights = {
        "pitch_score": 0.22,
        "pitch_stability": 0.14,
        "clarity_score": 0.18,
        "articulation_score": 0.16,
        "energy_score": 0.12,
        "emotion_score": 0.12,
        "transcript_score": 0.06,
        "segment_score": 0.02,
    }
    components: Dict[str, Optional[float]] = {
        "pitch_score": pitch_score,
        "pitch_stability": pitch_stability,
        "clarity_score": clarity_score,
        "articulation_score": articulation_score,
        "energy_score": energy_score,
        "emotion_score": emotion_score,
        "transcript_score": transcript_score,
        "segment_score": segment_score,
    }

    available = {key: value for key, value in components.items() if value is not None}
    if not available:
        breakdown = {
            key: None for key in weights
        }
        breakdown["excluded_components"] = list(weights.keys())
        breakdown["emotion_source"] = emotion_source
        breakdown["emotion_excluded"] = emotion_source != "model"
        return None, breakdown

    weight_sum = sum(weights[key] for key in available)
    raw_score = sum((weights[key] / weight_sum) * float(available[key]) for key in available)
    grade = round(_clamp(raw_score) * 10.0, 2)

    breakdown: Dict[str, Any] = {
        key: (round(float(value), 4) if value is not None else None)
        for key, value in components.items()
    }
    breakdown["excluded_components"] = [key for key, value in components.items() if value is None]
    breakdown["emotion_source"] = emotion_source
    breakdown["emotion_excluded"] = emotion_source != "model"
    breakdown["voice_quality_measured"] = voice_quality_measured
    return grade, breakdown


def _build_degraded_reasons(
    whisper_meta: Dict[str, Any],
    transcript_text: str,
    acoustic_features: Dict[str, Any],
    emotion_features: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []
    if not whisper_meta.get("available"):
        reasons.append("transcript_unavailable")
    elif not transcript_text.strip():
        reasons.append("transcript_empty")
    if not bool(acoustic_features.get("voice_quality_measured")):
        reasons.append("voice_quality_unmeasured")
    emotion_source = str(emotion_features.get("source", "heuristic")).strip().lower()
    if emotion_source != "model":
        reasons.append("emotion_heuristic")
    return reasons


def _pack_audio_payload(
    *,
    status: str,
    transcript_text: str,
    excerpt: str,
    word_count: int,
    segment_count: int,
    audio_grade: Optional[float],
    pitch_level: str,
    pitch_mean: float,
    pitch_min: float,
    pitch_max: float,
    pitch_std: float,
    emotion_features: Dict[str, Any],
    acoustic_features: Dict[str, Any],
    grade_breakdown: Dict[str, Any],
    degraded_reasons: List[str],
    transcript_features: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    predicted_emotion = str(emotion_features.get("predicted_emotion", "unknown")).strip() or "unknown"
    payload: Dict[str, Any] = {
        "status": status,
        "transcript": transcript_text,
        "transcript_excerpt": excerpt,
        "transcript_word_count": word_count,
        "segment_count": segment_count,
        "audio_grade": audio_grade,
        "pitch_profile": {
            "level": pitch_level,
            "mean_hz": round(pitch_mean, 2),
            "min_hz": round(pitch_min, 2),
            "max_hz": round(pitch_max, 2),
            "std_hz": round(pitch_std, 2),
        },
        "audio_emotion": {
            "predicted_emotion": predicted_emotion,
            "valence": _emotion_valence(predicted_emotion),
            "confidence": round(_clamp(_safe_float(emotion_features.get("confidence"), 0.0) or 0.0), 4),
            "source": str(emotion_features.get("source", "heuristic")),
            "probabilities": emotion_features.get("emotion_probabilities")
            or emotion_features.get("probabilities", {}),
        },
        "acoustic_features": {
            "duration_seconds": round(_safe_float(acoustic_features.get("duration_seconds"), 0.0) or 0.0, 2),
            "tempo_bpm": round(_safe_float(acoustic_features.get("tempo"), 0.0) or 0.0, 2),
            "rms_mean": round(_safe_float(acoustic_features.get("rms_mean"), 0.0) or 0.0, 6),
            "pitch_mean_hz": round(pitch_mean, 2),
            "pitch_min_hz": round(pitch_min, 2),
            "pitch_max_hz": round(pitch_max, 2),
            "pitch_std_hz": round(pitch_std, 2),
            "jitter_local": _optional_float(acoustic_features.get("jitter_local")),
            "shimmer_local": _optional_float(acoustic_features.get("shimmer_local")),
            "hnr_mean_db": _optional_float(acoustic_features.get("hnr_mean")),
            "voice_quality_measured": bool(acoustic_features.get("voice_quality_measured")),
        },
        "transcript_features": transcript_features or {},
        "grade_breakdown": grade_breakdown,
        "degraded_reasons": degraded_reasons,
    }
    if error:
        payload["error"] = error
    return payload


def analyze_audio_from_video(video_path: str, debug: bool = False) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    temp_audio_fd, temp_audio_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_audio_fd)
    transcription_output = ENGINE_ROOT / "outputs" / f"transcription_{uuid.uuid4().hex}.json"

    audio_analysis: Dict[str, Any] = {
        "status": "failed",
        "transcript": "",
        "transcript_excerpt": "",
        "transcript_word_count": 0,
        "segment_count": 0,
        "audio_grade": None,
        "pitch_profile": {
            "level": "unknown",
            "mean_hz": 0.0,
            "min_hz": 0.0,
            "max_hz": 0.0,
            "std_hz": 0.0,
        },
        "audio_emotion": {
            "predicted_emotion": "unknown",
            "valence": "unknown",
            "confidence": 0.0,
            "source": "unknown",
            "probabilities": {},
        },
        "acoustic_features": {},
        "grade_breakdown": {},
        "degraded_reasons": [],
    }

    try:
        extract_audio(video_path, temp_audio_path)

        transcript, segments, whisper_meta = transcribe_audio(
            temp_audio_path,
            model_size=WHISPER_MODEL_SIZE,
            output_path=transcription_output,
        )
        acoustic_features = extract_acoustic_features(temp_audio_path)

        emotion_features: Dict[str, Any] = {}
        try:
            emotion_features = extract_speech_emotion(temp_audio_path)
        except Exception as exc:
            if debug:
                print(f"Audio emotion extraction failed: {exc}")

        transcript_text = transcript.strip()
        word_count = len(transcript_text.split()) if transcript_text else 0
        excerpt = transcript_text[:320]
        if len(transcript_text) > 320:
            excerpt = f"{excerpt.rstrip()}..."

        pitch_mean = _safe_float(acoustic_features.get("pitch_mean"), 0.0) or 0.0
        pitch_min = _safe_float(acoustic_features.get("pitch_min"), 0.0) or 0.0
        pitch_max = _safe_float(acoustic_features.get("pitch_max"), 0.0) or 0.0
        pitch_std = _safe_float(acoustic_features.get("pitch_std"), 0.0) or 0.0
        pitch_level = _pitch_level(pitch_mean)

        if not emotion_features or not emotion_features.get("predicted_emotion"):
            emotion_features = _fallback_audio_emotion(acoustic_features, transcript_text)
        emotion_features = _cap_heuristic_emotion(emotion_features)

        degraded_reasons = _build_degraded_reasons(
            whisper_meta=whisper_meta,
            transcript_text=transcript_text,
            acoustic_features=acoustic_features,
            emotion_features=emotion_features,
        )

        transcript_features = extract_transcript_features(
            transcript=transcript_text,
            segments=segments,
            duration_seconds=_safe_float(acoustic_features.get("duration_seconds")),
            words_with_times=whisper_meta.get("words_with_times") or [],
        )

        common_kwargs = dict(
            transcript_text=transcript_text,
            excerpt=excerpt,
            word_count=word_count,
            segment_count=len(segments),
            pitch_level=pitch_level,
            pitch_mean=pitch_mean,
            pitch_min=pitch_min,
            pitch_max=pitch_max,
            pitch_std=pitch_std,
            emotion_features=emotion_features,
            acoustic_features=acoustic_features,
            degraded_reasons=degraded_reasons,
            transcript_features=transcript_features,
        )

        if not _audio_is_sufficient(acoustic_features, transcript_text):
            audio_analysis = _pack_audio_payload(
                status="insufficient_audio",
                audio_grade=None,
                grade_breakdown={},
                error="Insufficient voiced audio to compute a reliable grade",
                **common_kwargs,
            )
        else:
            audio_grade, grade_breakdown = _score_audio_grade(
                acoustic_features=acoustic_features,
                emotion_features=emotion_features,
                transcript=transcript_text,
                segment_count=len(segments),
            )

            if audio_grade is None:
                status = "insufficient_audio"
                error: Optional[str] = "No measurable audio components available for grading"
            elif degraded_reasons:
                status = "degraded"
                error = None
            else:
                status = "success"
                error = None

            audio_analysis = _pack_audio_payload(
                status=status,
                audio_grade=audio_grade,
                grade_breakdown=grade_breakdown,
                error=error,
                **common_kwargs,
            )

        if debug:
            print("Audio analysis completed")
            print(f"  Status: {audio_analysis.get('status')}")
            print(f"  Degraded reasons: {audio_analysis.get('degraded_reasons')}")
            print(f"  Transcript words: {word_count}")
            print(f"  Pitch level: {pitch_level}")
            print(f"  Audio grade: {audio_analysis.get('audio_grade')}")

    except Exception as exc:
        if debug:
            print(f"Audio analysis failed: {exc}")
        audio_analysis["error"] = str(exc)
    finally:
        for path in (temp_audio_path, transcription_output):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass

    return {"audio_analysis": audio_analysis}
