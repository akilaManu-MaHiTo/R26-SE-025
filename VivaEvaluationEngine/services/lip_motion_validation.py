"""Lip-motion checks for viva validity — isolated from other engines.

When speech is detected, lip movement on the on-camera face should scale with
how much was said. Default: at least one visible lip-motion event per five
transcript words (1/5). Example: 20 spoken words → minimum 4 lip motions.
"""
from __future__ import annotations

import math
import os
from typing import Any, Dict, Iterable, Optional

# Match gaze_head_analyser.GazeHeadAnalyser talking threshold.
MOUTH_TALKING_THRESHOLD = 0.32
MOUTH_DELTA_MIN = 0.04

# One lip-motion event per N transcript words (1/5 by default).
DEFAULT_WORDS_PER_LIP_EVENT = 5
MINIMUM_LIP_EVENTS = 1


def _words_per_lip_event() -> int:
    raw = (os.getenv("VIVA_LIP_WORDS_PER_EVENT") or "").strip()
    if not raw:
        return DEFAULT_WORDS_PER_LIP_EVENT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_WORDS_PER_LIP_EVENT
    return max(1, value)


def _speech_word_count(result: Dict[str, Any]) -> int:
    audio = result.get("audio_analysis") or {}
    transcript = audio.get("transcript_features") or {}
    for key in ("transcript_word_count", "word_count"):
        raw = audio.get(key) if key == "transcript_word_count" else transcript.get(key)
        if raw is not None:
            try:
                return int(raw)
            except (TypeError, ValueError):
                continue
    return 0


def _speech_requires_lip_motion(result: Dict[str, Any]) -> bool:
    """True when transcript evidence exists and should be lip-sync checked."""
    audio = result.get("audio_analysis") or {}
    status = str(audio.get("status") or "")
    if status == "failed":
        return False
    degraded = list(audio.get("degraded_reasons") or [])
    if "transcript_unavailable" in degraded:
        return False
    words = _speech_word_count(result)
    return words > 2


def _iter_mouth_samples(result: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    face_cues = result.get("face_cues")
    if isinstance(face_cues, list) and face_cues:
        for item in face_cues:
            if isinstance(item, dict):
                yield item
        return
    timeline = result.get("timeline") or []
    for item in timeline:
        if isinstance(item, dict):
            yield item


def _required_event_count(word_count: int, words_per_event: int) -> int:
    if word_count <= 0:
        return MINIMUM_LIP_EVENTS
    return max(MINIMUM_LIP_EVENTS, math.ceil(word_count / words_per_event))


def summarize_lip_motion(result: Dict[str, Any]) -> Dict[str, Any]:
    words_per_event = _words_per_lip_event()
    word_count = _speech_word_count(result)
    samples = sorted(
        list(_iter_mouth_samples(result)),
        key=lambda item: float(item.get("time") or 0.0),
    )

    talking_frames = 0
    open_transitions = 0
    mouth_delta_moves = 0
    mouth_samples = 0
    valid_samples = 0
    prev_talking = False
    prev_open: Optional[float] = None

    for sample in samples:
        if sample.get("valid") is False:
            continue
        valid_samples += 1

        mouth_raw = sample.get("mouth_open")
        talking = bool(sample.get("talking"))
        if mouth_raw is not None:
            try:
                mouth_open = float(mouth_raw)
            except (TypeError, ValueError):
                mouth_open = None
            else:
                mouth_samples += 1
                if mouth_open >= MOUTH_TALKING_THRESHOLD:
                    talking = True
                if prev_open is not None and abs(mouth_open - prev_open) >= MOUTH_DELTA_MIN:
                    mouth_delta_moves += 1
                prev_open = mouth_open

        if talking:
            talking_frames += 1
        if talking and not prev_talking:
            open_transitions += 1
        prev_talking = talking

    motion_events = max(open_transitions, talking_frames)
    required = _required_event_count(word_count, words_per_event)
    speech_requires = _speech_requires_lip_motion(result)
    track_available = valid_samples > 0 and mouth_samples > 0

    if not speech_requires:
        passed = True
    elif not track_available:
        passed = False
        unavailable = True
    else:
        unavailable = False
        passed = motion_events >= required

    return {
        "available": track_available,
        "track_unavailable": not track_available and speech_requires,
        "speech_requires_lips": speech_requires,
        "transcript_word_count": word_count,
        "words_per_lip_event": words_per_event,
        "lip_ratio": f"1/{words_per_event}",
        "talking_frames": talking_frames,
        "open_transitions": open_transitions,
        "mouth_delta_moves": mouth_delta_moves,
        "motion_events": motion_events,
        "minimum_required": required,
        "valid_face_samples": valid_samples,
        "passed": passed,
    }


def classify_lip_motion_evidence(result: Dict[str, Any]) -> Optional[str]:
    summary = summarize_lip_motion(result)
    if not summary.get("speech_requires_lips"):
        return None
    if summary.get("track_unavailable"):
        return "lip_motion_unavailable"
    if not summary.get("passed"):
        return "insufficient_lip_motion"
    return None
