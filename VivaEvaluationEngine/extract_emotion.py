from __future__ import annotations

from typing import Dict

import librosa
import numpy as np

from config import HEURISTIC_EMOTION_CONFIDENCE_CAP


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def extract_speech_emotion(audio_path: str) -> Dict[str, object]:
    # Lightweight heuristic emotion estimator used when no dedicated speech-emotion model is wired.
    # Confidence is intentionally capped so downstream scoring cannot treat this as a trained model.
    y, sr = librosa.load(audio_path, sr=16000, mono=True)
    if y.size == 0:
        return {
            "predicted_emotion": "neutral",
            "confidence": 0.3,
            "source": "heuristic",
            "emotion_probabilities": {"neutral": 1.0},
        }

    rms = float(np.mean(librosa.feature.rms(y=y)))

    try:
        f0 = librosa.yin(y, fmin=65, fmax=400, sr=sr)
        f0 = np.asarray(f0, dtype=float)
        valid = f0[np.isfinite(f0) & (f0 > 0)]
        pitch_mean = float(np.mean(valid)) if valid.size else 0.0
        pitch_std = float(np.std(valid)) if valid.size else 0.0
    except Exception:
        pitch_mean = 0.0
        pitch_std = 0.0

    if pitch_mean >= 225 or (pitch_std > 45 and rms > 0.04):
        emotion = "surprise"
    elif pitch_mean <= 145:
        emotion = "sad"
    elif rms > 0.05:
        emotion = "happy"
    else:
        emotion = "neutral"

    confidence = 0.35
    confidence += min(0.25, abs(pitch_mean - 180.0) / 220.0)
    confidence += min(0.2, pitch_std / 200.0)
    confidence += min(0.2, rms * 2.5)
    confidence = _clamp(confidence, 0.0, HEURISTIC_EMOTION_CONFIDENCE_CAP)

    probs = {
        "happy": 0.0,
        "surprise": 0.0,
        "neutral": 0.0,
        "sad": 0.0,
    }
    probs[emotion] = round(confidence, 4)
    remaining = max(0.0, 1.0 - probs[emotion])
    probs["neutral"] = round(max(probs["neutral"], remaining * 0.5), 4)

    return {
        "predicted_emotion": emotion,
        "confidence": round(confidence, 4),
        "source": "heuristic",
        "emotion_probabilities": probs,
    }
