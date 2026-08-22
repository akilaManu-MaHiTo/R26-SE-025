"""Shared MediaPipe Tasks FaceLandmarker (478-pt mesh including iris).

MediaPipe 0.10.x ships Tasks only — mp.solutions.face_mesh is absent.
One IMAGE-mode landmarker pass feeds blink, gaze, and head-pose.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Sequence
from urllib.request import urlretrieve

import cv2
import mediapipe as mp

from config import BLINK_SAMPLE_FPS

_FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)

IRIS_LANDMARK_COUNT = 478


@dataclass
class LandmarkSample:
    time_sec: float
    frame_index: int
    landmarks: Optional[Sequence]


def landmarker_model_path() -> Optional[str]:
    model_dir = Path(__file__).resolve().parent.parent / ".models"
    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "face_landmarker.task"
    if not model_path.exists():
        try:
            urlretrieve(_FACE_LANDMARKER_URL, str(model_path))
        except Exception:
            return None
    return str(model_path)


def create_face_landmarker():
    """Return a Tasks FaceLandmarker, or None if the runtime/model is unavailable."""
    try:
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions, RunningMode
    except Exception:
        return None
    model_path = landmarker_model_path()
    if model_path is None:
        return None
    try:
        options = FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
        )
        return FaceLandmarker.create_from_options(options)
    except Exception:
        return None


def detect_landmarks(landmarker, frame_bgr: np.ndarray) -> Optional[Sequence]:
    if landmarker is None or frame_bgr is None:
        return None
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    faces = result.face_landmarks or []
    if not faces:
        return None
    return faces[0]


def iter_landmark_samples(
    video_path: str,
    *,
    sample_fps: int = BLINK_SAMPLE_FPS,
    landmarker=None,
) -> Iterator[LandmarkSample]:
    """Yield sampled FaceLandmarker results. Caller closes `landmarker` if it passed one."""
    owned = landmarker is None
    if owned:
        landmarker = create_face_landmarker()
    cap = cv2.VideoCapture(video_path)
    try:
        if landmarker is None or not cap.isOpened():
            return
        source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_step = max(int(round(source_fps / float(sample_fps))), 1)
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_index % frame_step == 0:
                yield LandmarkSample(
                    time_sec=round(frame_index / source_fps, 3),
                    frame_index=frame_index,
                    landmarks=detect_landmarks(landmarker, frame),
                )
            frame_index += 1
    finally:
        cap.release()
        if owned and landmarker is not None:
            landmarker.close()


def nearest_landmarks(
    samples: Sequence[LandmarkSample],
    time_sec: float,
    *,
    max_dt: float = 0.6,
) -> Optional[Sequence]:
    if not samples:
        return None
    best = min(samples, key=lambda item: abs(item.time_sec - time_sec))
    if abs(best.time_sec - time_sec) > max_dt:
        return None
    return best.landmarks


def video_duration_seconds(video_path: str) -> float:
    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            return 0.0
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0
        if fps > 0 and frames > 0:
            return float(frames / fps)
        return 0.0
    finally:
        cap.release()


def has_iris(landmarks: Optional[Sequence]) -> bool:
    try:
        return landmarks is not None and len(landmarks) >= IRIS_LANDMARK_COUNT
    except TypeError:
        return False
