from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np


@dataclass
class FrameData:
    time_sec: float
    frame: np.ndarray


class VideoProcessor:
    def __init__(self, target_fps: int = 1) -> None:
        if target_fps <= 0:
            raise ValueError("target_fps must be greater than 0")
        self.target_fps = target_fps

    def iter_frames(self, video_path: str) -> Iterator[FrameData]:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            cap.release()
            raise FileNotFoundError(f"Could not open video file: {video_path}")

        source_fps = cap.get(cv2.CAP_PROP_FPS)
        if source_fps <= 0:
            source_fps = 25.0

        frame_step = max(int(round(source_fps / self.target_fps)), 1)

        frame_index = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_index % frame_step == 0:
                    time_sec = round(frame_index / source_fps, 2)
                    yield FrameData(time_sec=time_sec, frame=frame)

                frame_index += 1
        finally:
            cap.release()
