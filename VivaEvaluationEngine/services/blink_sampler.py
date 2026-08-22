from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from config import (
    BLINK_EAR_THRESHOLD,
    BLINK_ELEVATED_PER_MINUTE,
    BLINK_ISOLATED_MIN_DROP,
    BLINK_MIN_CONSECUTIVE,
    BLINK_MIN_DURATION_SECONDS,
    BLINK_MIN_VALID_EYE_FRAMES,
    BLINK_RELATIVE_CLOSE_RATIO,
    BLINK_SAMPLE_FPS,
)
from services.face_landmarker import (
    LandmarkSample,
    iter_landmark_samples,
    video_duration_seconds,
)

# MediaPipe canonical 468-mesh eye corners / lids (not iris). Same indices on 478-pt Tasks output.
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 387, 385, 263, 380, 373]


def _ear(lm, indices):
    pts = [(lm[i].x, lm[i].y) for i in indices]
    v1 = np.linalg.norm(np.array(pts[1]) - np.array(pts[5]))
    v2 = np.linalg.norm(np.array(pts[2]) - np.array(pts[4]))
    h = np.linalg.norm(np.array(pts[0]) - np.array(pts[3]))
    return (v1 + v2) / (2.0 * h) if h > 0 else 0.0


def eye_aspect_ratio(landmarks) -> Optional[float]:
    """Mean left/right EAR. None if the mesh is too short for the eye indices."""
    try:
        n = len(landmarks)
    except TypeError:
        return None
    if n <= max(LEFT_EYE + RIGHT_EYE):
        return None
    left = _ear(landmarks, LEFT_EYE)
    right = _ear(landmarks, RIGHT_EYE)
    if left != left or right != right:
        return None
    return (left + right) / 2.0


def closed_eye_threshold(
    ears: Sequence[Optional[float]],
    *,
    abs_threshold: float = BLINK_EAR_THRESHOLD,
    relative_ratio: float = BLINK_RELATIVE_CLOSE_RATIO,
) -> float:
    valid = [float(ear) for ear in ears if ear is not None]
    if not valid:
        return float(abs_threshold)
    baseline = float(np.median(valid))
    return max(float(abs_threshold), float(relative_ratio) * baseline)


def count_blinks_from_ears(
    ears: Sequence[Optional[float]],
    *,
    threshold: float = BLINK_EAR_THRESHOLD,
    min_consec: int = BLINK_MIN_CONSECUTIVE,
    relative_ratio: float = BLINK_RELATIVE_CLOSE_RATIO,
    isolated_min_drop: float = BLINK_ISOLATED_MIN_DROP,
) -> int:
    """Count blinks from an EAR series.

    A frame is closed when EAR is below max(absolute threshold, relative * median).
    Runs of min_consec closed samples count. A single deep trough also counts when
    it drops by isolated_min_drop from a neighbouring open frame — 10 fps otherwise
    misses ~100 ms blinks that occupy one sample.
    """
    values = list(ears)
    n = len(values)
    if n == 0:
        return 0
    valid = [float(ear) for ear in values if ear is not None]
    baseline = float(np.median(valid)) if valid else float(threshold)
    closed_th = max(float(threshold), float(relative_ratio) * baseline)
    closed = [ear is not None and ear < closed_th for ear in values]

    blink_count = 0
    i = 0
    while i < n:
        if not closed[i]:
            i += 1
            continue
        j = i
        min_ear = values[i]
        while j < n and closed[j]:
            if values[j] is not None:
                min_ear = min(min_ear, values[j])  # type: ignore[type-var]
            j += 1
        run_len = j - i
        if run_len >= min_consec:
            blink_count += 1
        elif run_len == 1 and min_ear is not None:
            prev = values[i - 1] if i > 0 else None
            nxt = values[j] if j < n else None
            neighbors = [float(x) for x in (prev, nxt) if x is not None]
            drop = (max(neighbors) - float(min_ear)) if neighbors else 0.0
            deep = float(min_ear) < float(threshold) or float(min_ear) < 0.5 * baseline
            if deep and drop >= isolated_min_drop:
                blink_count += 1
        i = j
    return blink_count


