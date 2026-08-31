from pathlib import Path
from typing import Any, List, Optional, Tuple
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
import numpy as np


BBox = Tuple[int, int, int, int]


class FaceDetector:
    _TASKS_MODEL_URL = (
        "https://storage.googleapis.com/mediapipe-models/face_detector/"
        "blaze_face_short_range/float16/latest/blaze_face_short_range.tflite"
    )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._detector is not None:
            self._detector.close()
            self._detector = None

    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        padding_ratio: float = 0.1,
        debug: bool = False,
    ) -> None:
        self.padding_ratio = padding_ratio
        self._mode = "solutions"
        self._detector: Any = None
        self._min_detection_confidence = min_detection_confidence
        self._debug = debug

        if hasattr(mp, "solutions") and hasattr(mp.solutions, "face_detection"):
            self._mp_face_detection = mp.solutions.face_detection
            self._detector = self._mp_face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=min_detection_confidence,
            )
            return

        # Newer minimal mediapipe builds expose only the Tasks API.
        self._mode = "tasks"
        self._tasks_model_path = self._ensure_tasks_model()
        self._detector = self._build_tasks_detector(min_detection_confidence)

    def _ensure_tasks_model(self) -> str:
        model_dir = Path(__file__).resolve().parent.parent / ".models"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / "blaze_face_short_range.tflite"

        if not model_path.exists():
            urlretrieve(self._TASKS_MODEL_URL, str(model_path))

        return str(model_path)

    def _build_tasks_detector(self, min_detection_confidence: float) -> Any:
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python.vision import FaceDetector as TasksFaceDetector
        from mediapipe.tasks.python.vision import FaceDetectorOptions
        from mediapipe.tasks.python.vision import RunningMode

        options = FaceDetectorOptions(
            base_options=BaseOptions(model_asset_path=self._tasks_model_path),
            running_mode=RunningMode.IMAGE,
            min_detection_confidence=min_detection_confidence,
        )
        return TasksFaceDetector.create_from_options(options)

    @staticmethod
    def _bbox_area(bbox: BBox) -> int:
        x1, y1, x2, y2 = bbox
        width = max(0, x2 - x1)
        height = max(0, y2 - y1)
        return width * height

    def detect_faces(self, frame_bgr: np.ndarray) -> List[BBox]:
        """Return all face boxes in the frame, largest first."""
        h, w = frame_bgr.shape[:2]
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        boxes: List[BBox] = []

        if self._mode == "solutions":
            results = self._detector.process(frame_rgb)
            if not results.detections:
                return []

            for detection in results.detections:
                rel_bbox = detection.location_data.relative_bounding_box

                x1 = max(int(rel_bbox.xmin * w), 0)
                y1 = max(int(rel_bbox.ymin * h), 0)
                bw = max(int(rel_bbox.width * w), 0)
                bh = max(int(rel_bbox.height * h), 0)

                x2 = min(x1 + bw, w)
                y2 = min(y1 + bh, h)

                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)

                if x2 <= x1 or y2 <= y1:
                    continue

                boxes.append((x1, y1, x2, y2))

            boxes.sort(key=self._bbox_area, reverse=True)
            return boxes

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        results = self._detector.detect(mp_image)
        detections = getattr(results, "detections", None)
        if not detections:
            return []

        for detection in detections:
            box = detection.bounding_box
            x1 = max(int(box.origin_x), 0)
            y1 = max(int(box.origin_y), 0)
            bw = max(int(box.width), 0)
            bh = max(int(box.height), 0)

            x2 = min(x1 + bw, w)
            y2 = min(y1 + bh, h)

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            if x2 <= x1 or y2 <= y1:
                continue

            boxes.append((x1, y1, x2, y2))

        boxes.sort(key=self._bbox_area, reverse=True)
        return boxes

    def detect_largest_face(self, frame_bgr: np.ndarray) -> Optional[BBox]:
        faces = self.detect_faces(frame_bgr)
        return faces[0] if faces else None

    def crop_face(self, frame_bgr: np.ndarray, bbox: BBox) -> Optional[np.ndarray]:
        h, w = frame_bgr.shape[:2]
        x1, y1, x2, y2 = bbox

        face_w = x2 - x1
        face_h = y2 - y1

        pad_x = int(face_w * self.padding_ratio)
        pad_y = int(face_h * self.padding_ratio)

        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(w, x2)
        y2 = min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return None

        face = frame_bgr[y1:y2, x1:x2]
        if face.size == 0:
            return None
        return face

    def detect_and_crop(self, frame_bgr: np.ndarray) -> Optional[np.ndarray]:
        bbox = self.detect_largest_face(frame_bgr)
        if bbox is None:
            return None
        if self._debug:
            print(f"Detected bbox: {bbox}")
        return self.crop_face(frame_bgr, bbox)
