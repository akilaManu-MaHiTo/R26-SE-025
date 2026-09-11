"""Single-student camera gate — reject viva when multiple faces are clearly visible."""
from __future__ import annotations

from typing import Any, Dict, Optional

from config import (
    MIN_CONSECUTIVE_MULTI_FACE_FRAMES,
    MIN_MULTI_FACE_FRAME_RATIO,
    MIN_SECONDARY_FACE_AREA_RATIO,
)


def _coverage_multi_face(result: Dict[str, Any]) -> Dict[str, Any]:
    coverage = result.get("coverage") or {}
    nested = coverage.get("multi_face")
    if isinstance(nested, dict):
        return nested
    top = result.get("multi_face")
    return top if isinstance(top, dict) else {}


def summarize_multi_face(result: Dict[str, Any]) -> Dict[str, Any]:
    data = _coverage_multi_face(result)
    frames_sampled = int(data.get("frames_sampled") or 0)
    significant_frames = int(data.get("frames_with_significant_second_face") or 0)
    max_consecutive = int(data.get("max_consecutive_frames") or 0)

    ratio = round(significant_frames / frames_sampled, 4) if frames_sampled else 0.0
    ratio_threshold = float(
        data.get("min_frame_ratio_threshold") or MIN_MULTI_FACE_FRAME_RATIO
    )
    consecutive_threshold = int(
        data.get("min_consecutive_frames_threshold") or MIN_CONSECUTIVE_MULTI_FACE_FRAMES
    )
    secondary_ratio_threshold = float(
        data.get("min_secondary_area_ratio") or MIN_SECONDARY_FACE_AREA_RATIO
    )

    available = frames_sampled > 0
    if not available:
        passed = True
    else:
        passed = (
            ratio < ratio_threshold
            and max_consecutive < consecutive_threshold
        )

    return {
        "available": available,
        "frames_sampled": frames_sampled,
        "frames_with_significant_second_face": significant_frames,
        "significant_second_face_ratio": ratio,
        "max_consecutive_frames": max_consecutive,
        "min_secondary_area_ratio": secondary_ratio_threshold,
        "min_frame_ratio_threshold": ratio_threshold,
        "min_consecutive_frames_threshold": consecutive_threshold,
        "passed": passed,
    }


def classify_multi_face_evidence(result: Dict[str, Any]) -> Optional[str]:
    summary = summarize_multi_face(result)
    if not summary.get("available"):
        return None
    if not summary.get("passed"):
        return "multiple_faces_detected"
    return None