def unavailable_blinks(reason: str) -> Dict[str, Any]:
    return {
        "status": "unavailable",
        "blink_count": None,
        "blink_rate_per_minute": None,
        "valid_eye_frames": 0,
        "reason": reason,
        "note": None,
        "detector": None,
        "measurement_quality": "unavailable",
    }


def _finalize_report(
    *,
    ears: List[Optional[float]],
    sample_fps: int,
    threshold: float,
    min_consec: int,
    detector: str,
    duration_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    valid_eye_frames = sum(1 for ear in ears if ear is not None)
    if duration_seconds is None:
        duration_seconds = len(ears) / float(sample_fps) if sample_fps else 0.0
    if valid_eye_frames < BLINK_MIN_VALID_EYE_FRAMES:
        payload = unavailable_blinks("insufficient_eye_frames")
        payload["valid_eye_frames"] = valid_eye_frames
        payload["detector"] = detector
        return payload
    if duration_seconds < BLINK_MIN_DURATION_SECONDS:
        payload = unavailable_blinks("recording_too_short")
        payload["valid_eye_frames"] = valid_eye_frames
        payload["detector"] = detector
        return payload

    closed_th = closed_eye_threshold(ears, abs_threshold=threshold)
    blink_count = count_blinks_from_ears(
        ears,
        threshold=threshold,
        min_consec=min_consec,
    )
    duration_minutes = duration_seconds / 60.0
    rate = round(blink_count / duration_minutes, 2) if duration_minutes > 0 else 0.0
    note = None
    if rate > BLINK_ELEVATED_PER_MINUTE:
        note = "Elevated blink frequency detected."
    quality = "adequate"
    if duration_seconds < 15.0 or valid_eye_frames < 30:
        quality = "low"
    elif duration_seconds < 30.0:
        quality = "medium"
    return {
        "status": "available",
        "blink_count": int(blink_count),
        "blink_rate_per_minute": rate,
        "valid_eye_frames": valid_eye_frames,
        "reason": None,
        "note": note,
        "detector": detector,
        "ear_threshold": threshold,
        "closed_threshold": round(closed_th, 4),
        "measurement_quality": quality,
        "measurement_quality_reason": (
            "short_window_rate_is_noisy" if quality != "adequate" else None
        ),
    }


def blinks_from_samples(
    samples: Sequence[LandmarkSample],
    *,
    sample_fps: int = BLINK_SAMPLE_FPS,
    ear_threshold: float = BLINK_EAR_THRESHOLD,
    min_consec: int = BLINK_MIN_CONSECUTIVE,
    duration_seconds: Optional[float] = None,
    detector: str = "tasks_face_landmarker",
) -> Dict[str, Any]:
    ears = [
        eye_aspect_ratio(sample.landmarks) if sample.landmarks is not None else None
        for sample in samples
    ]
    return _finalize_report(
        ears=ears,
        sample_fps=sample_fps,
        threshold=ear_threshold,
        min_consec=min_consec,
        detector=detector,
        duration_seconds=duration_seconds,
    )


class BlinkSampler:
    def __init__(
        self,
        sample_fps: int = BLINK_SAMPLE_FPS,
        ear_threshold: float = BLINK_EAR_THRESHOLD,
        min_consec: int = BLINK_MIN_CONSECUTIVE,
    ) -> None:
        self.sample_fps = sample_fps
        self.ear_threshold = ear_threshold
        self.min_consec = min_consec

    def count_blinks(self, video_path: str) -> Optional[float]:
        """Return blinks/min, or None when blinks cannot be measured.

        None must be treated as "exclude from scoring" — never as 0.0 perfect.
        0.0 means measured and observed zero blinks.
        """
        return self.measure_blinks(video_path).get("blink_rate_per_minute")

    def measure_blinks(self, video_path: str) -> Dict[str, Any]:
        duration = video_duration_seconds(video_path)
        samples = list(iter_landmark_samples(video_path, sample_fps=self.sample_fps))
        if not samples:
            if duration <= 0:
                return unavailable_blinks("video_unreadable")
            return unavailable_blinks("face_mesh_unavailable")
        return blinks_from_samples(
            samples,
            sample_fps=self.sample_fps,
            ear_threshold=self.ear_threshold,
            min_consec=self.min_consec,
            duration_seconds=duration or None,
        )
