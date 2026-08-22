"""Temporal engagement sequence model.

Default is unavailable until a real trained checkpoint exists.
Do not randomly initialize an LSTM and treat its output as engagement.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from config import TEMPORAL_ENGAGEMENT_CHECKPOINT


class TemporalEngagementModel:
    def __init__(self, checkpoint_path: Optional[str] = None) -> None:
        self.checkpoint_path = checkpoint_path or os.getenv(
            "VIVA_TEMPORAL_ENGAGEMENT_CHECKPOINT", TEMPORAL_ENGAGEMENT_CHECKPOINT
        )
        self.status = "unavailable"
        self.reason = "no_trained_checkpoint"
        self._predict_fn = None
        self._try_load()

    def _try_load(self) -> None:
        path = Path(self.checkpoint_path) if self.checkpoint_path else None
        if path is None or not path.is_file():
            self.status = "unavailable"
            self.reason = "no_trained_checkpoint"
            return
        try:
            import torch

            blob = torch.load(str(path), map_location="cpu", weights_only=False)
        except Exception:
            self.status = "unavailable"
            self.reason = "checkpoint_load_failed"
            return

        predict = getattr(blob, "predict", None)
        if callable(predict):
            self._predict_fn = predict
            self.status = "ready"
            self.reason = "checkpoint_loaded"
            return

        # A raw state_dict is not enough without the architecture + labeled training.
        self.status = "unavailable"
        self.reason = "checkpoint_architecture_unknown"

    def predict(self, sequence: Sequence[Dict[str, Any]]) -> Optional[float]:
        if self.status != "ready" or self._predict_fn is None:
            return None
        if not sequence:
            return None
        try:
            score = self._predict_fn(sequence)
            value = float(score)
        except Exception:
            return None
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return max(0.0, min(1.0, value))

    def describe(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score": None,
            "reason": self.reason,
            "trained": self.status == "ready",
            "checkpoint_present": bool(
                self.checkpoint_path and Path(self.checkpoint_path).is_file()
            ),
        }


def build_temporal_sequence(
    timeline: Sequence[Dict[str, Any]],
    gaze_signals: Sequence[Optional[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Pack per-frame emotion/gaze/head signals for a future sequence model."""
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(timeline):
        gaze = gaze_signals[index] if index < len(gaze_signals) else None
        gaze = gaze or {}
        rows.append(
            {
                "time": item.get("time"),
                "emotion": item.get("emotion"),
                "emotion_confidence": item.get("emotion_confidence"),
                "gaze_ok": gaze.get("gaze_ok"),
                "gaze_x": gaze.get("gaze_x"),
                "gaze_y": gaze.get("gaze_y"),
                "yaw_proxy": gaze.get("yaw_proxy", gaze.get("yaw")),
                "pitch_proxy": gaze.get("pitch_proxy", gaze.get("pitch")),
                "roll_proxy": gaze.get("roll_proxy", gaze.get("roll")),
            }
        )
    return rows
