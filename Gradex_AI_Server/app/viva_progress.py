"""In-memory analyze progress for the viva UI.

Read two ways: a one-shot GET (``snapshot``) and a long-lived SSE stream
(``wait_for_change``). The stream is the path the UI actually uses -- it blocks
until the pipeline publishes a new stage rather than re-asking on a timer, so a
five-minute analysis costs a dozen events instead of hundreds of polls.
"""
from __future__ import annotations

import time
from threading import Condition, Lock
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
# Every waiting SSE stream blocks on this one condition; publish() wakes them all
# and each re-checks its own job's version. Jobs are few and short-lived, so a
# shared condition is cheaper than per-job bookkeeping.
_CHANGED = Condition(_LOCK)
_JOBS: Dict[str, Dict[str, Any]] = {}
_MAX_AGE_SECONDS = 900

# Bumped on every publish so a stream can tell "nothing new" from "same stage,
# new message" without diffing payloads.
_VERSION = 0


def normalize_progress_id(raw: Optional[str]) -> Optional[str]:
    value = (raw or "").strip()
    if not value or len(value) > 64:
        return None
    if not all(char.isalnum() or char in "-_" for char in value):
        return None
    return value


def publish(job_id: Optional[str], stage: str, message: str) -> None:
    global _VERSION
    if not job_id:
        return
    now = time.time()
    with _CHANGED:
        _expire_locked(now)
        previous = _JOBS.get(job_id) or {}
        seen = list(previous.get("done") or [])
        if stage and stage not in seen:
            seen.append(stage)
        _VERSION += 1
        _JOBS[job_id] = {
            "stage": stage,
            "message": message,
            "done": seen,
            "updated_at": now,
            "version": _VERSION,
            "finished": False,
        }
        _CHANGED.notify_all()
    print(f"[VIVA] {message}")


def snapshot(job_id: Optional[str]) -> Dict[str, Any]:
    if not job_id:
        return {
            "stage": None,
            "message": None,
            "done": [],
            "stages": STAGE_ORDER,
            "version": 0,
            "finished": False,
        }
    with _LOCK:
        _expire_locked(time.time())
        row = dict(_JOBS.get(job_id) or {})
    return _as_payload(row)


def _as_payload(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "stage": row.get("stage"),
        "message": row.get("message"),
        "done": list(row.get("done") or []),
        "stages": STAGE_ORDER,
        "version": int(row.get("version") or 0),
        "finished": bool(row.get("finished")),
    }


def finish(job_id: Optional[str]) -> None:
    """Mark a job done so its SSE stream can close instead of idling to timeout."""
    global _VERSION
    if not job_id:
        return
    with _CHANGED:
        row = _JOBS.get(job_id)
        if row is None:
            return
        _VERSION += 1
        row["finished"] = True
        row["version"] = _VERSION
        row["updated_at"] = time.time()
        _CHANGED.notify_all()


def wait_for_change(job_id: str, since_version: int, timeout: float) -> Optional[Dict[str, Any]]:
    """Block until this job moves past ``since_version``.

    Returns the new payload, or None if ``timeout`` elapsed with no change --
    the caller turns that into an SSE keep-alive comment so proxies do not drop
    an idle connection during a long pipeline stage such as Whisper.
    """
    deadline = time.time() + timeout
    with _CHANGED:
        while True:
            row = _JOBS.get(job_id) or {}
            if int(row.get("version") or 0) > since_version:
                return _as_payload(row)
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            _CHANGED.wait(remaining)


def clear(job_id: Optional[str]) -> None:
    if not job_id:
        return
    with _CHANGED:
        _JOBS.pop(job_id, None)
        _CHANGED.notify_all()


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
