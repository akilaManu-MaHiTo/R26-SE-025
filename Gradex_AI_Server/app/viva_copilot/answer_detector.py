"""Detect a completed candidate utterance. Independent of VivaEvaluationEngine."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional, Set


def normalize_answer(text: str) -> str:
    lowered = (text or "").lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def answer_hash(text: str) -> str:
    normalized = normalize_answer(text)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def word_count(text: str) -> int:
    return len(normalize_answer(text).split()) if normalize_answer(text) else 0


def is_duplicate(text: str, recent_hashes: Iterable[str]) -> bool:
    digest = answer_hash(text)
    if not digest:
        return True
    recent: Set[str] = set(recent_hashes)
    return digest in recent


def detect_final_answer(
    text: str,
    recent_hashes: Iterable[str],
    *,
    min_words: int = 5,
) -> Optional[str]:
    """Return cleaned text if this is a new, long-enough utterance; else None."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if word_count(cleaned) < min_words:
        return None
    if is_duplicate(cleaned, recent_hashes):
        return None
    return cleaned
