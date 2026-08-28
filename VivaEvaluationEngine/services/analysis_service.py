from typing import Dict, List, Optional

from config import (
    AppConfig,
    BLINK_SAMPLE_FPS,
    ENGAGEMENT_LEVEL_SCORES,
    MAX_FRONTAL_YAW_DEGREES,
    MIN_CONSECUTIVE_MULTI_FACE_FRAMES,
    MIN_FACE_COVERAGE_RATIO,
    MIN_FACE_FRAMES,
    MIN_MULTI_FACE_FRAME_RATIO,
    MIN_SECONDARY_FACE_AREA_RATIO,
    NEGATIVE_EMOTIONS,
    NEUTRAL_EMOTIONS,
    POSITIVE_EMOTIONS,
    SURPRISE_EMOTIONS,
    canonical_emotion_label,
    canonical_engagement_label,
)
from services.engagement_detector import EngagementDetector
from services.emotion_detector import EmotionDetector
from services.face_detector import FaceDetector
from services.face_landmarker import iter_landmark_samples, nearest_sample, video_duration_seconds
from services.face_quality import prepare_face_for_emotion
from services.gaze_head_analyser import GazeHeadAnalyser
from services.blink_sampler import blinks_from_samples, unavailable_blinks
from services.engagement_scoring import build_video_features
from services.scoring import compute_confidence_score, compute_engagement_score, smooth_emotions
from services.video_processor import VideoProcessor

_EMOTION_DETECTORS: Dict[str, EmotionDetector] = {}
_ENGAGEMENT_DETECTORS: Dict[str, EngagementDetector] = {}


def _cached_emotion_detector(model_path: str, debug: bool) -> EmotionDetector:
    detector = _EMOTION_DETECTORS.get(model_path)
    if detector is None:
        detector = EmotionDetector(model_path=model_path, debug=debug)
        _EMOTION_DETECTORS[model_path] = detector
    return detector


def _cached_engagement_detector(model_path: str, debug: bool) -> EngagementDetector:
    detector = _ENGAGEMENT_DETECTORS.get(model_path)
    if detector is None:
        detector = EngagementDetector(model_path=model_path, debug=debug)
        _ENGAGEMENT_DETECTORS[model_path] = detector
    return detector


def build_summary(timeline: List[Dict[str, object]]) -> Dict[str, float]:
    # Filter: only frames that have valid=True (non-NoFace)
    valid_timeline = [item for item in timeline if item.get("valid", True) is True]
    total = len(valid_timeline)
    if total == 0:
        return {
            "positive_ratio": 0.0,
            "neutral_ratio": 0.0,
            "negative_ratio": 0.0,
        }

    positive_count = 0
    neutral_count = 0
    negative_count = 0

    for item in valid_timeline:
        emotion = canonical_emotion_label(str(item.get("emotion", "")))
        if emotion in POSITIVE_EMOTIONS or emotion in SURPRISE_EMOTIONS:
            positive_count += 1
        elif emotion in NEUTRAL_EMOTIONS:
            neutral_count += 1
        elif emotion in NEGATIVE_EMOTIONS:
            negative_count += 1

    return {
        "positive_ratio": round(positive_count / total, 4),
        "neutral_ratio": round(neutral_count / total, 4),
        "negative_ratio": round(negative_count / total, 4),
    }


