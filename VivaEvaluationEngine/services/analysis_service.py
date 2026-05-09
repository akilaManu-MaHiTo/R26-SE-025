from typing import Dict, List

from config import AppConfig, NEGATIVE_EMOTIONS, NEUTRAL_EMOTIONS, POSITIVE_EMOTIONS, SURPRISE_EMOTIONS, canonical_emotion_label
from services.emotion_detector import EmotionDetector
from services.face_detector import FaceDetector
from services.gaze_head_analyser import GazeHeadAnalyser
from services.blink_sampler import BlinkSampler
from services.scoring import compute_confidence_score, compute_engagement_score, smooth_emotions
from services.video_processor import VideoProcessor


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
        emotion = str(item.get("emotion", "")).strip().lower()
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


def analyze_video(config: AppConfig, include_summary: bool = True) -> Dict[str, object]:
    blinks_per_minute = BlinkSampler().count_blinks(config.video_path)

    video_processor = VideoProcessor(target_fps=config.target_fps)
    face_detector = FaceDetector(
        min_detection_confidence=config.min_face_confidence,
        debug=config.debug,
    )
    emotion_detector = EmotionDetector(
        model_path=config.emotion_model_path,
        debug=config.debug,
    )

    timeline: List[Dict[str, object]] = []
    gaze_signals: List[Dict | None] = []

    with GazeHeadAnalyser(gaze_threshold=config.gaze_threshold) as gaze_analyser:
        for frame_data in video_processor.iter_frames(config.video_path):
            gaze = gaze_analyser.analyse(frame_data.frame)
            gaze_signals.append(gaze)

            face_crop = face_detector.detect_and_crop(frame_data.frame)
            if face_crop is None:
                timeline.append(
                    {
                        "time": frame_data.time_sec,
                        "emotion": "NoFace",
                        "emotion_confidence": 0.0,
                        "valid": False,
                    }
                )
                continue

            emotion, emotion_confidence = emotion_detector.predict(face_crop)
            timeline.append(
                {
                    "time": frame_data.time_sec,
                    "emotion": emotion,
                    "emotion_confidence": round(emotion_confidence, 4),
                    "valid": True,
                }
            )

    paired = list(zip(timeline, gaze_signals))
    clean_pairs = [(t, g) for t, g in paired if t.get("valid", True) is True]
    clean_timeline = [t for t, g in clean_pairs]
    clean_gaze     = [g for t, g in clean_pairs]

    smoothed_timeline = smooth_emotions(clean_timeline)
    confidence_score = compute_confidence_score(smoothed_timeline)
    engagement_score = compute_engagement_score(smoothed_timeline, clean_gaze, blinks_per_minute)

    response: Dict[str, object] = {
        "timeline": smoothed_timeline,
        "confidence_score": confidence_score,
        "engagement_score": engagement_score,
    }

    if include_summary:
        response["summary"] = build_summary(smoothed_timeline)

    return response
