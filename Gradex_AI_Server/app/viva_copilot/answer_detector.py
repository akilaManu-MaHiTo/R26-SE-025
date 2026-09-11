"""Detect a completed candidate utterance. Independent of VivaEvaluationEngine."""
from __future__ import annotations

import hashlib
import re
from typing import Iterable, Optional, Sequence, Set


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


def is_near_duplicate(text: str, recent_texts: Sequence[str]) -> bool:
    """True when `text` only extends/repeats something already accepted.

    Exact hashing alone lets a growing utterance through twice: the browser
    Web Speech path and the Groq audio path finalize independently, so
    "Eat him I said" and "Eat him I said and" hash differently and both burn
    an LLM call. Prefix containment collapses that pair; a token-overlap check
    catches re-transcriptions that differ by a word or two in the middle.
    """
    normalized = normalize_answer(text)
    if not normalized:
        return True
    for previous in recent_texts:
        prior = normalize_answer(previous)
        if not prior:
            continue
        # One is a prefix/superstring of the other — the same utterance seen twice.
        if normalized.startswith(prior) or prior.startswith(normalized):
            return True
        current_tokens = set(normalized.split())
        prior_tokens = set(prior.split())
        if not current_tokens or not prior_tokens:
            continue
        overlap = len(current_tokens & prior_tokens)
        smaller = min(len(current_tokens), len(prior_tokens))
        if smaller and (overlap / smaller) >= 0.85:
            return True
    return False


def detect_final_answer(
    text: str,
    recent_hashes: Iterable[str],
    *,
    min_words: int = 5,
    recent_texts: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Return cleaned text if this is a new, long-enough utterance; else None.

    `recent_texts` enables near-duplicate rejection on top of the exact-hash
    check; omit it to keep the original hash-only behaviour.
    """
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if word_count(cleaned) < min_words:
        return None
    if is_duplicate(cleaned, recent_hashes):
        return None
    if recent_texts and is_near_duplicate(cleaned, recent_texts):
        return None
    return cleaned
