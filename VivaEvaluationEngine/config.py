from dataclasses import dataclass, field
from typing import Set


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
    "surprised": "surprise",
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


def canonical_emotion_label(emotion: str) -> str:
    normalized = str(emotion).strip().lower()
    return EMOTION_ALIASES.get(normalized, normalized)


def canonical_engagement_label(label: str) -> str:
    normalized = str(label).strip().lower().replace("-", " ")
    normalized = " ".join(normalized.split())
    normalized = normalized.replace(" ", "_")
    return ENGAGEMENT_ALIASES.get(normalized.replace("_", " "), normalized)


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
