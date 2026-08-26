"""Standalone Groq HTTP helpers for the copilot only.

Does not import VivaEvaluationEngine.llm_judge or any grading pipeline.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError

import httpx
from dotenv import load_dotenv

_ENV_LOADED = False

# Persistent, connection-pooled HTTP client. Reused across every STT and chat
# call so the TCP + TLS handshake with Groq only happens once instead of on
# every request (this alone shaves ~100-300ms off each call).
_HTTP_CLIENT: Optional[httpx.Client] = None
_HTTP_CLIENT_LOCK = threading.Lock()


def _http_client() -> httpx.Client:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None:
        with _HTTP_CLIENT_LOCK:
            if _HTTP_CLIENT is None:
                _HTTP_CLIENT = httpx.Client(
                    http2=False,
                    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
                    timeout=httpx.Timeout(30.0, connect=5.0),
                )
    return _HTTP_CLIENT

def _chat_url() -> str:
    _load_env()
    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("VIVA_LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _transcribe_url(api_key_override: Optional[str] = None) -> str:
    _load_env()
    explicit_stt_base = os.getenv("VIVA_COPILOT_STT_BASE_URL") or os.getenv("STT_BASE_URL")
    if explicit_stt_base:
        base = explicit_stt_base.rstrip("/")
        if base.endswith("/audio/transcriptions"):
            return base
        return f"{base}/audio/transcriptions"

    # If the active STT API key is a Groq key (starts with 'gsk_'), route directly to Groq Whisper
    active_key = api_key_override or stt_api_key() or ""
    if active_key.startswith("gsk_"):
        return "https://api.groq.com/openai/v1/audio/transcriptions"

    base = (os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL") or os.getenv("VIVA_LLM_BASE_URL") or "https://api.groq.com/openai/v1").rstrip("/")
    if base.endswith("/audio/transcriptions"):
        return base
    return f"{base}/audio/transcriptions"


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


def stt_api_key() -> Optional[str]:
    _load_env()
    for name in (
        "VIVA_COPILOT_STT_API_KEY",
        "STT_API_KEY",
        "GROQ_API_KEY",
        "AI_API_KEY",
        "VIVA_COPILOT_API_KEY",
        "VIVA_LLM_API_KEY",
        "BACKUP_API_KEY",
    ):
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


def _min_stt_gap() -> float:
    _load_env()
    try:
        return float(os.getenv("VIVA_COPILOT_MIN_STT_GAP", "0.4"))
    except ValueError:
        return 0.4


def friendly_groq_error(detail: str, *, kind: str = "Groq") -> str:
    lowered = (detail or "").lower()
    if "no credentials for provider" in lowered:
        return (
            f"{kind} failed: AI gateway does not have credentials configured for this provider. "
            "Set VIVA_COPILOT_STT_API_KEY or GROQ_API_KEY (gsk_...) to route Whisper directly to Groq."
        )
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


def groq_chat(
    system_prompt: str,
    user_payload: Dict[str, Any],
    *,
    api_key_value: str,
    model: str,
    timeout: int = 25,
    on_delta: Optional[Callable[[str], None]] = None,
) -> str:
    """Call the chat completion endpoint.

    When ``on_delta`` is provided the request is made with ``stream=True`` and
    the callback is invoked with each incremental content fragment as it
    arrives from Groq (SSE). This lets callers surface a suggestion the
    moment it becomes parseable instead of waiting for the whole response.
    The full assembled content is always returned.
    """
    last_error: Optional[Exception] = None
    models = [model] if model else []
    for fallback in chat_model_fallbacks():
        if fallback not in models:
            models.append(fallback)

    client = _http_client()
    headers = {
        "Authorization": f"Bearer {api_key_value}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "GradexVivaCopilot/1.0",
    }

    for candidate in models:
        stream_mode = on_delta is not None
        body = {
            "model": candidate,
            "temperature": 0.3,
            "stream": stream_mode,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        }
        try:
            if stream_mode:
                content_parts: List[str] = []
                got_any = False
                with client.stream(
                    "POST", _chat_url(), json=body, headers=headers, timeout=timeout
                ) as response:
                    if response.status_code >= 400:
                        raw = response.read()
                        detail = raw.decode("utf-8", errors="replace")
                        exc = httpx.HTTPStatusError(
                            "chat failed", request=response.request, response=response
                        )
                        exc._gradex_status = response.status_code  # type: ignore[attr-defined]
                        exc._gradex_detail = detail  # type: ignore[attr-defined]
                        raise exc
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices") or []
                        if not choices:
                            continue
                        delta = ((choices[0].get("delta") or {}).get("content")) or ""
                        if delta:
                            got_any = True
                            content_parts.append(delta)
                            on_delta(delta)
                content = "".join(content_parts)
                if not got_any or not content.strip():
                    last_error = RuntimeError("Groq chat returned empty content")
                    continue
                return content
            else:
                response = client.post(_chat_url(), json=body, headers=headers, timeout=timeout)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            status_code = getattr(exc, "_gradex_status", exc.response.status_code)
            detail = getattr(exc, "_gradex_detail", None)
            if detail is None:
                try:
                    detail = exc.response.text
                except Exception:
                    detail = str(exc)
            last_error = RuntimeError(friendly_groq_error(detail, kind="Follow-up generation"))
            if status_code == 404 or (
                status_code == 400 and ("model" in detail.lower() or "not exist" in detail.lower())
            ):
                continue
            raise last_error from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Groq chat unreachable: {exc}") from exc

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

    client = _http_client()

    def _once() -> str:
        files = {
            "file": (filename or "chunk.webm", audio_bytes, content_type or "audio/webm"),
        }
        data = {"model": model, "response_format": "json"}
        response = client.post(
            _transcribe_url(api_key_value),
            data=data,
            files=files,
            headers={
                "Authorization": f"Bearer {api_key_value}",
                "User-Agent": "GradexVivaCopilot/1.0",
            },
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return str(payload.get("text") or "").strip()

    global _LAST_STT_AT
    with _STT_LOCK:
        wait = _min_stt_gap() - (time.monotonic() - _LAST_STT_AT)
        if wait > 0:
            time.sleep(wait)
        try:
            text = _once()
            _LAST_STT_AT = time.monotonic()
            return text
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            status_code = exc.response.status_code
            _LAST_STT_AT = time.monotonic()
            if status_code == 429:
                time.sleep(4.0)
                try:
                    text = _once()
                    _LAST_STT_AT = time.monotonic()
                    return text
                except httpx.HTTPStatusError as retry_exc:
                    retry_detail = retry_exc.response.text
                    _LAST_STT_AT = time.monotonic()
                    raise RuntimeError(friendly_groq_error(retry_detail, kind="Speech recognition")) from retry_exc
            raise RuntimeError(friendly_groq_error(detail, kind="Speech recognition")) from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Groq STT unreachable: {exc}") from exc


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
