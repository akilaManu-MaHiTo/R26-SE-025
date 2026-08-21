"""Standalone Groq HTTP helpers for the copilot only.

Does not import VivaEvaluationEngine.llm_judge or any grading pipeline.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

_ENV_LOADED = False

CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
TRANSCRIBE_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

_HALLUCINATIONS = frozenset(
    {
        "thank you",
        "thanks for watching",
        "you",
        "the",
        "subtitle",
        "subtitles by",
        "please subscribe",
        "bye",
    }
)


def _load_env() -> None:
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(dotenv_path=env_path)


def api_key() -> Optional[str]:
    _load_env()
    for name in ("VIVA_COPILOT_API_KEY", "VIVA_LLM_API_KEY", "GROQ_API_KEY", "AI_API_KEY", "BACKUP_API_KEY"):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def chat_model() -> str:
    _load_env()
    return os.getenv("VIVA_COPILOT_LLM_MODEL") or "openai/gpt-oss-20b"


def chat_model_fallbacks() -> List[str]:
    preferred = chat_model()
    extras = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.6-27b",
    ]
    seen = set()
    ordered: List[str] = []
    for name in [preferred, *extras]:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def stt_model() -> str:
    _load_env()
    return os.getenv("VIVA_COPILOT_STT_MODEL") or "whisper-large-v3-turbo"


_STT_LOCK = threading.Lock()
_LAST_STT_AT = 0.0
_MIN_STT_GAP = 4.0


def friendly_groq_error(detail: str, *, kind: str = "Groq") -> str:
    lowered = (detail or "").lower()
    if "rate_limit" in lowered or "rate limit" in lowered:
        return (
            "Groq rate limit hit. Waiting a few seconds between speech slices "
            "(free tier allows about 20 transcriptions per minute)."
        )
    if "model_not_found" in lowered or "does not exist" in lowered:
        return (
            "The configured Groq chat model is not available on this API key. "
            "The copilot will try a fallback model automatically."
        )
    if "invalid api key" in lowered or "unauthorized" in lowered:
        return "Groq API key was rejected. Check AI_API_KEY / GROQ_API_KEY in Gradex_AI_Server/app/.env."
    compact = re.sub(r"\s+", " ", detail or "").strip()
    if len(compact) > 180:
        compact = compact[:177] + "..."
    return f"{kind} failed: {compact}" if compact else f"{kind} failed."


def _read_http_error(exc: HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return str(exc.reason or exc)


def extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def groq_chat(system_prompt: str, user_payload: Dict[str, Any], *, api_key_value: str, model: str, timeout: int = 25) -> str:
    last_error: Optional[Exception] = None
    models = [model] if model else []
    for fallback in chat_model_fallbacks():
        if fallback not in models:
            models.append(fallback)

    for candidate in models:
        body = {
            "model": candidate,
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        request = Request(
            CHAT_URL,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key_value}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "GradexVivaCopilot/1.0",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = _read_http_error(exc)
            last_error = RuntimeError(friendly_groq_error(detail, kind="Follow-up generation"))
            if exc.code == 404 or (
                exc.code == 400 and ("model" in detail.lower() or "not exist" in detail.lower())
            ):
                continue
            raise last_error from exc
        except URLError as exc:
            raise RuntimeError(f"Groq chat unreachable: {exc.reason}") from exc

        choices = payload.get("choices") or []
        if not choices:
            last_error = RuntimeError("Groq chat returned no choices")
            continue
        content = ((choices[0].get("message") or {}).get("content")) or ""
        if not isinstance(content, str) or not content.strip():
            last_error = RuntimeError("Groq chat returned empty content")
            continue
        return content

    raise last_error or RuntimeError("Groq chat failed")


def groq_transcribe(audio_bytes: bytes, filename: str, content_type: str, *, api_key_value: str, model: str, timeout: int = 30) -> str:
    if not audio_bytes or len(audio_bytes) < 800:
        return ""

    def _once() -> str:
        boundary = "----GradexCopilot" + uuid.uuid4().hex
        chunks = []

        def add_field(name: str, value: str) -> None:
            chunks.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        def add_file(name: str, file_name: str, data: bytes, mime: str) -> None:
            header = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{file_name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode("utf-8")
            chunks.append(header + data + b"\r\n")

        add_field("model", model)
        add_field("response_format", "json")
        add_file("file", filename or "chunk.webm", audio_bytes, content_type or "audio/webm")
        chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
        body = b"".join(chunks)

        request = Request(
            TRANSCRIBE_URL,
            data=body,
            headers={
                "Authorization": f"Bearer {api_key_value}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "GradexVivaCopilot/1.0",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload.get("text") or "").strip()

    global _LAST_STT_AT
    with _STT_LOCK:
        wait = _MIN_STT_GAP - (time.monotonic() - _LAST_STT_AT)
        if wait > 0:
            time.sleep(wait)
        try:
            text = _once()
            _LAST_STT_AT = time.monotonic()
            return text
        except HTTPError as exc:
            detail = _read_http_error(exc)
            _LAST_STT_AT = time.monotonic()
            if exc.code == 429:
                time.sleep(4.0)
                try:
                    text = _once()
                    _LAST_STT_AT = time.monotonic()
                    return text
                except HTTPError as retry_exc:
                    retry_detail = _read_http_error(retry_exc)
                    _LAST_STT_AT = time.monotonic()
                    raise RuntimeError(friendly_groq_error(retry_detail, kind="Speech recognition")) from retry_exc
            raise RuntimeError(friendly_groq_error(detail, kind="Speech recognition")) from exc
        except URLError as exc:
            raise RuntimeError(f"Groq STT unreachable: {exc.reason}") from exc


def is_probable_hallucination(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    normalized = re.sub(r"[^a-z0-9\s]", "", normalized).strip()
    if not normalized:
        return True
    if normalized in _HALLUCINATIONS:
        return True
    if "subtitle" in normalized or "subscribe to" in normalized:
        return True
    return False
