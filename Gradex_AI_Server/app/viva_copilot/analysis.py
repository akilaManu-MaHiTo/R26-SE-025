"""End-of-session analysis for a live copilot viva.

Runs the SAME scoring chain as an uploaded recording (see
viva_analysis_runner), so a live session and an upload produce identical
assessment/grade semantics. The only live-specific additions are:

  * the mark is stamped source="live_copilot" plus the session id
  * the copilot's live transcript log and the examiner's asked questions are
    attached to the engine result as `live_session`, and the interviewer Q&A
    is offered to the Q&A-relevance step

Scoring itself is still driven by the recording, not by the live transcript.
That is deliberate: the Stage-1 families (engagement CNN, Praat acoustics,
face coverage) are all video/waveform-derived, and the quality gates in
assessment_scoring depend on them. A transcript-only mark would be voided by
those gates, so the recording is what makes a live session gradable at all.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_live_transcript(session) -> Dict[str, Any]:
    """Serialize the live session into the JSON carried alongside the mark."""
    turns: List[Dict[str, Any]] = [dict(item) for item in (session.transcript_log or [])]
    student_text = " ".join(
        str(turn.get("text") or "").strip()
        for turn in turns
        if str(turn.get("speaker") or "") == "student"
    ).strip()
    return {
        "session_id": session.session_id,
        "project_context": dict(session.project_context or {}),
        "main_points": list(session.main_points or []),
        "asked_questions": list(session.asked_questions or []),
        "qa_pairs": [dict(pair) for pair in (session.recent_qa or [])],
        "analysis": dict(session.analysis or {}),
        "turns": turns,
        "turn_count": len(turns),
        "student_text": student_text,
        "student_word_count": len(student_text.split()),
    }


def attach_live_session(result: Dict[str, Any], live: Dict[str, Any]) -> Dict[str, Any]:
    """Attach the live-session record without disturbing engine-owned keys.

    Writes only under `live_session`, and fills `interviewer_questions` only
    when the engine did not already produce it — so the recorded-video path's
    own Q&A output is never overwritten.
    """
    result["live_session"] = live
    asked = list(live.get("asked_questions") or [])
    if asked and not result.get("interviewer_questions"):
        result["interviewer_questions"] = asked
    return result


async def analyze_live_session(
    session,
    video_path: str,
    *,
    db_instance,
    mode: str,
    video_filename: Optional[str] = None,
    subject_code: Optional[str] = None,
    student_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Full live-session assessment: recording -> engine -> mark -> publish."""
    from Gradex_AI_Server.app.viva_analysis_runner import (
        attach_subject_technical_accuracy,
        persist_and_autopublish,
        run_analysis,
    )

    live = build_live_transcript(session)

    result = await run_analysis(video_path)
    result = attach_live_session(result, live)
    result = await attach_subject_technical_accuracy(result, subject_code, db_instance)

    extra_doc: Dict[str, Any] = {
        "copilot_session_id": session.session_id,
        "live_transcript": live,
    }
    if student_id:
        extra_doc["student_id"] = student_id

    return await persist_and_autopublish(
        result,
        db_instance,
        mode=mode,
        video_filename=video_filename,
        source="live_copilot",
        extra_doc=extra_doc,
    )
