"""
Local regex splitter: map a full OCR transcript into per-question text buckets.
"""
from __future__ import annotations

import re


# Markers like: Question 01, Q1, Q.1, Q 1, 1), 01.
_QUESTION_MARKER_RE = re.compile(
    r"(?mi)"
    r"(?:^|\n)\s*"
    r"(?:"
    r"question\s*(?:no\.?|number|#)?\s*[:=\-]?\s*0*(\d+)"
    r"|q(?:uestion)?\s*[.\-:]?\s*0*(\d+)"
    r"|0*(\d+)\s*[\)\.]"
    r")"
    r"\s*"
)


def normalize_question_no(value, fallback_idx: int = 1) -> str:
    text = str(value or "").strip()
    match = re.search(r"(\d+)", text)
    if match:
        return str(int(match.group(1))).zfill(2)
    return str(fallback_idx).zfill(2)


def _find_markers(transcript: str) -> list[tuple[int, str]]:
    """Return (start_index, q_no) for each detected question marker."""
    markers: list[tuple[int, str]] = []
    for match in _QUESTION_MARKER_RE.finditer(transcript or ""):
        raw = match.group(1) or match.group(2) or match.group(3)
        if not raw:
            continue
        q_no = str(int(raw)).zfill(2)
        markers.append((match.start(), q_no))
    return markers


def split_transcript_by_questions(
    transcript: str,
    questions: list[dict],
) -> dict[str, str]:
    """
    Split OCR text into buckets keyed by normalized question_no.

    Returns only buckets that were found via markers. Missing keys mean
    the caller should fall back (e.g. use full transcript for that question).
    """
    text = (transcript or "").strip()
    if not text:
        return {}

    markers = _find_markers(text)
    if not markers:
        return {}

    # Keep first occurrence of each q_no in document order
    seen: set[str] = set()
    ordered: list[tuple[int, str]] = []
    for start, q_no in markers:
        if q_no in seen:
            continue
        seen.add(q_no)
        ordered.append((start, q_no))

    if not ordered:
        return {}

    buckets: dict[str, str] = {}
    for idx, (start, q_no) in enumerate(ordered):
        end = ordered[idx + 1][0] if idx + 1 < len(ordered) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            buckets[q_no] = chunk

    # If rubric questions are provided, only keep known question numbers
    if questions:
        allowed = {
            normalize_question_no(q.get("question_no"), idx)
            for idx, q in enumerate(questions, start=1)
            if isinstance(q, dict)
        }
        if allowed:
            buckets = {k: v for k, v in buckets.items() if k in allowed}

    return buckets


def resolve_answer_for_question(
    transcript: str,
    question: dict,
    buckets: dict[str, str],
    question_idx: int,
) -> tuple[str, str]:
    """
    Pick answer text for one question.

    Returns (answer_text, source) where source is:
    - "split"  — regex bucket found
    - "full"   — fell back to full transcript
    - "empty"  — no usable text
    """
    q_no = normalize_question_no(question.get("question_no"), question_idx)
    sliced = (buckets.get(q_no) or "").strip()
    if sliced:
        return sliced, "split"

    full = (transcript or "").strip()
    if full:
        return full, "full"

    return "", "empty"
