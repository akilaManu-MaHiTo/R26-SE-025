"""Bounded [0,1] maps for feature-complete scoring. Formulas live here, not in callers."""
from __future__ import annotations

from typing import Optional

from config import (
    BLINK_ELEVATED_PER_MINUTE,
    BLINK_PENALTY_PER_BPM_OVER,
    HEAD_POSE_PITCH_STD_SCALE,
    HEAD_POSE_ROLL_STD_SCALE,
    HEAD_POSE_YAW_STD_SCALE,
    PITCH_STD_SCALE_HZ,
    SPEECH_RATE_OPTIMAL_WPM,
)
from services.score_utils import clamp


def pitch_stability_score(pitch_std_hz: Optional[float]) -> Optional[float]:
    """1 - clamp(std_hz / 120). Same bound as Stage-1 audio_acoustics family."""
    if pitch_std_hz is None:
        return None
    return clamp(1.0 - (float(pitch_std_hz) / PITCH_STD_SCALE_HZ))


def head_axis_stability(std_value: Optional[float], scale: float) -> Optional[float]:
    """1 / (1 + (std/scale)^2) — bounded, monotone decreasing, not 1-raw_std."""
    if std_value is None or scale <= 0:
        return None
    ratio = float(std_value) / float(scale)
    return clamp(1.0 / (1.0 + ratio * ratio))


def head_pose_stability_score(
    yaw_std: Optional[float],
    pitch_std: Optional[float],
    roll_std: Optional[float],
) -> Optional[float]:
    axes = [
        head_axis_stability(yaw_std, HEAD_POSE_YAW_STD_SCALE),
        head_axis_stability(pitch_std, HEAD_POSE_PITCH_STD_SCALE),
        head_axis_stability(roll_std, HEAD_POSE_ROLL_STD_SCALE),
    ]
    present = [value for value in axes if value is not None]
    if not present:
        return None
    return clamp(sum(present) / len(present))


def blink_rate_score(blinks_per_minute: Optional[float]) -> Optional[float]:
    """1.0 up to the elevated threshold, then linear penalty. Not a clinical claim."""
    if blinks_per_minute is None:
        return None
    extra = max(0.0, float(blinks_per_minute) - BLINK_ELEVATED_PER_MINUTE)
    return clamp(1.0 - extra * BLINK_PENALTY_PER_BPM_OVER)


def speech_rate_score(wpm: Optional[float], *, word_count: Optional[int] = None) -> Optional[float]:
    """120–160 WPM → 1.0. Empty/silent transcripts are unavailable, not 'slow'."""
    if word_count is not None and int(word_count) <= 0:
        return None
    if wpm is None:
        return None
    low, high = SPEECH_RATE_OPTIMAL_WPM
    rate = float(wpm)
    if rate < 0:
        return None
    if low <= rate <= high:
        return 1.0
    if rate < low:
        return clamp(rate / low) if low > 0 else None
    return clamp(1.0 - (rate - high) / high) if high > 0 else None


def jitter_shimmer_quality(raw: Optional[float], good: float, poor: float) -> Optional[float]:
    if raw is None:
        return None
    if poor == good:
        return 1.0 if raw <= good else 0.0
    return clamp((poor - float(raw)) / (poor - good))


def energy_consistency_score(rms_mean: Optional[float], rms_std: Optional[float]) -> Optional[float]:
    """Lower coefficient of variation → more consistent energy. Not 'louder is better'."""
    if rms_mean is None or rms_std is None:
        return None
    mean = float(rms_mean)
    if mean <= 1e-8:
        return None
    cv = float(rms_std) / mean
    return clamp(1.0 / (1.0 + cv))
