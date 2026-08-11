from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Tuple

from extract_audio import extract_audio
from extract_emotion import extract_speech_emotion
from extract_features import extract_acoustic_features
from transcribe import transcribe_audio


ENGINE_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPTION_OUTPUT = ENGINE_ROOT / "outputs" / "transcription_result.json"
WHISPER_MODEL_SIZE = os.getenv("VIVA_WHISPER_MODEL", "base")


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        converted = float(value)
        if converted != converted or converted in (float("inf"), float("-inf")):
            return default
        return converted
    except (TypeError, ValueError):
        return default


def _pitch_level(pitch_mean: float) -> str:
    if pitch_mean <= 0:
        return "unknown"
    if pitch_mean < 140:
        return "low"
    if pitch_mean > 220:
        return "high"
    return "balanced"


def _emotion_valence(emotion: str) -> str:
    normalized = str(emotion).strip().lower()
    if normalized in {"happy", "surprise"}:
        return "positive"
    if normalized in {"sad", "angry", "fear", "disgust", "contempt"}:
        return "negative"
    if normalized:
        return "neutral"
    return "unknown"


def _fallback_audio_emotion(acoustic_features: Dict[str, Any], transcript: str) -> Dict[str, Any]:
    pitch_mean = _safe_float(acoustic_features.get("pitch_mean"))
    pitch_std = _safe_float(acoustic_features.get("pitch_std"))
    rms_mean = _safe_float(acoustic_features.get("rms_mean"))
    hnr_mean = _safe_float(acoustic_features.get("hnr_mean"))
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
    confidence = _clamp(confidence)

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
        "probabilities": probabilities,
    }


def _score_audio_grade(
    acoustic_features: Dict[str, Any],
    emotion_features: Dict[str, Any],
    transcript: str,
    segment_count: int,
) -> Tuple[float, Dict[str, float]]:
    pitch_mean = _safe_float(acoustic_features.get("pitch_mean"))
    pitch_std = _safe_float(acoustic_features.get("pitch_std"))
    hnr_mean = _safe_float(acoustic_features.get("hnr_mean"))
    jitter_local = _safe_float(acoustic_features.get("jitter_local"))
    shimmer_local = _safe_float(acoustic_features.get("shimmer_local"))
    rms_mean = _safe_float(acoustic_features.get("rms_mean"))

    pitch_score = 1.0 - abs(_clamp((pitch_mean - 180.0) / 140.0, -1.0, 1.0))
    pitch_score = _clamp(pitch_score)

    pitch_stability = 1.0 - _clamp(pitch_std / 120.0)
    clarity_score = _clamp(hnr_mean / 30.0)
    articulation_score = 1.0 - _clamp((jitter_local * 120.0 + shimmer_local * 12.0) / 2.0)
    energy_score = _clamp(rms_mean * 6.0)

    predicted_emotion = str(emotion_features.get("predicted_emotion", "")).strip().lower()
    emotion_confidence = _clamp(_safe_float(emotion_features.get("confidence")))
    emotion_valence = _emotion_valence(predicted_emotion)
    if emotion_valence == "positive":
        emotion_score = 0.9 * emotion_confidence + 0.1
    elif emotion_valence == "neutral":
        emotion_score = 0.75 * emotion_confidence + 0.15
    elif emotion_valence == "negative":
        emotion_score = 0.45 * emotion_confidence + 0.05
    else:
        emotion_score = 0.4 * emotion_confidence
    emotion_score = _clamp(emotion_score)

    transcript_text = transcript.strip()
    transcript_words = len(transcript_text.split()) if transcript_text else 0
    transcript_score = _clamp(transcript_words / 80.0)
    segment_score = _clamp(segment_count / 20.0)

    raw_score = (
        0.22 * pitch_score
        + 0.14 * pitch_stability
        + 0.18 * clarity_score
        + 0.16 * articulation_score
        + 0.12 * energy_score
        + 0.12 * emotion_score
        + 0.06 * transcript_score
        + 0.02 * segment_score
    )

    grade = round(_clamp(raw_score) * 10.0, 2)
    breakdown = {
        "pitch_score": round(pitch_score, 4),
        "pitch_stability": round(pitch_stability, 4),
        "clarity_score": round(clarity_score, 4),
        "articulation_score": round(articulation_score, 4),
        "energy_score": round(energy_score, 4),
        "emotion_score": round(emotion_score, 4),
        "transcript_score": round(transcript_score, 4),
        "segment_score": round(segment_score, 4),
    }
    return grade, breakdown


