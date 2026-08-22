"""Enhance a single-student webcam face crop, then measure quality.

Typical Gradex capture is one camera on one student. Skipping blurry/dark
frames would throw away the only face, so analysis always tries to lift the
crop first:

  1. mild non-local-means denoise (webcam grain)
  2. CLAHE on luminance (dark / uneven lighting)
  3. gamma lift if still dark
  4. gentle unsharp if still soft

This is classical OpenCV enhancement, not a generative face-restore model.
GFPGAN / CodeFormer can invent expressions and are not used.

After enhance, dark/blurry is a warning and the frame is still scored.
Only empty or tiny crops are skipped (there is no face to enhance).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from config import (
    FACE_CLAHE_CLIP,
    FACE_DENOISE_H,
    FACE_GAMMA_TARGET,
    FACE_MAX_BRIGHTNESS,
    FACE_MIN_BRIGHTNESS,
    FACE_MIN_CONTRAST,
    FACE_MIN_SHARPNESS,
    FACE_MIN_SIDE_PX,
    FACE_QUALITY_PROBE_SIZE,
    FACE_UNSHARP_AMOUNT,
    FACE_UNSHARP_IF_BELOW,
)


def _metrics(face_bgr: np.ndarray) -> Dict[str, Any]:
    height, width = face_bgr.shape[:2]
    if face_bgr.ndim == 3:
        gray = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2GRAY)
    else:
        gray = face_bgr
    probe = cv2.resize(
        gray,
        (FACE_QUALITY_PROBE_SIZE, FACE_QUALITY_PROBE_SIZE),
        interpolation=cv2.INTER_AREA,
    )
    return {
        "sharpness": round(float(cv2.Laplacian(probe, cv2.CV_64F).var()), 2),
        "brightness": round(float(np.mean(probe)), 2),
        "contrast": round(float(np.std(probe)), 2),
        "width": int(width),
        "height": int(height),
    }


def _warning_reason(metrics: Dict[str, Any]) -> Optional[str]:
    brightness = float(metrics.get("brightness") or 0.0)
    contrast = float(metrics.get("contrast") or 0.0)
    sharpness = float(metrics.get("sharpness") or 0.0)
    if brightness < FACE_MIN_BRIGHTNESS:
        return "dark"
    if brightness > FACE_MAX_BRIGHTNESS:
        return "overexposed"
    if contrast < FACE_MIN_CONTRAST:
        return "low_contrast"
    if sharpness < FACE_MIN_SHARPNESS:
        return "blurry"
    return None


def assess_face_crop(face_bgr: Optional[np.ndarray]) -> Dict[str, Any]:
    """Measure crop quality. ok=False means a warning, except empty/too_small."""
    if face_bgr is None or getattr(face_bgr, "size", 0) == 0 or face_bgr.ndim < 2:
        return {
            "ok": False,
            "reason": "empty",
            "sharpness": None,
            "brightness": None,
            "contrast": None,
            "width": None,
            "height": None,
        }
    height, width = face_bgr.shape[:2]
    if min(height, width) < FACE_MIN_SIDE_PX:
        return {
            "ok": False,
            "reason": "too_small",
            "sharpness": None,
            "brightness": None,
            "contrast": None,
            "width": int(width),
            "height": int(height),
        }
    metrics = _metrics(face_bgr)
    reason = _warning_reason(metrics)
    return {"ok": reason is None, "reason": reason, **metrics}


def enhance_face_crop(face_bgr: np.ndarray) -> Tuple[np.ndarray, List[str]]:
    """Lift a webcam face crop. Always safe to run on a valid BGR crop."""
    if face_bgr.ndim == 2:
        image = cv2.cvtColor(face_bgr, cv2.COLOR_GRAY2BGR)
    else:
        image = face_bgr.copy()
    steps: List[str] = []

    h_param = float(FACE_DENOISE_H)
    if min(image.shape[:2]) >= FACE_MIN_SIDE_PX and h_param > 0:
        image = cv2.fastNlMeansDenoisingColored(image, None, h_param, h_param, 7, 21)
        steps.append("denoise")

    lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
    lightness, chroma_a, chroma_b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=float(FACE_CLAHE_CLIP), tileGridSize=(8, 8))
    lightness = clahe.apply(lightness)
    image = cv2.cvtColor(cv2.merge([lightness, chroma_a, chroma_b]), cv2.COLOR_LAB2BGR)
    steps.append("clahe")

    brightness = float(np.mean(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)))
    if brightness < FACE_GAMMA_TARGET and brightness > 0:
        gamma = float(np.clip(np.log(FACE_GAMMA_TARGET / 255.0) / np.log(brightness / 255.0), 0.45, 1.0))
        table = np.array([((i / 255.0) ** gamma) * 255.0 for i in range(256)]).astype(np.uint8)
        image = cv2.LUT(image, table)
        steps.append("gamma")

    sharpness = _metrics(image)["sharpness"]
    if sharpness < FACE_UNSHARP_IF_BELOW:
        blur = cv2.GaussianBlur(image, (0, 0), 1.0)
        image = cv2.addWeighted(image, 1.0 + FACE_UNSHARP_AMOUNT, blur, -FACE_UNSHARP_AMOUNT, 0)
        steps.append("unsharp")

    return image, steps


def prepare_face_for_emotion(face_bgr: Optional[np.ndarray]) -> Dict[str, Any]:
    """Enhance a detected face and say whether it can be scored.

    Returns crop=None only for empty/too_small. Dark/blurry crops are enhanced
    and still returned for emotion analysis.
    """
    before = assess_face_crop(face_bgr)
    if before.get("reason") in {"empty", "too_small"}:
        return {
            "crop": None,
            "enhanced": False,
            "steps": [],
            "before": before,
            "after": before,
            "ok": False,
            "scored": False,
            "warning": before.get("reason"),
        }

    assert face_bgr is not None
    enhanced, steps = enhance_face_crop(face_bgr)
    after = assess_face_crop(enhanced)
    warning = after.get("reason")
    return {
        "crop": enhanced,
        "enhanced": True,
        "steps": steps,
        "before": before,
        "after": after,
        "ok": bool(after.get("ok")),
        "scored": True,
        "warning": warning,
    }
