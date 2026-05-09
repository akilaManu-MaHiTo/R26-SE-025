from collections import Counter
from typing import Dict, List
import numpy as np
from config import (
    NEGATIVE_EMOTIONS,
    NEUTRAL_EMOTIONS,
    POSITIVE_EMOTIONS,
    SURPRISE_EMOTIONS,
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
    valid_timeline = [item for item in timeline if str(item.get('emotion', '')).lower() not in ('noface', 'no_face')]
    total_frames = len(valid_timeline)
    if total_frames == 0:
        return 0.0

    positive_frames = 0
    surprise_frames = 0
    neutral_frames = 0
    negative_frames = 0

    for item in valid_timeline:
        emotion = str(item.get('emotion', '')).strip().lower()
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


def compute_engagement_score(
    timeline: List[Dict[str, object]],
    gaze_signals: List[Dict | None],
    blinks_per_minute: float,
) -> float:
    total = len(timeline)
    if total == 0:
        return 0.0

    emotion_map = {
        "happy": 0.9, "neutral": 1.0, "surprise": 0.6,
        "sad": 0.3, "fear": 0.2, "angry": 0.2, "disgust": 0.1,
    }

    avg_emotion = sum(
        emotion_map.get(str(t.get("emotion","")).lower(), 0.5)
        for t in timeline
    ) / total

    valid_gaze = [g for g in gaze_signals if g is not None]
    gaze_score     = sum(1 for g in valid_gaze if g["gaze_ok"]) / len(valid_gaze) if valid_gaze else 0.5
    head_stability = 1.0 - min(1.0, np.std([g["yaw"] for g in valid_gaze])*10) if valid_gaze else 0.5

    blink_penalty  = max(0.0, (blinks_per_minute - 25) * 0.01)

    lstm_score = 0.5

    score = (
        0.30 * avg_emotion +
        0.30 * gaze_score +
        0.20 * head_stability +
        0.10 * max(0.0, 1.0 - blink_penalty) +
        0.10 * lstm_score
    )
    return round(min(100.0, score * 100), 2)