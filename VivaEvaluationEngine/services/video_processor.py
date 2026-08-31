from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np


# Plausible bounds for a real capture frame rate. Outside this range the
# container metadata is treated as unusable rather than authoritative.
_MIN_PLAUSIBLE_FPS = 1.0
_MAX_PLAUSIBLE_FPS = 240.0
# Used only when fps metadata AND presentation timestamps are both unusable.
_ASSUMED_FPS = 25.0


class VideoUnreadableError(ValueError):
    """The path exists but OpenCV cannot decode it as video."""


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
            raise VideoUnreadableError(
                "This file could not be opened as a video. Upload MP4 or WEBM with a student face on camera."
            )

        source_fps = cap.get(cv2.CAP_PROP_FPS)
        # Browser MediaRecorder webm (live viva) is variable-frame-rate and has
        # no fixed rate in the container, so OpenCV frequently reports the
        # Matroska timescale (e.g. 1000) instead of a real frame rate. Trusting
        # it makes frame_step enormous and samples 1-2 frames from a whole
        # session — which then reads as "100% face coverage" on 1 frame while
        # falling under MIN_FACE_FRAMES, so no mark is issued. Anything outside
        # a plausible capture range is treated as unusable metadata.
        if not (_MIN_PLAUSIBLE_FPS <= source_fps <= _MAX_PLAUSIBLE_FPS):
            source_fps = 0.0

        frame_step = max(int(round(source_fps / self.target_fps)), 1) if source_fps else 0

        frame_index = 0
        yielded = 0
        # Fallback for unusable fps metadata: pace off the container's own
        # presentation timestamps, and if those are missing too, assume a
        # nominal rate so a long recording still yields many samples.
        next_capture_ms = 0.0
        interval_ms = 1000.0 / self.target_fps

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                if frame_step:
                    if frame_index % frame_step == 0:
                        time_sec = round(frame_index / source_fps, 2)
                        yielded += 1
                        yield FrameData(time_sec=time_sec, frame=frame)
                else:
                    pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)
                    if not pos_ms or pos_ms <= 0:
                        pos_ms = (frame_index / _ASSUMED_FPS) * 1000.0
                    if pos_ms >= next_capture_ms:
                        yielded += 1
                        yield FrameData(time_sec=round(pos_ms / 1000.0, 2), frame=frame)
                        # Advance past the frame we just took so a stalled or
                        # non-monotonic timestamp cannot emit every frame.
                        next_capture_ms = pos_ms + interval_ms

                frame_index += 1
        finally:
            cap.release()
            print(
                f"[VIVA][sampler] {video_path}: reported_fps="
                f"{cap.get(cv2.CAP_PROP_FPS)!r} used_fps={source_fps!r} "
                f"frame_step={frame_step} decoded_frames={frame_index} "
                f"yielded={yielded}"
            )
