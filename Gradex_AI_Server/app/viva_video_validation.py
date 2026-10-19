"""Low-cost validation performed before the viva analysis pipeline starts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

MIN_VIVA_UPLOAD_BYTES = 1 * 1024 * 1024
MAX_VIVA_UPLOAD_BYTES = 1024 * 1024 * 1024
MIN_VIVA_DURATION_SECONDS = 10.0
MAX_VIVA_DURATION_SECONDS = 30 * 60.0
QUALITY_SAMPLE_COUNT = 5
MIN_LAPLACIAN_VARIANCE = 20.0
MIN_BRIGHTNESS = 20.0
MAX_BRIGHTNESS = 240.0
MAX_FLAT_FRAME_NOISE = 0.18


def _check_frame_quality(cv2, frame: Any) -> dict[str, float]:
    """Measure only clearly unusable visual quality; normal variation is allowed."""
    small = cv2.resize(frame, (320, 180))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    noise = float(cv2.absdiff(gray, blurred).mean()) / 255.0
    contrast = float(gray.std())
    return {
        "brightness": float(gray.mean()),
        "blur_score": float(cv2.Laplacian(gray, cv2.CV_64F).var()),
        "noise_score": noise if contrast < 35.0 else 0.0,
    }


def validate_viva_video(video_path: str | Path) -> dict[str, Any]:
    """Return basic media facts or raise ValueError with a re-uploadable error."""
    path = Path(video_path)
    if not path.is_file():
        raise ValueError("The uploaded video is missing. Please upload it again.")

    size = path.stat().st_size
    if size < MIN_VIVA_UPLOAD_BYTES:
        raise ValueError("The video is too small. Upload a video of at least 1 MB.")
    if size > MAX_VIVA_UPLOAD_BYTES:
        raise ValueError("The video is too large. Upload a video no larger than 1 GB.")

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("Video validation is unavailable because OpenCV is not installed.") from exc

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError(
                "This file cannot be opened as a video. Please re-upload it as MP4 or WEBM."
            )

        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        duration = frame_count / fps if frame_count > 0 and fps > 0 else 0.0
        if frame_count < 1 or duration <= 0:
            raise ValueError(
                "The video has no readable frames. Please re-upload a playable video."
            )
        if duration < MIN_VIVA_DURATION_SECONDS:
            raise ValueError("The video must be at least 10 seconds long. Please re-upload it.")
        if duration > MAX_VIVA_DURATION_SECONDS:
            raise ValueError("The video must be 30 minutes or shorter. Please re-upload it.")

        sample_indices = {
            min(frame_count - 1, int(frame_count * position / QUALITY_SAMPLE_COUNT))
            for position in range(QUALITY_SAMPLE_COUNT)
        }
        quality_samples = []
        for frame_index in sorted(sample_indices):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            readable, frame = capture.read()
            if not readable or frame is None or getattr(frame, "size", 0) == 0:
                continue
            quality_samples.append(_check_frame_quality(cv2, frame))

        if not quality_samples:
            raise ValueError(
                "The video contains no readable frames. Please re-upload a playable video."
            )

        unusable_blur = sum(
            sample["blur_score"] < MIN_LAPLACIAN_VARIANCE for sample in quality_samples
        )
        unusable_lighting = sum(
            sample["brightness"] < MIN_BRIGHTNESS or sample["brightness"] > MAX_BRIGHTNESS
            for sample in quality_samples
        )
        unusable_noise = sum(
            sample["noise_score"] > MAX_FLAT_FRAME_NOISE for sample in quality_samples
        )
        majority = max(1, (len(quality_samples) + 1) // 2)
        if unusable_blur >= majority:
            raise ValueError(
                "The video is too blurry for reliable viva analysis. "
                "Please re-upload a clearer, steady video."
            )
        if unusable_lighting >= majority:
            raise ValueError(
                "The video is too dark or overexposed for reliable viva analysis. "
                "Please re-upload with better lighting."
            )
        if unusable_noise >= majority:
            raise ValueError(
                "The video has excessive visual noise for reliable viva analysis. "
                "Please re-upload a clearer recording."
            )
    finally:
        capture.release()

    return {
        "size_bytes": size,
        "duration_seconds": round(duration, 2),
        "frame_count": frame_count,
        "fps": round(fps, 2),
        "quality_samples": len(quality_samples),
    }
