from collections import Counter
from typing import Dict, List, Optional
import numpy as np
from config import (
    ENGAGEMENT_LEVEL_SCORES,
    NEGATIVE_EMOTIONS,
    NEUTRAL_EMOTIONS,
    POSITIVE_EMOTIONS,
    SURPRISE_EMOTIONS,
    canonical_engagement_label,
    canonical_emotion_label,
)


def smooth_emotions(timeline: List[Dict[str, object]], window: int = 3) -> List[Dict[str, object]]:
    if window <= 0:
        return timeline

    smoothed: List[Dict[str, object]] = []
    for i in range(len(timeline)):
        half = window // 2
        window_slice = timeline[max(0, i - half): min(len(timeline), i + half + 1)]
        emotions = [str(item.get('emotion', '')) for item in window_slice]
        if emotions:
            most_common = Counter(emotions).most_common(1)[0][0]
            # Compute mean confidence over the window, ignoring None
            confidences = [item.get('emotion_confidence') for item in window_slice
                          if item.get('emotion_confidence') is not None]
            mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else None
            updated = dict(timeline[i])
            updated['emotion'] = most_common
            updated['emotion_confidence'] = mean_conf
            smoothed.append(updated)
        else:
            smoothed.append(dict(timeline[i]))
    return smoothed


def compute_confidence_score(timeline: List[Dict[str, object]]) -> float:
    valid_timeline = [
        item for item in timeline
        if canonical_emotion_label(str(item.get('emotion', ''))) not in ('noface', 'no_face')
    ]
    total_frames = len(valid_timeline)
    if total_frames == 0:
        return 0.0

    positive_frames = 0
    surprise_frames = 0
    neutral_frames = 0
    negative_frames = 0

    for item in valid_timeline:
        emotion = canonical_emotion_label(str(item.get('emotion', '')))
        if emotion in POSITIVE_EMOTIONS:
            positive_frames += 1
        elif emotion in SURPRISE_EMOTIONS:
            surprise_frames += 1
        elif emotion in NEUTRAL_EMOTIONS:
            neutral_frames += 1
        elif emotion in NEGATIVE_EMOTIONS:
            negative_frames += 1

    negative_ratio = negative_frames / total_frames
    positive_score = (
        positive_frames * 1.0 +
        surprise_frames * 0.8 +
        neutral_frames * 0.6
    ) / total_frames

    confidence = positive_score
    if negative_ratio > 0.4:
        confidence *= 0.7

    final_score = round(max(0.0, min(100.0, confidence * 100)), 2)
    return final_score


def _weighted_mean(parts: Dict[str, Optional[float]], weights: Dict[str, float], default: float = 0.5) -> float:
    """Average only measured components; renormalize their weights. Empty → default."""
    available = {key: value for key, value in parts.items() if value is not None}
    if not available:
        return default
    weight_sum = sum(weights[key] for key in available)
    if weight_sum <= 0:
        return default
    return sum(weights[key] * float(available[key]) for key in available) / weight_sum


def compute_engagement_score(
    timeline: List[Dict[str, object]],
    gaze_signals: List[Dict | None],
    blinks_per_minute: Optional[float],
) -> float:
    total = len(timeline)
    if total == 0:
        return 0.0

    emotion_map = {
        "happy": 0.9,
        "neutral": 1.0,
        "surprise": 0.6,
        "sad": 0.3,
        "fear": 0.2,
        "angry": 0.2,
        "disgust": 0.1,
        "contempt": 0.2,
    }

    avg_emotion = sum(
        emotion_map.get(canonical_emotion_label(str(t.get("emotion", ""))), 0.5)
        for t in timeline
    ) / total

    valid_gaze = [g for g in gaze_signals if g is not None]
    if valid_gaze:
        gaze_score = sum(1 for g in valid_gaze if g.get("gaze_ok")) / len(valid_gaze)
        yaw_values = [float(g["yaw"]) for g in valid_gaze if g.get("yaw") is not None]
        if yaw_values:
            head_stability = 1.0 - min(1.0, float(np.std(yaw_values)) * 10.0)
        else:
            head_stability = None
    else:
        gaze_score = None
        head_stability = None

    if blinks_per_minute is None:
        blink_term = None
    else:
        blink_penalty = max(0.0, (float(blinks_per_minute) - 25.0) * 0.01)
        blink_term = max(0.0, 1.0 - blink_penalty)

    engagement_scores = []
    for item in timeline:
        score_value = item.get("engagement_model_score")
        try:
            engagement_scores.append(max(0.0, min(1.0, float(score_value))))
            continue
        except (TypeError, ValueError):
            pass

        label = canonical_engagement_label(str(item.get("engagement_label", "")))
        engagement_scores.append(ENGAGEMENT_LEVEL_SCORES.get(label, 0.5))

    engagement_model_score = sum(engagement_scores) / total if engagement_scores else 0.5

    score = _weighted_mean(
        {
            "emotion": avg_emotion,
            "gaze": gaze_score,
            "head": head_stability,
            "blink": blink_term,
            "model": engagement_model_score,
        },
        {
            "emotion": 0.30,
            "gaze": 0.30,
            "head": 0.20,
            "blink": 0.10,
            "model": 0.10,
        },
        default=0.5,
    )
    return round(min(100.0, score * 100), 2)
