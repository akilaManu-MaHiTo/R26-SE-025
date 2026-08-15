from __future__ import annotations

from typing import Any, Dict, Optional

import librosa
import numpy as np


SR = 16000


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_pitch_stats(y: np.ndarray, sr: int) -> Dict[str, float]:
    try:
        f0 = librosa.yin(y, fmin=65, fmax=400, sr=sr)
        f0 = np.asarray(f0, dtype=float)
        valid = f0[np.isfinite(f0) & (f0 > 0)]
        if valid.size == 0:
            return {"pitch_mean": 0.0, "pitch_min": 0.0, "pitch_max": 0.0, "pitch_std": 0.0}
        return {
            "pitch_mean": float(np.mean(valid)),
            "pitch_min": float(np.min(valid)),
            "pitch_max": float(np.max(valid)),
            "pitch_std": float(np.std(valid)),
        }
    except Exception:
        return {"pitch_mean": 0.0, "pitch_min": 0.0, "pitch_max": 0.0, "pitch_std": 0.0}


def _safe_voice_quality(audio_path: str) -> Dict[str, Optional[float]]:
    """Praat/parselmouth voice quality. Unavailability → None, never fake zeros."""
    try:
        import parselmouth
        from parselmouth.praat import call

        snd = parselmouth.Sound(audio_path)
        point_process = call(snd, "To PointProcess (periodic, cc)", 75, 500)

        jitter_local = _safe_float(call(point_process, "Get jitter (local)", 0, 0, 0.0001, 0.02, 1.3))
        shimmer_local = _safe_float(call([snd, point_process], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6))

        harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
        hnr_mean = _safe_float(call(harmonicity, "Get mean", 0, 0))

        return {
            "jitter_local": max(0.0, jitter_local),
            "shimmer_local": max(0.0, shimmer_local),
            "hnr_mean": max(0.0, hnr_mean),
            "voice_quality_measured": 1.0,
        }
    except Exception:
        return {
            "jitter_local": None,
            "shimmer_local": None,
            "hnr_mean": None,
            "voice_quality_measured": 0.0,
        }


def extract_acoustic_features(audio_path: str) -> Dict[str, Any]:
    y, sr = librosa.load(audio_path, sr=SR, mono=True)

    duration = librosa.get_duration(y=y, sr=sr)
    rms = librosa.feature.rms(y=y)

    try:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        tempo_value = float(np.squeeze(tempo))
    except Exception:
        tempo_value = 0.0

    pitch = _safe_pitch_stats(y, sr)
    voice_quality = _safe_voice_quality(audio_path)

    return {
        "duration_seconds": float(duration),
        "tempo": max(0.0, tempo_value),
        "rms_mean": float(np.mean(rms)) if rms.size else 0.0,
        "pitch_mean": pitch["pitch_mean"],
        "pitch_min": pitch["pitch_min"],
        "pitch_max": pitch["pitch_max"],
        "pitch_std": pitch["pitch_std"],
        "jitter_local": voice_quality["jitter_local"],
        "shimmer_local": voice_quality["shimmer_local"],
        "hnr_mean": voice_quality["hnr_mean"],
        "voice_quality_measured": bool(voice_quality.get("voice_quality_measured")),
    }
