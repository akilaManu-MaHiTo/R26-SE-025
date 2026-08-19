from dataclasses import dataclass, field
from typing import Iterable, Set


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


NEUTRAL_WEIGHT: float = 0.5

# Soft ceiling for heuristic (non-model) speech-emotion confidence.
HEURISTIC_EMOTION_CONFIDENCE_CAP: float = 0.4

# Refuse to emit video scores when face coverage is too thin to trust.
MIN_FACE_FRAMES: int = 3
MIN_FACE_COVERAGE_RATIO: float = 0.15

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
    output_path: str = "outputs/results.json"
    target_fps: int = 1
    min_face_confidence: float = 0.5
    gaze_threshold: float = 0.04
    emotion_model_path: str = "models/hsemotion_improved.pt"
    engagement_model_path: str = "models/engagement_cnn.pt"
    positive_emotions: Set[str] = field(default_factory=lambda: set(POSITIVE_EMOTIONS))
    neutral_emotions: Set[str] = field(default_factory=lambda: set(NEUTRAL_EMOTIONS))
    surprise_emotions: Set[str] = field(default_factory=lambda: set(SURPRISE_EMOTIONS))
    debug: bool = False
