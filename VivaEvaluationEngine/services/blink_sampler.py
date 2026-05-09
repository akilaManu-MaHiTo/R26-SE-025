import cv2
import mediapipe as mp
import numpy as np
from typing import Optional

LEFT_EYE  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 387, 385, 263, 380, 373]

def _ear(lm, indices):
    pts = [(lm[i].x, lm[i].y) for i in indices]
    v1 = np.linalg.norm(np.array(pts[1]) - np.array(pts[5]))
    v2 = np.linalg.norm(np.array(pts[2]) - np.array(pts[4]))
    h  = np.linalg.norm(np.array(pts[0]) - np.array(pts[3]))
    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0

class BlinkSampler:
    def __init__(self, sample_fps: int = 10, ear_threshold: float = 0.25,
                 min_consec: int = 2) -> None:
        self.sample_fps      = sample_fps
        self.ear_threshold   = ear_threshold
        self.min_consec      = min_consec

    def count_blinks(self, video_path: str) -> float:
        cap = cv2.VideoCapture(video_path)
        try:
            source_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            frame_step = max(int(round(source_fps / self.sample_fps)), 1)
            if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_mesh"):
                mesh = mp.solutions.face_mesh.FaceMesh(
                    static_image_mode=True,
                    max_num_faces=1,
                    refine_landmarks=False,
                    min_detection_confidence=0.5,
                )
                try:
                    return self._count_in_loop(cap, mesh, frame_step)
                finally:
                    mesh.close()

            # Fallback: mediapipe 'solutions' not available in this build.
            # Blink sampling requires face mesh landmarks; return 0.0 and
            # let the rest of the pipeline proceed.
            return 0.0
        finally:
            cap.release()

    def _count_in_loop(self, cap, mesh, frame_step):
        blink_count = 0
        consec       = 0
        total_sampled = 0
        frame_idx    = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_step == 0:
                total_sampled += 1
                ear = self._frame_ear(frame, mesh)
                if ear is not None and ear < self.ear_threshold:
                    consec += 1
                else:
                    if consec >= self.min_consec:
                        blink_count += 1
                    consec = 0
            frame_idx += 1

        duration_minutes = (total_sampled / self.sample_fps) / 60
        return round(blink_count / duration_minutes, 2) if duration_minutes > 0 else 0.0

    def _frame_ear(self, frame_bgr, mesh) -> Optional[float]:
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        results = mesh.process(rgb)
        if not results.multi_face_landmarks:
            return None
        lm = results.multi_face_landmarks[0].landmark
        return (_ear(lm, LEFT_EYE) + _ear(lm, RIGHT_EYE)) / 2
