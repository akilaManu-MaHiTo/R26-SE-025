from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Set

ENGINE_ROOT = Path(__file__).resolve().parent


POSITIVE_EMOTIONS: Set[str] = {"happy"}
NEUTRAL_EMOTIONS: Set[str] = {"neutral"}
SURPRISE_EMOTIONS: Set[str] = {"surprise"}
NEGATIVE_EMOTIONS: Set[str] = {
    "fear",
    "sad",
    "angry",
    "disgust",
    "contempt",
}

# Map model-specific/raw labels to canonical labels used by scoring.
EMOTION_ALIASES = {
    "happiness": "happy",
    "hap": "happy",
    "joy": "happy",
    "surprised": "surprise",
    "surprise": "surprise",
    "anger": "angry",
    "ang": "angry",
    "angry": "angry",
    "fearful": "fear",
    "fear": "fear",
    "sadness": "sad",
    "sad": "sad",
    "neu": "neutral",
    "neutral": "neutral",
    "calm": "neutral",  # RAVDESS-style SER often emits calm ≈ low-arousal neutral
    "disgust": "disgust",
    "disgusted": "disgust",
    "contempt": "contempt",
}

ENGAGEMENT_ALIASES = {
    "very low": "very_low",
    "very-low": "very_low",
    "verylow": "very_low",
    "very high": "very_high",
    "very-high": "very_high",
    "veryhigh": "very_high",
}

ENGAGEMENT_LEVEL_SCORES = {
    "very_low": 0.15,
    "low": 0.40,
    "high": 0.75,
    "very_high": 0.95,
}


# Soft ceiling for heuristic (non-model) speech-emotion confidence.
HEURISTIC_EMOTION_CONFIDENCE_CAP: float = 0.4

# Refuse to emit video scores when face coverage is too thin to trust.
MIN_FACE_FRAMES: int = 3
MIN_FACE_COVERAGE_RATIO: float = 0.15

# A frame only counts toward face coverage if the head is roughly frontal —
# MediaPipe's face detector fires on side profiles too, so coverage alone
# can't tell a profile shot from a genuine on-camera face. Threshold is the
# real Euler yaw (degrees) from FaceLandmarker's facial transformation matrix,
# calibrated against sample footage: frontal/talking clips stayed under ~18°,
# a deliberate "looking away" clip sat at 35-57°. 30° sits in the gap.
MAX_FRONTAL_YAW_DEGREES: float = 30.0

# Multi-face gate: viva expects one student on camera. Ignore tiny partial faces
# (second face area < this fraction of the largest). Fail when a significant
# second face appears often enough or for several consecutive sampled frames.
MIN_SECONDARY_FACE_AREA_RATIO: float = 0.20
MIN_MULTI_FACE_FRAME_RATIO: float = 0.12
MIN_CONSECUTIVE_MULTI_FACE_FRAMES: int = 3

# --- Feature-complete baseline (does not replace Stage-1 /100) ---
# Iris offset sum below this → gaze_on_camera. Used only from GazeHeadAnalyser.
GAZE_ON_CAMERA_THRESHOLD: float = 0.04
GAZE_DIRECTION_DEADZONE: float = 0.015

# Landmark-proxy head-pose std scales for 1/(1+(std/S)^2) → [0,1].
# These are FaceMesh normalized distances, not Euler-angle degrees, and are
# now applied to the inter-ocular-distance-normalized proxies (see
# gaze_head_analyser.py's yaw/pitch/roll_normalized) rather than the raw
# ones, so they decouple from how far the subject sits from the camera.
# Rescaled ~6.3x from the old raw-proxy constants — the empirical ratio
# between normalized and raw proxy magnitude measured against
# videos/only boy talking.mp4 — since no ground-truth head-pose dataset
# exists to calibrate these against directly (see validated: false below).
HEAD_POSE_YAW_STD_SCALE: float = 0.25
HEAD_POSE_PITCH_STD_SCALE: float = 0.25
HEAD_POSE_ROLL_STD_SCALE: float = 0.19

# EAR blink sampler. Rate above this is flagged (neutral wording only).
# 0.25 is the classic Soukupova pixel-EAR open/close split. MediaPipe 6-point
# EAR on viva webcams sits lower (open-eye median ≈ 0.22, blink troughs ≈ 0.03
# on only boy talking.mp4). 0.15 is below that open-eye mass and above troughs.
BLINK_EAR_THRESHOLD: float = 0.15
# Closed if EAR < max(absolute, relative * session-median). High-EAR cameras
# (open median ≈ 0.55) never stay below 0.15 for two samples; relative catch
# is required. Isolated deep troughs still count (10 fps misses ~100 ms blinks).
BLINK_RELATIVE_CLOSE_RATIO: float = 0.55
BLINK_ISOLATED_MIN_DROP: float = 0.04
BLINK_MIN_CONSECUTIVE: int = 2
BLINK_SAMPLE_FPS: int = 10
BLINK_MIN_VALID_EYE_FRAMES: int = 8
BLINK_MIN_DURATION_SECONDS: float = 3.0
BLINK_ELEVATED_PER_MINUTE: float = 25.0
BLINK_PENALTY_PER_BPM_OVER: float = 0.01