def build_engagement_summary(timeline: List[Dict[str, object]]) -> Dict[str, float]:
    valid_timeline = [item for item in timeline if item.get("valid", True) is True]
    total = len(valid_timeline)
    if total == 0:
        return {
            "very_low_ratio": 0.0,
            "low_ratio": 0.0,
            "high_ratio": 0.0,
            "very_high_ratio": 0.0,
            "average_engagement_score": 0.0,
        }

    counts = {label: 0 for label in ENGAGEMENT_LEVEL_SCORES}
    engagement_scores = []

    for item in valid_timeline:
        label = canonical_engagement_label(str(item.get("engagement_label", "")))
        if label in counts:
            counts[label] += 1

        score_value = item.get("engagement_model_score")
        try:
            engagement_scores.append(float(score_value))
        except (TypeError, ValueError):
            engagement_scores.append(ENGAGEMENT_LEVEL_SCORES.get(label, 0.5))

    return {
        "very_low_ratio": round(counts["very_low"] / total, 4),
        "low_ratio": round(counts["low"] / total, 4),
        "high_ratio": round(counts["high"] / total, 4),
        "very_high_ratio": round(counts["very_high"] / total, 4),
        "average_engagement_score": round(sum(engagement_scores) / total, 4),
    }


def _coverage_is_sufficient(frames_sampled: int, frames_with_face: int) -> bool:
    if frames_with_face < MIN_FACE_FRAMES:
        return False
    if frames_sampled <= 0:
        return False
    return (frames_with_face / frames_sampled) >= MIN_FACE_COVERAGE_RATIO


def _has_significant_second_face(faces: List) -> bool:
    if len(faces) < 2:
        return False
    primary_area = FaceDetector._bbox_area(faces[0])
    secondary_area = FaceDetector._bbox_area(faces[1])
    if primary_area <= 0:
        return False
    return (secondary_area / primary_area) >= MIN_SECONDARY_FACE_AREA_RATIO


def _build_multi_face_summary(
    *,
    frames_sampled: int,
    significant_frames: int,
    max_consecutive: int,
) -> Dict[str, object]:
    ratio = round(significant_frames / frames_sampled, 4) if frames_sampled else 0.0
    passed = frames_sampled <= 0 or (
        ratio < MIN_MULTI_FACE_FRAME_RATIO
        and max_consecutive < MIN_CONSECUTIVE_MULTI_FACE_FRAMES
    )
    return {
        "frames_sampled": frames_sampled,
        "frames_with_significant_second_face": significant_frames,
        "significant_second_face_ratio": ratio,
        "max_consecutive_frames": max_consecutive,
        "min_secondary_area_ratio": MIN_SECONDARY_FACE_AREA_RATIO,
        "min_frame_ratio_threshold": MIN_MULTI_FACE_FRAME_RATIO,
        "min_consecutive_frames_threshold": MIN_CONSECUTIVE_MULTI_FACE_FRAMES,
        "passed": passed,
    }