def analyze_audio_from_video(video_path: str, debug: bool = False) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    temp_audio_fd, temp_audio_path = tempfile.mkstemp(suffix=".wav")
    os.close(temp_audio_fd)

    audio_analysis: Dict[str, Any] = {
        "status": "failed",
        "transcript": "",
        "transcript_excerpt": "",
        "transcript_word_count": 0,
        "segment_count": 0,
        "audio_grade": 0.0,
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
            "probabilities": {},
        },
        "acoustic_features": {},
        "grade_breakdown": {},
    }

    try:
        extract_audio(video_path, temp_audio_path)

        transcript, segments = transcribe_audio(
            temp_audio_path,
            model_size=WHISPER_MODEL_SIZE,
            output_path=TRANSCRIPTION_OUTPUT,
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

        pitch_mean = _safe_float(acoustic_features.get("pitch_mean"))
        pitch_min = _safe_float(acoustic_features.get("pitch_min"))
        pitch_max = _safe_float(acoustic_features.get("pitch_max"))
        pitch_std = _safe_float(acoustic_features.get("pitch_std"))
        pitch_level = _pitch_level(pitch_mean)

        if not emotion_features or not emotion_features.get("predicted_emotion"):
            emotion_features = _fallback_audio_emotion(acoustic_features, transcript_text)

        audio_grade, grade_breakdown = _score_audio_grade(
            acoustic_features=acoustic_features,
            emotion_features=emotion_features,
            transcript=transcript_text,
            segment_count=len(segments),
        )

        predicted_emotion = str(emotion_features.get("predicted_emotion", "unknown")).strip() or "unknown"
        emotion_confidence = _clamp(_safe_float(emotion_features.get("confidence")))
        emotion_probabilities = emotion_features.get("emotion_probabilities") or emotion_features.get("probabilities", {})

        audio_analysis = {
            "status": "success",
            "transcript": transcript_text,
            "transcript_excerpt": excerpt,
            "transcript_word_count": word_count,
            "segment_count": len(segments),
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
                "confidence": round(emotion_confidence, 4),
                "probabilities": emotion_probabilities,
            },
            "acoustic_features": {
                "duration_seconds": round(_safe_float(acoustic_features.get("duration_seconds")), 2),
                "tempo_bpm": round(_safe_float(acoustic_features.get("tempo")), 2),
                "rms_mean": round(_safe_float(acoustic_features.get("rms_mean")), 6),
                "pitch_mean_hz": round(pitch_mean, 2),
                "pitch_min_hz": round(pitch_min, 2),
                "pitch_max_hz": round(pitch_max, 2),
                "pitch_std_hz": round(pitch_std, 2),
                "jitter_local": round(_safe_float(acoustic_features.get("jitter_local")), 6),
                "shimmer_local": round(_safe_float(acoustic_features.get("shimmer_local")), 6),
                "hnr_mean_db": round(_safe_float(acoustic_features.get("hnr_mean")), 2),
            },
            "grade_breakdown": grade_breakdown,
        }

        if debug:
            print("Audio analysis completed")
            print(f"  Transcript words: {word_count}")
            print(f"  Pitch level: {pitch_level}")
            print(f"  Audio grade: {audio_grade}")

    except Exception as exc:
        if debug:
            print(f"Audio analysis failed: {exc}")
        audio_analysis["error"] = str(exc)
    finally:
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except OSError:
                pass

    return {"audio_analysis": audio_analysis}
