"""Feature-complete engagement mix (facial guide weights). Not Stage-1 /100."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from config import EMOTION_ENGAGEMENT_MAP, ENGAGEMENT_FEATURE_WEIGHTS, canonical_emotion_label
from services.normalization import blink_rate_score, head_pose_stability_score
from services.score_utils import measured_value, weighted_mean_available
from services.temporal_engagement import TemporalEngagementModel, build_temporal_sequence


def _std(values: List[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    return float(np.std(values))


def aggregate_gaze(gaze_signals: Sequence[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    valid = [g for g in gaze_signals if g is not None]
    if not valid:
        return {
            "status": "unavailable",
            "gaze_on_camera_ratio": None,
            "gaze_x_mean": None,
            "gaze_y_mean": None,
            "frames_with_gaze": 0,
            "direction_counts": {},
            "validated": False,
            "validation_reason": "no_looking_away_recording",
        }
    on_camera = sum(1 for g in valid if g.get("gaze_ok"))
    xs = [float(g["gaze_x"]) for g in valid if g.get("gaze_x") is not None]
    ys = [float(g["gaze_y"]) for g in valid if g.get("gaze_y") is not None]
    directions: Dict[str, int] = {}
    for g in valid:
        key = str(g.get("gaze_direction") or "unknown")
        directions[key] = directions.get(key, 0) + 1
    return {
        "status": "available",
        "gaze_on_camera_ratio": round(on_camera / len(valid), 4),
        "gaze_x_mean": round(sum(xs) / len(xs), 4) if xs else None,
        "gaze_y_mean": round(sum(ys) / len(ys), 4) if ys else None,
        "frames_with_gaze": len(valid),
        "direction_counts": directions,
        "validated": False,
        "validation_reason": "no_looking_away_recording",
    }


def _axis_raw_proxy(signal: Dict[str, Any], axis: str) -> Optional[float]:
    """Raw landmark-distance proxy, conflated with camera distance. Kept
    only for diagnostic comparison — stability is no longer computed from
    this. Falls back to legacy yaw/pitch/roll keys from older stored docs."""
    value = signal.get(f"{axis}_proxy")
    if value is None:
        value = signal.get(axis)
    if value is None:
        return None
    return float(value)


def _axis_normalized(signal: Dict[str, Any], axis: str) -> Optional[float]:
    """Inter-ocular-distance-normalized proxy — decoupled from camera
    distance. This is what head-pose stability is actually computed from.
    Falls back to the raw proxy for older stored docs that predate it."""
    value = signal.get(f"{axis}_normalized")
    if value is None:
        value = _axis_raw_proxy(signal, axis)
    return value


def aggregate_head_pose(gaze_signals: Sequence[Optional[Dict[str, Any]]]) -> Dict[str, Any]:
    valid = [g for g in gaze_signals if g is not None]
    yaws_raw = [v for v in (_axis_raw_proxy(g, "yaw") for g in valid) if v is not None]
    pitches_raw = [v for v in (_axis_raw_proxy(g, "pitch") for g in valid) if v is not None]
    rolls_raw = [v for v in (_axis_raw_proxy(g, "roll") for g in valid) if v is not None]
    yaws = [v for v in (_axis_normalized(g, "yaw") for g in valid) if v is not None]
    pitches = [v for v in (_axis_normalized(g, "pitch") for g in valid) if v is not None]
    rolls = [v for v in (_axis_normalized(g, "roll") for g in valid) if v is not None]
    if not yaws and not pitches and not rolls:
        return {
            "status": "unavailable",
            "yaw_proxy_std": None,
            "pitch_proxy_std": None,
            "roll_proxy_std": None,
            "yaw_normalized_std": None,
            "pitch_normalized_std": None,
            "roll_normalized_std": None,
            "yaw_std": None,
            "pitch_std": None,
            "roll_std": None,
            "stability_score": None,
            "head_stability": None,
            "unit": "normalized_landmark_distance",
            "not_euler_degrees": True,
            "validated": False,
            "validation_reason": "no_turn_tilt_recording",
        }
    yaw_std_raw = _std(yaws_raw)
    pitch_std_raw = _std(pitches_raw)
    roll_std_raw = _std(rolls_raw)
    yaw_std = _std(yaws)
    pitch_std = _std(pitches)
    roll_std = _std(rolls)
    stability = head_pose_stability_score(yaw_std, pitch_std, roll_std)
    return {
        "status": "available",
        # Raw proxy std — diagnostic only, conflated with camera distance.
        "yaw_proxy_std": None if yaw_std_raw is None else round(yaw_std_raw, 4),
        "pitch_proxy_std": None if pitch_std_raw is None else round(pitch_std_raw, 4),
        "roll_proxy_std": None if roll_std_raw is None else round(roll_std_raw, 4),
        # Inter-ocular-normalized std — what stability_score is computed from.
        "yaw_normalized_std": None if yaw_std is None else round(yaw_std, 4),
        "pitch_normalized_std": None if pitch_std is None else round(pitch_std, 4),
        "roll_normalized_std": None if roll_std is None else round(roll_std, 4),
        "yaw_std": None if yaw_std is None else round(yaw_std, 4),
        "pitch_std": None if pitch_std is None else round(pitch_std, 4),
        "roll_std": None if roll_std is None else round(roll_std, 4),
        "stability_score": stability,
        "head_stability": stability,
        "unit": "normalized_landmark_distance",
        "not_euler_degrees": True,
        "validated": False,
        "validation_reason": "no_turn_tilt_recording",
    }


def aggregate_emotion(timeline: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    labels: List[str] = []
    confidences: List[float] = []
    for item in timeline:
        if item.get("valid") is False:
            continue
        label = canonical_emotion_label(str(item.get("emotion", "")))
        if label in {"noface", "no_face", "lowquality", "low_quality", ""}:
            continue
        labels.append(label)
        try:
            confidences.append(float(item.get("emotion_confidence")))
        except (TypeError, ValueError):
            pass
    if not labels:
        return {
            "status": "unavailable",
            "score": None,
            "mean_confidence": None,
            "frame_count": 0,
        }
    mapped = [EMOTION_ENGAGEMENT_MAP.get(label, 0.5) for label in labels]
    return {
        "status": "available",
        "score": round(sum(mapped) / len(mapped), 4),
        "mean_confidence": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "frame_count": len(labels),
    }


def compute_engagement_score(features: Dict[str, Any]) -> Dict[str, Any]:
    """Feature-complete engagement mix. Not Stage-1 CNN engagement and not UI diagnostic_engagement."""
    video = features.get("video_features") or features
    emotion = video.get("emotion") or {}
    gaze = video.get("gaze") or {}
    head = video.get("head_pose") or {}
    blink = video.get("blink") or {}
    temporal = video.get("temporal_engagement") or {}

    emotion_s = emotion.get("score") if emotion.get("status") == "available" else None
    gaze_s = gaze.get("gaze_on_camera_ratio") if gaze.get("status") == "available" else None
    head_s = head.get("stability_score")
    if head_s is None:
        head_s = head.get("head_stability")
    if head.get("status") != "available":
        head_s = None
    blink_s = blink_rate_score(blink.get("blink_rate_per_minute")) if blink.get("status") == "available" else None
    temporal_s = temporal.get("score") if temporal.get("status") == "ready" else None

    score, applied = weighted_mean_available(
        {
            "emotion": emotion_s,
            "gaze": gaze_s,
            "head": head_s,
            "blink": blink_s,
            "temporal": temporal_s,
        },
        ENGAGEMENT_FEATURE_WEIGHTS,
    )
    warnings: List[str] = []
    if blink.get("note"):
        warnings.append(str(blink["note"]))
    if temporal.get("status") != "ready":
        warnings.append("Temporal CNN-LSTM unavailable (no trained checkpoint).")

    components = {
        "emotion": measured_value(
            raw=emotion.get("score"),
            normalized=emotion_s,
            available=emotion_s is not None,
            method="emotion_label_map",
            status=str(emotion.get("status") or "unavailable"),
        ),
        "gaze": measured_value(
            raw=gaze.get("gaze_on_camera_ratio"),
            normalized=gaze_s,
            available=gaze_s is not None,
            method="gaze_on_camera_ratio",
            status=str(gaze.get("status") or "unavailable"),
        ),
        "head": measured_value(
            raw={
                "yaw_proxy_std": head.get("yaw_proxy_std", head.get("yaw_std")),
                "pitch_proxy_std": head.get("pitch_proxy_std", head.get("pitch_std")),
                "roll_proxy_std": head.get("roll_proxy_std", head.get("roll_std")),
            },
            normalized=head_s,
            available=head_s is not None,
            method="1/(1+(std/scale)^2) mean of yaw/pitch/roll landmark proxies (not degrees)",
            status=str(head.get("status") or "unavailable"),
        ),
        "blink": measured_value(
            raw=blink.get("blink_rate_per_minute"),
            normalized=blink_s,
            available=blink_s is not None,
            method="1 - max(0, bpm-25)*0.01",
            status=str(blink.get("status") or "unavailable"),
        ),
        "temporal": measured_value(
            raw=None,
            normalized=temporal_s,
            available=temporal_s is not None,
            method="cnn_lstm_checkpoint",
            status=str(temporal.get("status") or "unavailable"),
        ),
    }

    available = score is not None
    return {
        "metric_id": "feature_complete_engagement",
        "score": None if score is None else round(float(score), 4),
        "available": available,
        "status": "available" if available else "unavailable",
        "components": components,
        "family_weights_applied": applied,
        "warnings": warnings,
    }


def build_video_features(
    *,
    timeline: Sequence[Dict[str, Any]],
    gaze_signals: Sequence[Optional[Dict[str, Any]]],
    blink: Dict[str, Any],
    coverage: Dict[str, Any],
    temporal_model: Optional[TemporalEngagementModel] = None,
) -> Dict[str, Any]:
    model = temporal_model or TemporalEngagementModel()
    sequence = build_temporal_sequence(timeline, gaze_signals)
    temporal_score = model.predict(sequence)
    temporal = model.describe()
    if temporal_score is not None:
        temporal["score"] = round(float(temporal_score), 4)
        temporal["status"] = "ready"

    face_available = int(coverage.get("frames_with_face") or 0) > 0
    return {
        "face_available": face_available,
        "valid_face_ratio": coverage.get("face_coverage_ratio"),
        "emotion": aggregate_emotion(timeline),
        "gaze": aggregate_gaze(gaze_signals),
        "head_pose": aggregate_head_pose(gaze_signals),
        "blink": blink,
        "temporal_engagement": temporal,
    }
