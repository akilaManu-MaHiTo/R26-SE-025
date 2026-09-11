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
import numpy as np
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
    yaw_degrees: Optional[float] = None
    pitch_degrees: Optional[float] = None
    roll_degrees: Optional[float] = None


def euler_angles_from_transformation_matrix(matrix) -> Optional[tuple]:
    """Real yaw/pitch/roll (degrees) from a FaceLandmarker 4x4 pose matrix.

    Standard rotation-matrix-to-Euler decomposition (matches solvePnP-style
    conventions): yaw is rotation about the vertical axis, i.e. exactly the
    "is the head turned toward profile" signal — unlike the landmark-distance
    proxies in gaze_head_analyser.py, this isn't confounded by camera distance.
    """
    if matrix is None:
        return None
    r = np.asarray(matrix)[:3, :3]
    sy = float((r[0, 0] ** 2 + r[1, 0] ** 2) ** 0.5)
    if sy < 1e-6:
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        pitch = np.degrees(np.arctan2(-r[1, 2], r[1, 1]))
        roll = 0.0
    else:
        yaw = np.degrees(np.arctan2(-r[2, 0], sy))
        pitch = np.degrees(np.arctan2(r[2, 1], r[2, 2]))
        roll = np.degrees(np.arctan2(r[1, 0], r[0, 0]))
    return float(yaw), float(pitch), float(roll)


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
            output_facial_transformation_matrixes=True,
        )
        return FaceLandmarker.create_from_options(options)
    except Exception:
        return None


def detect_landmarks(landmarker, frame_bgr: np.ndarray) -> Optional[Sequence]:
    return detect_landmarks_and_pose(landmarker, frame_bgr)[0]


def detect_landmarks_and_pose(
    landmarker, frame_bgr: np.ndarray
) -> "tuple[Optional[Sequence], Optional[tuple]]":
    if landmarker is None or frame_bgr is None:
        return None, None
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = landmarker.detect(mp_image)
    faces = result.face_landmarks or []
    if not faces:
        return None, None
    matrices = result.facial_transformation_matrixes or []
    pose = euler_angles_from_transformation_matrix(matrices[0]) if matrices else None
    return faces[0], pose


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
                landmarks, pose = detect_landmarks_and_pose(landmarker, frame)
                yaw, pitch, roll = pose if pose is not None else (None, None, None)
                yield LandmarkSample(
                    time_sec=round(frame_index / source_fps, 3),
                    frame_index=frame_index,
                    landmarks=landmarks,
                    yaw_degrees=yaw,
                    pitch_degrees=pitch,
                    roll_degrees=roll,
                )
            frame_index += 1
    finally:
        cap.release()
        if owned and landmarker is not None:
            landmarker.close()


def nearest_sample(
    samples: Sequence[LandmarkSample],
    time_sec: float,
    *,
    max_dt: float = 0.6,
) -> Optional[LandmarkSample]:
    if not samples:
        return None
    best = min(samples, key=lambda item: abs(item.time_sec - time_sec))
    if abs(best.time_sec - time_sec) > max_dt:
        return None
    return best


def nearest_landmarks(
    samples: Sequence[LandmarkSample],
    time_sec: float,
    *,
    max_dt: float = 0.6,
) -> Optional[Sequence]:
    sample = nearest_sample(samples, time_sec, max_dt=max_dt)
    return sample.landmarks if sample is not None else None


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
