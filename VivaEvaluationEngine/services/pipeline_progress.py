"""Optional progress callbacks for the viva analyze pipeline.

Uses a process-wide slot on ``sys`` so it still works when this file is
imported twice (``services.pipeline_progress`` and
``VivaEvaluationEngine.services.pipeline_progress``).
"""
from __future__ import annotations

import sys
from typing import Callable, Optional

ProgressFn = Callable[[str, str], None]
_SLOT = "_viva_pipeline_progress_cb"


def emit(stage: str, message: str) -> None:
    callback = getattr(sys, _SLOT, None)
    if callable(callback):
        callback(str(stage), str(message))
    else:
        print(f"[VIVA] {message}")


class progress_callback:
    def __init__(self, callback: Optional[ProgressFn]) -> None:
        self.callback = callback
        self._previous: Optional[ProgressFn] = None

    def __enter__(self) -> "progress_callback":
        self._previous = getattr(sys, _SLOT, None)
        setattr(sys, _SLOT, self.callback)
        return self

    def __exit__(self, *_exc: object) -> None:
        setattr(sys, _SLOT, self._previous)
