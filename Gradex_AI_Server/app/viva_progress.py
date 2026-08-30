"""In-memory analyze progress for the viva UI (polled while POST is in flight)."""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Dict, List, Optional

from VivaEvaluationEngine.services.pipeline_progress import progress_callback

# Same order the engine emits. The client checklist uses this list.
STAGE_ORDER: List[str] = [
    "starting",
    "face_landmarks",
    "facial_emotion",
    "engagement",
    "extract_audio",
    "whisper",
    "audio_emotion",
    "acoustics",
    "llm_judge",
    "qa",
    "assessment",
    "technical",
    "saving",
]

_LOCK = Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}
_MAX_AGE_SECONDS = 900


def normalize_progress_id(raw: Optional[str]) -> Optional[str]:
    value = (raw or "").strip()
    if not value or len(value) > 64:
        return None
    if not all(char.isalnum() or char in "-_" for char in value):
        return None
    return value


def publish(job_id: Optional[str], stage: str, message: str) -> None:
    if not job_id:
        return
    now = time.time()
    with _LOCK:
        _expire_locked(now)
        previous = _JOBS.get(job_id) or {}
        seen = list(previous.get("done") or [])
        if stage and stage not in seen:
            seen.append(stage)
        _JOBS[job_id] = {
            "stage": stage,
            "message": message,
            "done": seen,
            "updated_at": now,
        }
    print(f"[VIVA] {message}")


def snapshot(job_id: Optional[str]) -> Dict[str, Any]:
    if not job_id:
        return {"stage": None, "message": None, "done": [], "stages": STAGE_ORDER}
    with _LOCK:
        _expire_locked(time.time())
        row = dict(_JOBS.get(job_id) or {})
    return {
        "stage": row.get("stage"),
        "message": row.get("message"),
        "done": list(row.get("done") or []),
        "stages": STAGE_ORDER,
    }


def clear(job_id: Optional[str]) -> None:
    if not job_id:
        return
    with _LOCK:
        _JOBS.pop(job_id, None)


def bind_progress(job_id: Optional[str]) -> progress_callback:
    def _callback(stage: str, message: str) -> None:
        publish(job_id, stage, message)

    return progress_callback(_callback if job_id else None)


def _expire_locked(now: float) -> None:
    stale = [
        key
        for key, row in _JOBS.items()
        if now - float(row.get("updated_at") or 0) > _MAX_AGE_SECONDS
    ]
    for key in stale:
        _JOBS.pop(key, None)
