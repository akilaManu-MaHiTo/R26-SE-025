from typing import Dict, Optional, Sequence

import numpy as np

from config import GAZE_DIRECTION_DEADZONE, GAZE_ON_CAMERA_THRESHOLD
from services.face_landmarker import create_face_landmarker, detect_landmarks, has_iris

LEFT_IRIS = (468, 469, 470, 471, 472)
RIGHT_IRIS = (473, 474, 475, 476, 477)


def _iris_center(lm, indices) -> tuple:
    xs = [lm[i].x for i in indices]
    ys = [lm[i].y for i in indices]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def gaze_metrics_from_landmarks(lm, gaze_threshold: float = GAZE_ON_CAMERA_THRESHOLD) -> Dict:
    """Iris vs eye-corner offsets. Threshold is config.GAZE_ON_CAMERA_THRESHOLD."""
    if not has_iris(lm):
        raise IndexError("iris landmarks required (478-point mesh)")
    left_iris_x, left_iris_y = _iris_center(lm, LEFT_IRIS)
    right_iris_x, right_iris_y = _iris_center(lm, RIGHT_IRIS)
    left_eye_cx = (lm[33].x + lm[133].x) / 2
    left_eye_cy = (lm[33].y + lm[133].y) / 2
    right_eye_cx = (lm[362].x + lm[263].x) / 2
    right_eye_cy = (lm[362].y + lm[263].y) / 2

    left_dx = left_iris_x - left_eye_cx
    right_dx = right_iris_x - right_eye_cx
    left_dy = left_iris_y - left_eye_cy
    right_dy = right_iris_y - right_eye_cy
    gaze_x = (left_dx + right_dx) / 2
    gaze_y = (left_dy + right_dy) / 2
    offset = abs(left_dx) + abs(right_dx)
    gaze_ok = offset < gaze_threshold
    # Raw cheek-to-cheek / nose-to-chin distances in image-normalized coordinates.
    # These are face-width and face-height proxies, not rotation angles: a
    # subject moving toward or away from the camera changes them exactly like
    # a head turn does, because nothing here is normalized against face size.
    # Real Euler angles would need solvePnP with camera intrinsics + a 3D face
    # model, which this module deliberately does not attempt (see module docs).
    yaw_proxy = abs(lm[234].x - lm[454].x)
    pitch_proxy = abs(lm[1].y - lm[152].y)
    roll_proxy = (lm[33].y + lm[133].y) / 2 - (lm[362].y + lm[263].y) / 2
    inter_ocular_distance = float(
        ((right_eye_cx - left_eye_cx) ** 2 + (right_eye_cy - left_eye_cy) ** 2) ** 0.5
    )
    # Scale-invariant versions: dividing by inter-ocular distance cancels out
    # camera-distance changes (both shrink/grow together), leaving something
    # closer to an actual orientation signal. Diagnostic only for now — not
    # yet wired into any scoring path, so introducing it carries no risk to
    # existing (already-unvalidated) head-stability calibration.
    yaw_normalized = None if inter_ocular_distance <= 1e-6 else yaw_proxy / inter_ocular_distance
    pitch_normalized = None if inter_ocular_distance <= 1e-6 else pitch_proxy / inter_ocular_distance
    roll_normalized = None if inter_ocular_distance <= 1e-6 else roll_proxy / inter_ocular_distance
    return {
        "gaze_x": round(float(gaze_x), 4),
        "gaze_y": round(float(gaze_y), 4),
        "gaze_ok": bool(gaze_ok),
        "gaze_direction": classify_gaze_direction(gaze_x, gaze_y),
        "left_dx": round(float(left_dx), 4),
        "right_dx": round(float(right_dx), 4),
        "sum_abs_dx": round(float(offset), 4),
        # Landmark-normalized distances, not Euler-angle degrees, and not yet
        # decoupled from camera distance. Kept for backward compatibility with
        # existing scoring formulas calibrated against this exact magnitude.
        "yaw_proxy": yaw_proxy,
        "pitch_proxy": pitch_proxy,
        "roll_proxy": roll_proxy,
        "face_width_ratio": yaw_proxy,
        "face_height_ratio": pitch_proxy,
        "inter_ocular_distance": round(inter_ocular_distance, 4),
        "yaw_normalized": None if yaw_normalized is None else round(yaw_normalized, 4),
        "pitch_normalized": None if pitch_normalized is None else round(pitch_normalized, 4),
        "roll_normalized": None if roll_normalized is None else round(roll_normalized, 4),
        # Aliases for older diagnostic_engagement readers / stored docs.
        "yaw": yaw_proxy,
        "pitch": pitch_proxy,
        "roll": roll_proxy,
    }


def classify_gaze_direction(
    gaze_x: float,
    gaze_y: float,
    deadzone: float = GAZE_DIRECTION_DEADZONE,
) -> str:
    if abs(gaze_x) < deadzone and abs(gaze_y) < deadzone:
        return "center"
    if abs(gaze_x) >= abs(gaze_y):
        return "left" if gaze_x < 0 else "right"
    return "up" if gaze_y < 0 else "down"


def metrics_from_landmarks(
    lm: Optional[Sequence],
    *,
    gaze_threshold: float = GAZE_ON_CAMERA_THRESHOLD,
) -> Optional[Dict]:
    if lm is None or not has_iris(lm):
        return None
    try:
        metrics = gaze_metrics_from_landmarks(lm, gaze_threshold)
    except (IndexError, AttributeError, TypeError):
        return None
    mouth_open = _mouth_open(lm)
    metrics["mouth_open"] = mouth_open
    metrics["talking"] = mouth_open >= 0.32
    return metrics


def _mouth_open(lm) -> float:
    """Mouth aspect ratio of the on-camera face (higher = lips apart / talking)."""
    try:
        vertical = ((lm[13].x - lm[14].x) ** 2 + (lm[13].y - lm[14].y) ** 2) ** 0.5
        horizontal = ((lm[78].x - lm[308].x) ** 2 + (lm[78].y - lm[308].y) ** 2) ** 0.5
        if horizontal <= 1e-6:
            return 0.0
        return round(float(vertical / horizontal), 4)
    except (IndexError, AttributeError, TypeError):
        return 0.0


class GazeHeadAnalyser:
    def __init__(self, gaze_threshold: float = GAZE_ON_CAMERA_THRESHOLD) -> None:
        self._gaze_threshold = gaze_threshold
        self._landmarker = None
        self._owns_landmarker = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        if self._owns_landmarker and self._landmarker is not None:
            self._landmarker.close()
        self._landmarker = None
        self._owns_landmarker = False

    def from_landmarks(self, landmarks: Optional[Sequence]) -> Optional[Dict]:
        return metrics_from_landmarks(landmarks, gaze_threshold=self._gaze_threshold)

    def analyse(self, frame_bgr: np.ndarray, landmarks: Optional[Sequence] = None) -> Optional[Dict]:
        if landmarks is not None:
            return self.from_landmarks(landmarks)
        if self._landmarker is None:
            self._landmarker = create_face_landmarker()
            self._owns_landmarker = self._landmarker is not None
        if self._landmarker is None:
            return None
        detected = detect_landmarks(self._landmarker, frame_bgr)
        return self.from_landmarks(detected)
