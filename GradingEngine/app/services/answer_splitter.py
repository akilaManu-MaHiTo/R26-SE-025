"""
Local regex splitter: map a full OCR transcript into per-question text buckets.
"""
from __future__ import annotations

import re


# Markers like: Question 01, Q1, Q.1, Q 1, Q I, QI, Ql, Q II, 1), 01.
# OCR often reads handwritten "1" as I, l, or |.
_QUESTION_MARKER_RE = re.compile(
    r"(?mi)"
    r"(?:^|\n)\s*"
    r"(?:"
    r"question\s*(?:no\.?|number|#)?\s*[:=\-]?\s*"
    r"(?P<q_a>0*\d+|[ivxlcdmIVXLCDM]{1,6}|[lL|])"
    r"|q(?:uestion)?\s*[.\-:]?\s*"
    r"(?P<q_b>0*\d+|[ivxlcdmIVXLCDM]{1,6}|[lL|])"
    r"|(?P<q_c>0*\d+)\s*[\)\.]"
    r")"
    r"(?![A-Za-z])"
    r"\s*"
)

_ROMAN_TO_INT = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
    "xi": 11,
    "xii": 12,
    "xiii": 13,
    "xiv": 14,
    "xv": 15,
    "xvi": 16,
    "xvii": 17,
    "xviii": 18,
    "xix": 19,
    "xx": 20,
}

# OCR.Space / pipeline noise often injected between pages or failed regions.
# Keep [OCR_ERROR]/[OCR_EMPTY] lines so empty pages are visible in review.
_OCR_JUNK_LINE_RE = re.compile(
    r"(?i)^\s*(?:"
    r"-{2,}\s*ocr\s+start\s*-{2,}"
    r"|-{2,}\s*ocr\s+end\s*-{2,}"
    r"|-{2,}\s*page\s+\d+\s*:.*"
    r"|ocr\s+start"
    r"|ocr\s+end"
    r"|\[ocr empty for .+\]"
    r"|[\.:,;=\{\}\[\]\|\-\_\*]{1,8}"
    r"|d\.?ne"
    r")\s*$"
)


def normalize_question_no(value, fallback_idx: int = 1) -> str:
    text = str(value or "").strip()
    parsed = _token_to_qno(text) if text else None
    if parsed:
        return parsed
    match = re.search(r"(\d+)", text)
    if match:
        return str(int(match.group(1))).zfill(2)
    return str(fallback_idx).zfill(2)


def _token_to_qno(token: str) -> str | None:
    """Map a marker token (digit, roman, or OCR lookalike) to 01, 02, ..."""
    raw = (token or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d+", raw):
        return str(int(raw)).zfill(2)

    # I / l / | (and repeats) are common OCR readings of 1, 11→II, etc.
    lookalike = raw.replace("|", "I").replace("l", "I").replace("L", "I")
    if re.fullmatch(r"I{1,3}", lookalike):
        return str(len(lookalike)).zfill(2)

    roman = _ROMAN_TO_INT.get(raw.lower())
    if roman is not None:
        return str(roman).zfill(2)
    return None


def clean_ocr_transcript(transcript: str) -> str:
    """
    Drop obvious OCR junk lines while preserving real answer text.
    """
    if not (transcript or "").strip():
        return ""

    cleaned_lines: list[str] = []
    for raw in transcript.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            cleaned_lines.append("")
            continue
        if _OCR_JUNK_LINE_RE.match(line):
            continue
        # Very short punctuation-only leftovers
        if re.fullmatch(r"[\W_]{1,12}", line) and not re.search(r"[A-Za-z0-9]", line):
            continue
        cleaned_lines.append(raw.rstrip())

    text = "\n".join(cleaned_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _trim_trailing_junk(chunk: str) -> str:
    """Remove trailing junk lines from a question bucket (before next Q marker)."""
    lines = chunk.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines:
        last = lines[-1].strip()
        if not last:
            lines.pop()
            continue
        if _OCR_JUNK_LINE_RE.match(last):
            lines.pop()
            continue
        if re.fullmatch(r"[\W_]{1,12}", last) and not re.search(r"[A-Za-z0-9]", last):
            lines.pop()
            continue
        break
    return "\n".join(lines).strip()


def _find_markers(transcript: str) -> list[tuple[int, str]]:
    """Return (start_index, q_no) for each detected question marker."""
    markers: list[tuple[int, str]] = []
    for match in _QUESTION_MARKER_RE.finditer(transcript or ""):
        raw = match.group("q_a") or match.group("q_b") or match.group("q_c")
        q_no = _token_to_qno(raw or "")
        if not q_no:
            continue
        markers.append((match.start(), q_no))
    return markers


def transcript_has_markers(transcript: str) -> bool:
    return bool(_find_markers(clean_ocr_transcript(transcript or "")))


def split_transcript_by_questions(
    transcript: str,
    questions: list[dict],
) -> dict[str, str]:
    """
    Split OCR text into buckets keyed by normalized question_no.

    Returns only buckets that were found via markers. Missing keys mean
    no dedicated answer was found for that question.
    """
    text = clean_ocr_transcript(transcript or "")
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
        chunk = _trim_trailing_junk(text[start:end])
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
    *,
    markers_found: bool | None = None,
) -> tuple[str, str]:
    """
    Pick answer text for one question.

    Returns (answer_text, source) where source is:
    - "split"  — regex bucket found
    - "full"   — no markers anywhere; use cleaned full transcript once
    - "empty"  — markers exist but this question has no bucket, or no text
    """
    q_no = normalize_question_no(question.get("question_no"), question_idx)
    sliced = (buckets.get(q_no) or "").strip()
    if sliced:
        return sliced, "split"

    cleaned = clean_ocr_transcript(transcript or "")
    has_markers = bool(markers_found) if markers_found is not None else bool(_find_markers(cleaned))

    # If the paper has question markers but this Q is missing, do NOT dump the whole paper.
    if has_markers:
        return "", "empty"

    if cleaned:
        return cleaned, "full"

    return "", "empty"
