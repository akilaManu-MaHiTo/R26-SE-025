import mediapipe as mp
import cv2
import numpy as np
from typing import Optional, Dict


class GazeHeadAnalyser:
    def __init__(self, gaze_threshold: float = 0.04) -> None:
        self._gaze_threshold = gaze_threshold
        self._mesh = None

        # Use solutions FaceMesh when available; otherwise disable gaze analysis.
        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
            self._mesh = mp.solutions.face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
            )

    def __enter__(self):
        return self

    def __exit__(self, *_):
        if self._mesh is not None:
            self._mesh.close()

    def analyse(self, frame_bgr: np.ndarray) -> Optional[Dict]:
        if self._mesh is None:
            return None

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = self._mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None

        lm = results.multi_face_landmarks[0].landmark
        mouth_open = self._mouth_open(lm)
        return {
            "gaze_ok": self._gaze_on_camera(lm),
            "yaw": self._head_yaw(lm),
            "pitch": self._head_pitch(lm),
            "mouth_open": mouth_open,
            "talking": mouth_open >= 0.32,
        }

    def _gaze_on_camera(self, lm) -> bool:
        left_iris_x = (lm[468].x + lm[469].x + lm[470].x + lm[471].x + lm[472].x) / 5
        right_iris_x = (lm[473].x + lm[474].x + lm[475].x + lm[476].x + lm[477].x) / 5
        left_eye_cx = (lm[33].x + lm[133].x) / 2
        right_eye_cx = (lm[362].x + lm[263].x) / 2
        offset = abs(left_iris_x - left_eye_cx) + abs(right_iris_x - right_eye_cx)
        return offset < self._gaze_threshold

    def _head_yaw(self, lm) -> float:
        return abs(lm[234].x - lm[454].x)

    def _head_pitch(self, lm) -> float:
        return abs(lm[1].y - lm[152].y)

    def _mouth_open(self, lm) -> float:
        """Mouth aspect ratio of the on-camera face (higher = lips apart / talking)."""
        try:
            vertical = ((lm[13].x - lm[14].x) ** 2 + (lm[13].y - lm[14].y) ** 2) ** 0.5
            horizontal = ((lm[78].x - lm[308].x) ** 2 + (lm[78].y - lm[308].y) ** 2) ** 0.5
            if horizontal <= 1e-6:
                return 0.0
            return round(float(vertical / horizontal), 4)
        except (IndexError, AttributeError, TypeError):
            return 0.0