# Facial-guide engagement mix. Missing components are omitted and renormalized.
ENGAGEMENT_FEATURE_WEIGHTS = {
    "emotion": 0.30,
    "gaze": 0.30,
    "head": 0.20,
    "blink": 0.10,
    "temporal": 0.10,
}

# Engagement contribution of facial emotion labels (not psychological diagnosis).
EMOTION_ENGAGEMENT_MAP = {
    "neutral": 1.0,
    "happy": 0.9,
    "surprise": 0.6,
    "sad": 0.3,
    "fear": 0.2,
    "angry": 0.2,
    "disgust": 0.1,
    "contempt": 0.2,
}

SPEECH_RATE_OPTIMAL_WPM = (120.0, 160.0)
PAUSE_SHORT_SECONDS: float = 0.5
PAUSE_LONG_SECONDS: float = 2.0

# Diagnostic transcript evidence only — does not change Stage-1 or FC scores.
# <8 words cannot populate hedge/filler scales (8 / 12). <40 words or <15s
# is shorter than a few sentences at 120–160 WPM, so pause/hedge zeros are
# weak evidence rather than "perfect delivery".
TRANSCRIPT_COVERAGE_INSUFFICIENT_WORDS: int = 8
TRANSCRIPT_COVERAGE_LIMITED_WORDS: int = 40
TRANSCRIPT_COVERAGE_LIMITED_SECONDS: float = 15.0

# Pitch stability: 1 - clamp(std_hz / this). Same bound as Stage-1 audio family.
PITCH_STD_SCALE_HZ: float = 120.0

TEMPORAL_ENGAGEMENT_CHECKPOINT: str = "models/temporal_engagement.pt"

# Face-crop quality: enhance webcam frames, then warn (do not skip) if still
# dark/blurry. Skip only empty or tiny crops — a single-student camera has no
# other face to fall back on. No generative deblur (GFPGAN/CodeFormer).
FACE_QUALITY_PROBE_SIZE: int = 96
FACE_MIN_SIDE_PX: int = 48
FACE_MIN_SHARPNESS: float = 28.0
FACE_MIN_BRIGHTNESS: float = 22.0
FACE_MAX_BRIGHTNESS: float = 245.0
FACE_MIN_CONTRAST: float = 10.0
FACE_CLAHE_CLIP: float = 2.0
FACE_DENOISE_H: float = 5.0
FACE_UNSHARP_AMOUNT: float = 0.35
FACE_UNSHARP_IF_BELOW: float = 80.0
FACE_GAMMA_TARGET: float = 70.0

SCORING_EMOTION_BUCKETS: Set[str] = (
    POSITIVE_EMOTIONS | NEUTRAL_EMOTIONS | SURPRISE_EMOTIONS | NEGATIVE_EMOTIONS
)


def canonical_emotion_label(emotion: str) -> str:
    normalized = str(emotion).strip().lower()
    return EMOTION_ALIASES.get(normalized, normalized)


def canonical_engagement_label(label: str) -> str:
    normalized = str(label).strip().lower().replace("-", " ")
    normalized = " ".join(normalized.split())
    normalized = normalized.replace(" ", "_")
    return ENGAGEMENT_ALIASES.get(normalized.replace("_", " "), normalized)


def assert_emotion_classes_covered(class_names: Iterable[str]) -> None:
    """Fail fast if a model class cannot map into exactly one scoring bucket."""
    uncovered = []
    for name in class_names:
        canonical = canonical_emotion_label(str(name))
        if canonical in {"noface", "no_face", "lowquality", "low_quality", ""}:
            continue
        if canonical not in SCORING_EMOTION_BUCKETS:
            uncovered.append(f"{name}->{canonical}")
    if uncovered:
        raise RuntimeError(
            "Emotion classes missing from scoring buckets: " + ", ".join(uncovered)
        )


@dataclass
class AppConfig:
    video_path: str
    # Resolved against this file's own directory, not the caller's CWD, so
    # these defaults work whether the engine is run as a script from inside
    # this directory or imported as a package from anywhere else.
    output_path: str = str(ENGINE_ROOT / "outputs" / "results.json")
    target_fps: int = 1
    min_face_confidence: float = 0.5
    gaze_threshold: float = GAZE_ON_CAMERA_THRESHOLD
    emotion_model_path: str = str(ENGINE_ROOT / "models" / "hsemotion_improved.pt")
    engagement_model_path: str = str(ENGINE_ROOT / "models" / "engagement_cnn.pt")
    debug: bool = False
