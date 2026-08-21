"""Shared scoring helpers. Missing values are omitted, never coerced to 0."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


def clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, value))


def is_finite_number(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


def measured_value(
    *,
    raw: Any,
    normalized: Optional[float],
    available: bool,
    method: str,
    status: str = "available",
) -> Dict[str, Any]:
    payload = {
        "raw": raw,
        "normalized": None if normalized is None else round(float(normalized), 4),
        "available": bool(available),
        "method": method,
        "status": status if available else (status if status != "available" else "unavailable"),
    }
    if payload["normalized"] is not None:
        payload["normalized"] = clamp(float(payload["normalized"]))
    return payload


def weighted_mean_available(
    parts: Dict[str, Optional[float]],
    weights: Dict[str, float],
) -> Tuple[Optional[float], Dict[str, float]]:
    """Average only present parts; renormalize their weights.

    Returns (score in [0,1] or None, applied_weights). None if nothing is available.
    """
    available = {
        key: float(value)
        for key, value in parts.items()
        if value is not None and is_finite_number(value) and key in weights
    }
    if not available:
        return None, {}
    weight_sum = sum(float(weights[key]) for key in available)
    if weight_sum <= 0:
        return None, {}
    applied_raw = {key: float(weights[key]) / weight_sum for key in available}
    applied = {key: round(applied_raw[key], 4) for key in available}
    blended = sum(applied_raw[key] * clamp(available[key]) for key in available)
    return clamp(blended), applied
