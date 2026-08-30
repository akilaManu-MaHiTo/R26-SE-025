"""Typed event dicts for the isolated copilot WebSocket."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional


def _now() -> int:
    return int(time.time())


def transcript_partial(session_id: str, text: str, speaker: str = "candidate") -> Dict[str, Any]:
    return {
        "event": "transcript.partial",
        "sessionId": session_id,
        "speaker": speaker,
        "text": text,
        "timestamp": _now(),
    }


def transcript_final(session_id: str, text: str, speaker: str = "candidate") -> Dict[str, Any]:
    return {
        "event": "transcript.final",
        "sessionId": session_id,
        "speaker": speaker,
        "text": text,
        "timestamp": _now(),
    }


def presentation_points(session_id: str, points: List[str], analysis: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "event": "presentation.points.extracted",
        "sessionId": session_id,
        "timestamp": _now(),
        "data": {"points": points, "analysis": analysis or {}},
    }


def candidate_answer_final(session_id: str, answer_id: str, text: str) -> Dict[str, Any]:
    return {
        "event": "candidate.answer.final",
        "sessionId": session_id,
        "answerId": answer_id,
        "speaker": "candidate",
        "text": text,
        "timestamp": _now(),
    }


def followup_suggestion_partial(
    session_id: str,
    answer_id: str,
    suggestion: Dict[str, Any],
) -> Dict[str, Any]:
    """A single suggestion streamed in early, before the full LLM turn (and
    its remaining 1-2 suggestions) has finished generating."""
    return {
        "event": "followup.suggestion.partial",
        "sessionId": session_id,
        "answerId": answer_id,
        "timestamp": _now(),
        "data": {"suggestion": suggestion},
    }


def followup_suggestions(
    session_id: str,
    answer_id: str,
    suggestions: List[Dict[str, Any]],
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "event": "followup.suggestions.generated",
        "sessionId": session_id,
        "answerId": answer_id,
        "timestamp": _now(),
        "data": {
            "suggestions": suggestions,
            "analysis": analysis or {},
        },
    }


def interviewer_asked(session_id: str, question: str) -> Dict[str, Any]:
    return {
        "event": "interviewer.question.asked",
        "sessionId": session_id,
        "text": question,
        "speaker": "interviewer",
        "timestamp": _now(),
    }


def phase_changed(session_id: str, phase: str) -> Dict[str, Any]:
    return {
        "event": "session.phase",
        "sessionId": session_id,
        "phase": phase,
        "timestamp": _now(),
    }


def copilot_error(session_id: str, message: str) -> Dict[str, Any]:
    return {
        "event": "copilot.error",
        "sessionId": session_id,
        "message": message,
        "timestamp": _now(),
    }


def session_state(session_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "event": "session.state",
        "sessionId": session_id,
        "timestamp": _now(),
        "data": payload,
    }


def session_expired(session_id: str, *, ttl_seconds: float) -> Dict[str, Any]:
    return {
        "event": "session.expired",
        "sessionId": session_id,
        "message": "Copilot session expired after inactivity. Create a new session to continue.",
        "ttlSeconds": int(ttl_seconds),
        "timestamp": _now(),
    }
