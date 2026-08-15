"""Deterministic transcript-quality features for viva delivery analysis.

No ground-truth / reference answer required. All metrics are derived from the
student's own transcript + timestamps + audio duration.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple


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

_SPEECH_RATE_OPTIMAL = (120.0, 160.0)
_PAUSE_SHORT_S = 0.5
_PAUSE_LONG_S = 2.0


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
) -> Tuple[str, int, int, List[Dict[str, float]]]:
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

    pause_count = sum(1 for gap, _s, _e in gaps if gap > _PAUSE_SHORT_S)
    long_pauses = [
        {"start": round(start, 2), "end": round(end, 2)}
        for gap, start, end in gaps
        if gap > _PAUSE_LONG_S
    ]
    return granularity, pause_count, len(long_pauses), long_pauses


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


def _speech_rate_band(wpm: Optional[float]) -> Optional[str]:
    if wpm is None:
        return None
    low, high = _SPEECH_RATE_OPTIMAL
    if wpm < low:
        return "too_slow"
    if wpm > high:
        return "too_fast"
    return "optimal"


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
    speech_rate_wpm = round(word_count / (duration / 60.0), 2) if duration else None

    granularity, pause_count, long_pause_count, long_pauses = _pause_stats(timed_words, segments)

    return {
        "hedge_count": len(hedge_hits),
        "hedge_phrases": hedge_hits[:50],
        "filler_count": len(filler_hits),
        "filler_words": filler_hits[:50],
        "word_count": word_count,
        "speech_rate_wpm": speech_rate_wpm,
        "speech_rate_band": _speech_rate_band(speech_rate_wpm),
        "pause_count": pause_count,
        "long_pause_count": long_pause_count,
        "long_pauses": long_pauses[:30],
        "sentence_completion_ratio": _sentence_completion_ratio(transcript_text),
        "pause_detection_granularity": granularity,
        "sentence_completion_is_heuristic": True,
    }
