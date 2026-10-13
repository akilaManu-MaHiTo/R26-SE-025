"""Shared viva analysis + persistence pipeline.

Extracted verbatim from the /api/viva-analyze handler so the live copilot's
end-of-session analysis runs the *same* chain rather than a divergent copy:

    saved video file
      -> viva_service.analyze_video_file      (emotion / engagement / audio / LLM / QA)
      -> optional technical_accuracy_ai        (when subject_code has a rubric)
      -> assessment_scoring.attach_assessment  (official Stage-1 mark)
      -> vivamark.marks persistence
      -> auto-publish for WITHOUT_TECHNICAL_ACCURACY

Callers differ only in `source` ("upload" vs "live_copilot") and in any extra
document fields they want stamped on the mark. Scoring itself is identical, so
a live session and an uploaded recording are graded on the same basis.
"""
from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from VivaEvaluationEngine.services.assessment_scoring import MODE_WITH, MODE_WITHOUT

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UPLOAD_DIR = PROJECT_ROOT / "Gradex_AI_Server" / "app" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_VIVA_UPLOAD_BYTES = 1024 * 1024 * 1024
VIDEO_SUFFIXES = {".mp4", ".webm", ".mov", ".avi", ".mkv", ".m4v"}


def analyze_timeout_seconds() -> float:
    raw = (os.getenv("VIVA_ANALYZE_TIMEOUT_SECONDS") or "600").strip()
    try:
        value = float(raw)
    except ValueError:
        return 600.0
    return value if value > 0 else 600.0


async def run_analysis(
    video_path: str,
    *,
    debug: bool = False,
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the ML pipeline off the event loop, with the shared timeout."""
    from Gradex_AI_Server.app.viva_progress import bind_progress, publish
    from Gradex_AI_Server.app.viva_service import analyze_video_file

    def _run() -> Dict[str, Any]:
        publish(progress_id, "starting", "Starting video analysis")
        with bind_progress(progress_id):
            return analyze_video_file(video_path, debug)

    return await asyncio.wait_for(
        asyncio.to_thread(_run),
        timeout=analyze_timeout_seconds(),
    )


async def attach_subject_technical_accuracy(
    result: Dict[str, Any],
    subject_code: Optional[str],
    db_instance: Any,
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Optional advisory technical-accuracy panel. Never auto-published."""
    code = subject_code.strip() if isinstance(subject_code, str) else ""
    if not code:
        return result
    from Gradex_AI_Server.app.viva_progress import publish

    publish(progress_id, "technical", "Scoring concept coverage")
    try:
        from Gradex_AI_Server.app.subject_rubric_service import get_subject_rubric
        from VivaEvaluationEngine.services.technical_accuracy import attach_technical_accuracy

        concept_rubric = await get_subject_rubric(db_instance, code)
        return attach_technical_accuracy(result, concept_rubric)
    except Exception as exc:
        print(f"[VIVA] Warning: technical-accuracy scoring failed ({exc})")
        result["technical_accuracy_ai"] = {
            "status": "unavailable",
            "model": None,
            "overall_score": None,
            "concepts": [],
            "error": str(exc),
        }
        return result


async def persist_and_autopublish(
    result: Dict[str, Any],
    db_instance: Any,
    *,
    mode: str,
    video_filename: Optional[str],
    source: str = "upload",
    extra_doc: Optional[Dict[str, Any]] = None,
    progress_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Save the mark and auto-publish non-technical vivas.

    Best-effort: a storage failure annotates the result but never fails an
    otherwise-successful analysis.
    """
    from Gradex_AI_Server.app.core.database import ensure_marks_collection
    from Gradex_AI_Server.app.viva_progress import publish

    publish(progress_id, "saving", "Saving the mark")
    result["assessment_mode"] = mode

    if not await ensure_marks_collection():
        result["persistence_error"] = (
            "MongoDB is not connected — mark was not saved. Publish is unavailable."
        )
        print(f"[VIVA] Warning: {result['persistence_error']}")
        return result

    try:
        assessment = result.get("assessment") or {}
        mark_doc: Dict[str, Any] = {
            "video_filename": video_filename,
            "processed_at": datetime.now(timezone.utc),
            "published": False,
            "human_published": False,
            "student_id": None,
            "source": source,
            "confidence_score": result.get("confidence_score"),
            "engagement_score": result.get("engagement_score"),
            "video_status": result.get("video_status"),
            "assessment": assessment,
            "scoring_version": assessment.get("scoring_version"),
            "feature_schema_version": assessment.get("feature_schema_version"),
            "result": result,
        }
        if extra_doc:
            mark_doc.update(extra_doc)

        insert_result = await db_instance.marks_col.insert_one(mark_doc)
        mark_object_id = insert_result.inserted_id
        result["mark_id"] = str(mark_object_id)
        result["published"] = False
        result["source"] = source

        if mode == MODE_WITH:
            # Technical viva: never auto-publish. Stays a draft until an
            # examiner enters a technical score and publishes.
            print(f"[VIVA] Technical viva — mark {result['mark_id']} saved as draft, awaiting examiner review.")
        else:
            from Gradex_AI_Server.app.viva_marks import (
                auto_publish_without_technical,
                merge_auto_publish_into_analyze_result,
            )

            try:
                auto_payload = await auto_publish_without_technical(
                    db_instance.marks_col, mark_object_id, result
                )
                if auto_payload:
                    merge_auto_publish_into_analyze_result(result, auto_payload)
                    print(f"[VIVA] Auto-published mark {result['mark_id']} (non-technical viva)")
            except Exception as auto_exc:
                print(f"[VIVA] Warning: auto-publish failed; mark remains draft. ({auto_exc})")
    except Exception as exc:
        result["persistence_error"] = (
            "Could not save mark (Mongo authentication or network failed)."
        )
        print(f"[VIVA] Warning: failed to persist result to MongoDB ({type(exc).__name__}: {exc})")
        await ensure_marks_collection()

    return result


def normalize_mode(assessment_mode: Any) -> str:
    """A stray value (or a raw Form(...) sentinel) falls back to the safe default."""
    return assessment_mode if assessment_mode in {MODE_WITH, MODE_WITHOUT} else MODE_WITHOUT