def analyze_video(config: AppConfig, include_summary: bool = True) -> Dict[str, object]:
    landmark_samples = list(
        iter_landmark_samples(config.video_path, sample_fps=BLINK_SAMPLE_FPS)
    )
    duration_seconds = video_duration_seconds(config.video_path)
    if landmark_samples:
        blink_report = blinks_from_samples(
            landmark_samples,
            sample_fps=BLINK_SAMPLE_FPS,
            duration_seconds=duration_seconds or None,
        )
    elif duration_seconds <= 0:
        blink_report = unavailable_blinks("video_unreadable")
    else:
        blink_report = unavailable_blinks("face_mesh_unavailable")
    blinks_per_minute = blink_report.get("blink_rate_per_minute")

    video_processor = VideoProcessor(target_fps=config.target_fps)
    emotion_detector = _cached_emotion_detector(config.emotion_model_path, config.debug)
    engagement_detector = _cached_engagement_detector(config.engagement_model_path, config.debug)

    timeline: List[Dict[str, object]] = []
    gaze_signals: List[Optional[Dict]] = []
    face_cues: List[Dict[str, object]] = []
    multi_face_frames = 0
    consecutive_multi_face_frames = 0
    max_consecutive_multi_face_frames = 0

    with FaceDetector(
        min_detection_confidence=config.min_face_confidence,
        debug=config.debug,
    ) as face_detector:
        with GazeHeadAnalyser(gaze_threshold=config.gaze_threshold) as gaze_analyser:
            dense_gaze: List[Optional[Dict]] = [
                gaze_analyser.from_landmarks(sample.landmarks) for sample in landmark_samples
            ]
            for frame_data in video_processor.iter_frames(config.video_path):
                nearby = nearest_sample(landmark_samples, frame_data.time_sec)
                gaze = gaze_analyser.from_landmarks(nearby.landmarks if nearby else None)
                gaze_signals.append(gaze)
                mouth_open = None
                talking = False
                if gaze and gaze.get("mouth_open") is not None:
                    mouth_open = float(gaze["mouth_open"])
                    talking = bool(gaze.get("talking"))

                yaw_degrees = nearby.yaw_degrees if nearby else None
                is_frontal = yaw_degrees is None or abs(yaw_degrees) <= MAX_FRONTAL_YAW_DEGREES

                faces = face_detector.detect_faces(frame_data.frame)
                face_crop = (
                    face_detector.crop_face(frame_data.frame, faces[0])
                    if faces and is_frontal
                    else None
                )
                if _has_significant_second_face(faces):
                    multi_face_frames += 1
                    consecutive_multi_face_frames += 1
                    max_consecutive_multi_face_frames = max(
                        max_consecutive_multi_face_frames,
                        consecutive_multi_face_frames,
                    )
                else:
                    consecutive_multi_face_frames = 0
                face_cues.append(
                    {
                        "time": frame_data.time_sec,
                        "valid": face_crop is not None or gaze is not None,
                        "mouth_open": mouth_open,
                        "talking": talking,
                    }
                )
                if face_crop is None:
                    non_frontal = bool(faces) and not is_frontal
                    timeline.append(
                        {
                            "time": frame_data.time_sec,
                            "emotion": "NonFrontal" if non_frontal else "NoFace",
                            "emotion_confidence": 0.0,
                            "engagement_label": "NonFrontal" if non_frontal else "NoFace",
                            "engagement_confidence": 0.0,
                            "engagement_model_score": 0.0,
                            "valid": False,
                            "yaw_degrees": yaw_degrees,
                            "mouth_open": mouth_open,
                            "talking": talking,
                        }
                    )
                    continue

                prepared = prepare_face_for_emotion(face_crop)
                face_for_model = prepared.get("crop")
                if face_for_model is None:
                    timeline.append(
                        {
                            "time": frame_data.time_sec,
                            "emotion": "LowQuality",
                            "emotion_confidence": 0.0,
                            "engagement_label": "LowQuality",
                            "engagement_confidence": 0.0,
                            "engagement_model_score": 0.0,
                            "valid": False,
                            "quality_reject": prepared.get("warning"),
                            "face_quality": prepared.get("after") or prepared.get("before"),
                            "mouth_open": mouth_open,
                            "talking": talking,
                        }
                    )
                    continue

                emotion, emotion_confidence = emotion_detector.predict(face_for_model)
                engagement_label, engagement_confidence, engagement_model_score = engagement_detector.predict(
                    face_for_model
                )
                after = prepared.get("after") or {}
                timeline.append(
                    {
                        "time": frame_data.time_sec,
                        "emotion": emotion,
                        "emotion_confidence": round(emotion_confidence, 4),
                        "engagement_label": engagement_label,
                        "engagement_confidence": round(engagement_confidence, 4),
                        "engagement_model_score": round(engagement_model_score, 4),
                        "valid": True,
                        "face_enhanced": bool(prepared.get("enhanced")),
                        "quality_warning": prepared.get("warning"),
                        "face_quality": {
                            "sharpness": after.get("sharpness"),
                            "brightness": after.get("brightness"),
                            "contrast": after.get("contrast"),
                            "steps": prepared.get("steps") or [],
                        },
                        "yaw_degrees": yaw_degrees,
                        "mouth_open": mouth_open,
                        "talking": talking,
                    }
                )

    frames_sampled = len(timeline)
    frames_with_face = sum(1 for item in timeline if item.get("valid", True) is True)
    frames_rejected_quality = sum(
        1 for item in timeline if str(item.get("emotion", "")).lower() in {"lowquality", "low_quality"}
    )
    frames_rejected_non_frontal = sum(
        1 for item in timeline if str(item.get("emotion", "")).lower() == "nonfrontal"
    )
    frames_enhanced = sum(1 for item in timeline if item.get("face_enhanced"))
    frames_quality_warning = sum(1 for item in timeline if item.get("valid") and item.get("quality_warning"))
    reject_reasons: Dict[str, int] = {}
    for item in timeline:
        reason = item.get("quality_reject") or (item.get("quality_warning") if item.get("valid") else None)
        if reason:
            key = str(reason)
            reject_reasons[key] = reject_reasons.get(key, 0) + 1
    face_coverage_ratio = round(frames_with_face / frames_sampled, 4) if frames_sampled else 0.0
    scores_emitted = _coverage_is_sufficient(frames_sampled, frames_with_face)
    multi_face = _build_multi_face_summary(
        frames_sampled=frames_sampled,
        significant_frames=multi_face_frames,
        max_consecutive=max_consecutive_multi_face_frames,
    )

    paired = list(zip(timeline, gaze_signals))
    clean_pairs = [(t, g) for t, g in paired if t.get("valid", True) is True]
    clean_timeline = [t for t, _g in clean_pairs]
    gaze_for_features = dense_gaze if any(item is not None for item in dense_gaze) else [
        g for _t, g in clean_pairs
    ]

    smoothed_timeline = smooth_emotions(clean_timeline)

    if scores_emitted:
        confidence_score: Optional[float] = compute_confidence_score(smoothed_timeline)
        engagement_score: Optional[float] = compute_engagement_score(
            smoothed_timeline, gaze_for_features, blinks_per_minute
        )
        video_status = "success"
    else:
        confidence_score = None
        engagement_score = None
        video_status = "insufficient_face_coverage"

    coverage = {
        "frames_sampled": frames_sampled,
        "frames_with_face": frames_with_face,
        "face_coverage_ratio": face_coverage_ratio,
        "min_face_frames": MIN_FACE_FRAMES,
        "min_face_coverage_ratio": MIN_FACE_COVERAGE_RATIO,
        "max_frontal_yaw_degrees": MAX_FRONTAL_YAW_DEGREES,
        "blinks_measured": blink_report.get("status") == "available",
        "blinks_per_minute": blinks_per_minute,
        "blink_count": blink_report.get("blink_count"),
        "blink_status": blink_report.get("status"),
        "blink_reason": blink_report.get("reason"),
        "blink_note": blink_report.get("note"),
        "blink_measurement_quality": blink_report.get("measurement_quality"),
        "scores_emitted": scores_emitted,
        "frames_rejected_quality": frames_rejected_quality,
        "frames_rejected_non_frontal": frames_rejected_non_frontal,
        "frames_enhanced": frames_enhanced,
        "frames_quality_warning": frames_quality_warning,
        "quality_reject_reasons": reject_reasons,
        "multi_face": multi_face,
    }

    video_features = build_video_features(
        timeline=smoothed_timeline,
        gaze_signals=gaze_for_features,
        blink=blink_report,
        coverage=coverage,
    )

    response: Dict[str, object] = {
        "timeline": smoothed_timeline,
        # diagnostic_engagement (0–100). Not official Stage-1. See engagement_metrics after attach_assessment.
        "engagement_score": engagement_score,
        "confidence_score": confidence_score,
        "engagement_summary": build_engagement_summary(smoothed_timeline),
        "coverage": coverage,
        "video_status": video_status,
        "face_cues": face_cues,
        "multi_face": multi_face,
        "video_features": video_features,
    }

    if include_summary:
        response["summary"] = build_summary(smoothed_timeline)

    return response
