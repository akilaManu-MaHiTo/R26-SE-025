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


NEUTRAL_WEIGHT: float = 0.5


def canonical_emotion_label(emotion: str) -> str:
    normalized = str(emotion).strip().lower()
    return EMOTION_ALIASES.get(normalized, normalized)


@dataclass
class AppConfig:
    video_path: str
    output_path: str = "outputs/results.json"
    target_fps: int = 1
    min_face_confidence: float = 0.5
    gaze_threshold: float = 0.04
    emotion_model_path: str = "models/hsemotion_improved.pt"
    positive_emotions: Set[str] = field(default_factory=lambda: set(POSITIVE_EMOTIONS))
    neutral_emotions: Set[str] = field(default_factory=lambda: set(NEUTRAL_EMOTIONS))
    surprise_emotions: Set[str] = field(default_factory=lambda: set(SURPRISE_EMOTIONS))
    debug: bool = False
