"""Deterministic transcript-quality features for viva delivery analysis.

No ground-truth / reference answer required. All metrics are derived from the
student's own transcript + timestamps + audio duration.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import PAUSE_LONG_SECONDS, PAUSE_SHORT_SECONDS, SPEECH_RATE_OPTIMAL_WPM


HEDGE_PHRASES = [
    "i think",
    "i believe",
    "maybe",
    "perhaps",
    "sort of",
    "kind of",
    "i'm not sure but",
    "im not sure but",
    "i guess",
    "probably",
    "i suppose",
]

# Skip ambiguous "like" as filler for v1 (also a content word).
FILLER_WORDS = ["um", "uh", "uhh", "umm", "hmm", "er", "erm"]

_SPEECH_RATE_OPTIMAL = SPEECH_RATE_OPTIMAL_WPM
_PAUSE_SHORT_S = PAUSE_SHORT_SECONDS
_PAUSE_LONG_S = PAUSE_LONG_SECONDS


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    for quote in ("\u2019", "\u2018", "`"):
        lowered = lowered.replace(quote, "'")
    return re.sub(r"[^\w\s']+", " ", lowered)


def _word_tokens(text: str) -> List[str]:
    return [tok for tok in _normalize_text(text).split() if tok]


def _extract_timed_words(segments: Sequence[Dict[str, Any]], words_with_times: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if words_with_times:
        timed = []
        for item in words_with_times:
            word = str(item.get("word", "")).strip()
            if not word:
                continue
            try:
                start = float(item.get("start"))
                end = float(item.get("end", start))
            except (TypeError, ValueError):
                continue
            timed.append({"word": word, "start": start, "end": end})
        if timed:
            return timed

    timed = []
    for segment in segments or []:
        for item in segment.get("words") or []:
            word = str(item.get("word", "")).strip()
            if not word:
                continue
            try:
                start = float(item.get("start"))
                end = float(item.get("end", start))
            except (TypeError, ValueError):
                continue
            timed.append({"word": word, "start": start, "end": end})
    return timed


def _nearest_time(timed_words: Sequence[Dict[str, Any]], char_index: int, transcript: str) -> Optional[float]:
    if not timed_words:
        return None
    # Approximate: map character fraction → timed word index.
    if not transcript:
        return float(timed_words[0]["start"])
    ratio = max(0.0, min(1.0, char_index / max(len(transcript), 1)))
    idx = min(len(timed_words) - 1, int(round(ratio * (len(timed_words) - 1))))
    return float(timed_words[idx]["start"])


def _find_phrase_hits(
    transcript: str,
    phrases: Sequence[str],
    timed_words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    normalized = _normalize_text(transcript)
    hits: List[Dict[str, Any]] = []
    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)")
        for match in pattern.finditer(normalized):
            hits.append(
                {
                    "phrase": phrase,
                    "time": _nearest_time(timed_words, match.start(), normalized),
                }
            )
    return hits


def _find_filler_hits(
    transcript: str,
    fillers: Sequence[str],
    timed_words: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    if timed_words:
        for item in timed_words:
            token = re.sub(r"[^\w']+", "", str(item["word"]).lower())
            if token in fillers:
                hits.append({"word": token, "time": float(item["start"])})
        return hits

    normalized = _normalize_text(transcript)
    for filler in fillers:
        pattern = re.compile(rf"(?<!\w){re.escape(filler)}(?!\w)")
        for match in pattern.finditer(normalized):
            hits.append({"word": filler, "time": None})
    return hits


def _pause_stats(
    timed_words: Sequence[Dict[str, Any]],
    segments: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    gaps: List[Tuple[float, float, float]] = []
    granularity = "none"

    if len(timed_words) >= 2:
        granularity = "word"
        for i in range(len(timed_words) - 1):
            start = float(timed_words[i]["end"])
            end = float(timed_words[i + 1]["start"])
            gap = end - start
            if gap > 0:
                gaps.append((gap, start, end))
    else:
        timed_segments = []
        for segment in segments or []:
            try:
                start = float(segment.get("start"))
                end = float(segment.get("end"))
            except (TypeError, ValueError):
                continue
            timed_segments.append((start, end))
        timed_segments.sort(key=lambda item: item[0])
        if len(timed_segments) >= 2:
            granularity = "segment"
            for i in range(len(timed_segments) - 1):
                start = timed_segments[i][1]
                end = timed_segments[i + 1][0]
                gap = end - start
                if gap > 0:
                    gaps.append((gap, start, end))

    qualifying = [gap for gap, _s, _e in gaps if gap > _PAUSE_SHORT_S]
    long_pauses = [
        {"start": round(start, 2), "end": round(end, 2), "duration": round(gap, 2)}
        for gap, start, end in gaps
        if gap > _PAUSE_LONG_S
    ]
    return {
        "granularity": granularity,
        "pause_count": len(qualifying),
        "long_pause_count": len(long_pauses),
        "long_pauses": long_pauses[:30],
        "total_pause_duration": round(sum(qualifying), 2) if qualifying else 0.0,
        "max_pause_duration": round(max(qualifying), 2) if qualifying else 0.0,
    }


def _sentence_completion_ratio(transcript: str) -> Optional[float]:
    """Weak heuristic — Whisper punctuation is unreliable; flagged as such by callers."""
    text = transcript.strip()
    if not text:
        return None
    # Prefer terminal punctuation splits; fall back to whitespace chunks.
    parts = re.split(r"(?<=[.!?])\s+", text)
    if len(parts) <= 1 and " " in text:
        parts = re.split(r"\s{2,}|\n+", text) or [text]
    completed = sum(1 for part in parts if part.strip().endswith((".", "!", "?")))
    return round(completed / len(parts), 4) if parts else None


def _fragmented_sentence_count(transcript: str) -> int:
    text = (transcript or "").strip()
    if not text:
        return 0
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not parts:
        return 0
    fragmented = 0
    for part in parts:
        if part.endswith((".", "!", "?")):
            continue
        fragmented += 1
    return fragmented


def _speech_rate_band(wpm: Optional[float], word_count: int) -> Optional[str]:
    if word_count <= 0:
        return "unknown"
    if wpm is None:
        return "unknown"
    low, high = _SPEECH_RATE_OPTIMAL
    if wpm < low:
        return "too_slow"
    if wpm > high:
        return "too_fast"
    return "optimal"


def _response_structure(transcript: str, word_count: int) -> Dict[str, Any]:
    """Diagnostic only. Documented PRD item; no validated scoring schema."""
    text = (transcript or "").strip()
    if word_count <= 0 or not text:
        return {
            "status": "unavailable",
            "scored": False,
            "reason": "no_student_transcript",
            "sentence_count": 0,
            "word_count": word_count,
        }
    parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    return {
        "status": "diagnostic_only",
        "scored": False,
        "reason": "no_validated_schema",
        "sentence_count": len(parts) if parts else 1,
        "word_count": word_count,
        "has_terminal_punctuation": text.endswith((".", "!", "?")),
    }


def extract_transcript_features(
    transcript: str,
    segments: Optional[Sequence[Dict[str, Any]]] = None,
    duration_seconds: Optional[float] = None,
    words_with_times: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    transcript_text = (transcript or "").strip()
    segments = list(segments or [])
    timed_words = _extract_timed_words(segments, words_with_times)

    hedge_hits = _find_phrase_hits(transcript_text, HEDGE_PHRASES, timed_words)
    filler_hits = _find_filler_hits(transcript_text, FILLER_WORDS, timed_words)

    tokens = _word_tokens(transcript_text)
    word_count = len(tokens)
    duration = float(duration_seconds) if duration_seconds and duration_seconds > 0 else None
    speech_rate_wpm = None
    if duration and word_count > 0:
        speech_rate_wpm = round(word_count / (duration / 60.0), 2)

    pauses = _pause_stats(timed_words, segments)

    return {
        "hedge_count": len(hedge_hits),
        "hedge_phrases": hedge_hits[:50],
        "filler_count": len(filler_hits),
        "filler_words": filler_hits[:50],
        "word_count": word_count,
        "speech_rate_wpm": speech_rate_wpm,
        "speech_rate_band": _speech_rate_band(speech_rate_wpm, word_count),
        "pause_count": pauses["pause_count"],
        "long_pause_count": pauses["long_pause_count"],
        "long_pauses": pauses["long_pauses"],
        "total_pause_duration": pauses["total_pause_duration"],
        "max_pause_duration": pauses["max_pause_duration"],
        "sentence_completion_ratio": _sentence_completion_ratio(transcript_text),
        "fragmented_sentence_count": _fragmented_sentence_count(transcript_text),
        "pause_detection_granularity": pauses["granularity"],
        "sentence_completion_is_heuristic": True,
        "response_structure": _response_structure(transcript_text, word_count),
    }
