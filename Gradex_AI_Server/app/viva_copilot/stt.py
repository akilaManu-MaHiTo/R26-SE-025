"""Chunked Groq Whisper STT. Isolated from VivaEvaluationEngine.transcribe."""
from __future__ import annotations

from typing import Callable, Optional

from Gradex_AI_Server.app.viva_copilot.groq_client import (
    api_key,
    groq_transcribe,
    is_probable_hallucination,
    stt_api_key,
    stt_model,
)

TranscribeFn = Callable[[bytes, str, str], str]


def _default_transcribe(audio_bytes: bytes, filename: str, content_type: str) -> str:
    key = stt_api_key() or api_key()
    if not key:
        raise RuntimeError("No STT API key configured (set AI_API_KEY, GROQ_API_KEY, or VIVA_COPILOT_STT_API_KEY)")
    return groq_transcribe(
        audio_bytes,
        filename,
        content_type,
        api_key_value=key,
        model=stt_model(),
    )


def transcribe_chunk(
    audio_bytes: bytes,
    *,
    filename: str = "chunk.webm",
    content_type: str = "audio/webm",
    transcribe: Optional[TranscribeFn] = None,
) -> str:
    fn = transcribe or _default_transcribe
    text = (fn(audio_bytes, filename, content_type) or "").strip()
    if is_probable_hallucination(text):
        return ""
    return text
