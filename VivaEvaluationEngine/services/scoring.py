import logging
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

logger = logging.getLogger(__name__)


def _frame_time(item: Dict[str, object], fallback: float) -> float:
    try:
        return float(item.get('time'))
    except (TypeError, ValueError):
        return fallback


def smooth_emotions(timeline: List[Dict[str, object]], window: int = 3) -> List[Dict[str, object]]:
    """Majority-vote smoothing over a *time-local* neighborhood.

    Invalid (NoFace/LowQuality) frames are dropped before this runs, so
    array neighbours can be seconds or minutes apart in real time. Walking
    outward stops as soon as the gap between consecutive timestamps exceeds
    ~2x the session's typical frame spacing, so a smoothing window never
    bridges across a dropped stretch of video.
    """
    if window <= 0 or not timeline:
        return timeline

    half = window // 2
    times = [_frame_time(item, float(idx)) for idx, item in enumerate(timeline)]
    gaps = [times[i + 1] - times[i] for i in range(len(times) - 1) if times[i + 1] > times[i]]
    median_gap = sorted(gaps)[len(gaps) // 2] if gaps else 1.0
    max_gap = max(median_gap * 2.0, 1e-6)

    smoothed: List[Dict[str, object]] = []
    for i in range(len(timeline)):
        indices = {i}
        j = i - 1
        while j >= max(0, i - half) and (times[j + 1] - times[j]) <= max_gap:
            indices.add(j)
            j -= 1
        j = i + 1
        while j <= min(len(timeline) - 1, i + half) and (times[j] - times[j - 1]) <= max_gap:
            indices.add(j)
            j += 1
        window_slice = [timeline[k] for k in sorted(indices)]

        emotions = [str(item.get('emotion', '')) for item in window_slice]
        most_common = Counter(emotions).most_common(1)[0][0]
        # Confidence is only meaningful for the label that actually won —
        # averaging across the whole window would mix in other emotions' scores.
        confidences = [
            item.get('emotion_confidence') for item in window_slice
            if str(item.get('emotion', '')) == most_common and item.get('emotion_confidence') is not None
        ]
        mean_conf = round(sum(confidences) / len(confidences), 4) if confidences else timeline[i].get('emotion_confidence')

        updated = dict(timeline[i])
        updated['emotion'] = most_common
        updated['emotion_confidence'] = mean_conf
        smoothed.append(updated)
    return smoothed


def compute_confidence_score(timeline: List[Dict[str, object]]) -> float:
    """Each frame's vote is scaled by the model's own emotion_confidence, so a
    label the model was barely sure of (e.g. 0.26) pulls the score toward
    zero instead of counting as a full vote equal to a 0.99-confidence frame."""
    valid_timeline = [
        item for item in timeline
        if canonical_emotion_label(str(item.get('emotion', ''))) not in ('noface', 'no_face', 'lowquality', 'low_quality')
    ]
    total_frames = len(valid_timeline)
    if total_frames == 0:
        return 0.0

    positive_weight = 0.0
    surprise_weight = 0.0
    neutral_weight = 0.0
    negative_weight = 0.0

    for item in valid_timeline:
        emotion = canonical_emotion_label(str(item.get('emotion', '')))
        try:
            weight = max(0.0, min(1.0, float(item.get('emotion_confidence', 1.0))))
        except (TypeError, ValueError):
            weight = 1.0
        if emotion in POSITIVE_EMOTIONS:
            positive_weight += weight
        elif emotion in SURPRISE_EMOTIONS:
            surprise_weight += weight
        elif emotion in NEUTRAL_EMOTIONS:
            neutral_weight += weight
        elif emotion in NEGATIVE_EMOTIONS:
            negative_weight += weight

    negative_ratio = negative_weight / total_frames
    positive_score = (
        positive_weight * 1.0 +
        surprise_weight * 0.8 +
        neutral_weight * 0.6
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
    """UI/diagnostic engagement 0–100.

    This is diagnostic_engagement (result.engagement_score). It is NOT
    stage1_cnn_engagement and NOT feature_complete_engagement. Official /100
    uses average_engagement_score only.
    """
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

    def _engagement_weight(raw_emotion: str) -> float:
        label = canonical_emotion_label(raw_emotion)
        if label in emotion_map:
            return emotion_map[label]
        logger.warning("Unmapped emotion label reached engagement scoring: %r -> %r", raw_emotion, label)
        return 0.5

    avg_emotion = sum(_engagement_weight(str(t.get("emotion", ""))) for t in timeline) / total

    valid_gaze = [g for g in gaze_signals if g is not None]
    if valid_gaze:
        gaze_score = sum(1 for g in valid_gaze if g.get("gaze_ok")) / len(valid_gaze)
        yaw_values = []
        for g in valid_gaze:
            # Prefer the inter-ocular-distance-normalized proxy so a subject
            # moving closer/further from the camera isn't read as head
            # movement; fall back to the raw proxy for older stored data.
            proxy = g.get("yaw_normalized")
            if proxy is None:
                proxy = g.get("yaw_proxy")
            if proxy is None:
                proxy = g.get("yaw")
            if proxy is not None:
                yaw_values.append(float(proxy))
        if yaw_values:
            # 1.6 ≈ 10 / 6.3, rescaled by the same empirical ratio used for
            # HEAD_POSE_YAW_STD_SCALE in config.py, to keep this diagnostic
            # score in a comparable range to its pre-normalization behavior.
            head_stability = 1.0 - min(1.0, float(np.std(yaw_values)) * 1.6)
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
