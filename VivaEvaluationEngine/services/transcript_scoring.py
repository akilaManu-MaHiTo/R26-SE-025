"""Feature-complete transcript/communication sub-score. Independent of Groq Q&A."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from config import (
    TRANSCRIPT_COVERAGE_INSUFFICIENT_WORDS,
    TRANSCRIPT_COVERAGE_LIMITED_SECONDS,
    TRANSCRIPT_COVERAGE_LIMITED_WORDS,
)
from services.normalization import speech_rate_score
from services.score_utils import clamp, measured_value, weighted_mean_available

TRANSCRIPT_FEATURE_WEIGHTS = {
    "speech_rate": 0.25,
    "hedges": 0.20,
    "fillers": 0.20,
    "pauses": 0.15,
    "sentence_completion": 0.10,
    "fragmentation": 0.10,
}

NO_STUDENT_TRANSCRIPT = "no_student_transcript"


def transcript_coverage(
    *,
    word_count: Optional[int],
    duration_seconds: Optional[float],
) -> Dict[str, Any]:
    """Diagnostic evidence quantity. Does not change transcript_feature_score."""
    try:
        words = int(word_count) if word_count is not None else 0
    except (TypeError, ValueError):
        words = 0
    try:
        duration = float(duration_seconds) if duration_seconds is not None else None
    except (TypeError, ValueError):
        duration = None

    if words <= 0:
        status = "insufficient"
        reason = "no_student_transcript"
    elif words < TRANSCRIPT_COVERAGE_INSUFFICIENT_WORDS:
        status = "insufficient"
        reason = "short_transcript"
    elif words < TRANSCRIPT_COVERAGE_LIMITED_WORDS or (
        duration is not None and duration < TRANSCRIPT_COVERAGE_LIMITED_SECONDS
    ):
        status = "limited"
        reason = "short_transcript" if words < TRANSCRIPT_COVERAGE_LIMITED_WORDS else "short_duration"
        if words < TRANSCRIPT_COVERAGE_LIMITED_WORDS and duration is not None and duration < TRANSCRIPT_COVERAGE_LIMITED_SECONDS:
            reason = "short_transcript"
    else:
        status = "adequate"
        reason = None

    return {
        "status": status,
        "word_count": words,
        "duration_seconds": None if duration is None else round(duration, 3),
        "reason": reason,
    }


def _count_score(count: Optional[int], scale: float) -> Optional[float]:
    if count is None:
        return None
    return clamp(1.0 - min(1.0, float(count) / scale))


def _has_student_transcript(tx: Dict[str, Any]) -> bool:
    words = tx.get("word_count")
    try:
        return words is not None and int(words) > 0
    except (TypeError, ValueError):
        return False


def compute_transcript_score(features: Dict[str, Any]) -> Dict[str, Any]:
    tx = features.get("transcript_features") or features.get("transcript") or {}
    word_count = tx.get("word_count")

    components_raw = {
        "speech_rate": measured_value(
            raw=tx.get("speech_rate_wpm"),
            normalized=None,
            available=False,
            method="120-160 WPM = 1.0; empty = unavailable",
            status="unavailable",
        ),
        "hedges": measured_value(
            raw=tx.get("hedge_count"),
            normalized=None,
            available=False,
            method="1 - min(1, count/8)",
            status="unavailable",
        ),
        "fillers": measured_value(
            raw=tx.get("filler_count"),
            normalized=None,
            available=False,
            method="1 - min(1, count/12)",
            status="unavailable",
        ),
        "pauses": measured_value(
            raw=tx.get("long_pause_count"),
            normalized=None,
            available=False,
            method="1 - min(1, long_pause_count/6); pauses >0.5s counted separately",
            status="unavailable",
        ),
        "sentence_completion": measured_value(
            raw=tx.get("sentence_completion_ratio"),
            normalized=None,
            available=False,
            method="terminal-punctuation ratio",
            status="unavailable",
        ),
        "fragmentation": measured_value(
            raw=tx.get("fragmented_sentence_count"),
            normalized=None,
            available=False,
            method="1 - min(1, fragmented_sentence_count/6)",
            status="unavailable",
        ),
    }

    if not _has_student_transcript(tx):
        coverage = transcript_coverage(word_count=word_count, duration_seconds=_duration(features, tx))
        return {
            "metric_id": "feature_complete_transcript",
            "score": None,
            "available": False,
            "status": "unavailable",
            "reason": NO_STUDENT_TRANSCRIPT,
            "coverage": coverage,
            "components": components_raw,
            "family_weights_applied": {},
            "warnings": ["Empty transcript is not scored; zero hedge/filler counts are not a perfect delivery."],
        }

    rate = speech_rate_score(tx.get("speech_rate_wpm"), word_count=word_count)
    hedges = _count_score(tx.get("hedge_count"), 8.0)
    fillers = _count_score(tx.get("filler_count"), 12.0)
    pauses = _count_score(tx.get("long_pause_count"), 6.0)
    completion = tx.get("sentence_completion_ratio")
    if completion is not None:
        completion = clamp(float(completion))
    frag_count = tx.get("fragmented_sentence_count")
    fragmentation = _count_score(frag_count, 6.0) if frag_count is not None else None

    score, applied = weighted_mean_available(
        {
            "speech_rate": rate,
            "hedges": hedges,
            "fillers": fillers,
            "pauses": pauses,
            "sentence_completion": completion,
            "fragmentation": fragmentation,
        },
        TRANSCRIPT_FEATURE_WEIGHTS,
    )
    warnings: List[str] = []
    if tx.get("sentence_completion_is_heuristic"):
        warnings.append("Sentence completion uses Whisper punctuation and is heuristic.")

    components = {
        "speech_rate": measured_value(
            raw=tx.get("speech_rate_wpm"),
            normalized=rate,
            available=rate is not None,
            method="120-160 WPM = 1.0; empty = unavailable",
        ),
        "hedges": measured_value(
            raw=tx.get("hedge_count"),
            normalized=hedges,
            available=hedges is not None,
            method="1 - min(1, count/8)",
        ),
        "fillers": measured_value(
            raw=tx.get("filler_count"),
            normalized=fillers,
            available=fillers is not None,
            method="1 - min(1, count/12)",
        ),
        "pauses": measured_value(
            raw=tx.get("long_pause_count"),
            normalized=pauses,
            available=pauses is not None,
            method="1 - min(1, long_pause_count/6); pauses >0.5s counted separately",
        ),
        "pause_count_gt_0_5s": measured_value(
            raw=tx.get("pause_count"),
            normalized=None,
            available=tx.get("pause_count") is not None,
            method="count of gaps >0.5s — diagnostic; scored pause term uses >2s only",
            status="diagnostic_only",
        ),
        "total_pause_duration": measured_value(
            raw=tx.get("total_pause_duration"),
            normalized=None,
            available=tx.get("total_pause_duration") is not None,
            method="sum of gaps >0.5s — diagnostic",
            status="diagnostic_only",
        ),
        "max_pause_duration": measured_value(
            raw=tx.get("max_pause_duration"),
            normalized=None,
            available=tx.get("max_pause_duration") is not None,
            method="max gap >0.5s — diagnostic",
            status="diagnostic_only",
        ),
        "response_structure": measured_value(
            raw=tx.get("response_structure"),
            normalized=None,
            available=False,
            method="no_validated_schema",
            status="unavailable",
        ),
        "sentence_completion": measured_value(
            raw=tx.get("sentence_completion_ratio"),
            normalized=completion,
            available=completion is not None,
            method="terminal-punctuation ratio",
        ),
        "fragmentation": measured_value(
            raw=tx.get("fragmented_sentence_count"),
            normalized=fragmentation,
            available=fragmentation is not None,
            method="1 - min(1, fragmented_sentence_count/6)",
        ),
    }
    return {
        "metric_id": "feature_complete_transcript",
        "score": None if score is None else round(float(score), 4),
        "available": score is not None,
        "status": "available" if score is not None else "unavailable",
        "reason": None,
        "coverage": transcript_coverage(word_count=word_count, duration_seconds=_duration(features, tx)),
        "components": components,
        "family_weights_applied": applied,
        "warnings": warnings,
    }


def _duration(features: Dict[str, Any], tx: Dict[str, Any]) -> Optional[float]:
    quality = features.get("quality") or {}
    raw = tx.get("duration_seconds")
    if raw is None:
        raw = quality.get("duration_seconds")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None
