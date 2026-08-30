"""LLM/STT HTTP helpers for the copilot only.

Chat completion is a multi-provider free-tier chain (no local gateway):

    Groq  ->  Gemini  ->  OpenRouter (free models)

Every candidate model of a provider is tried before moving to the next
provider. STT stays on Groq Whisper (the only free, already-integrated
speech-to-text option) -- chat provider failures never affect STT.

Does not import VivaEvaluationEngine.llm_judge or any grading pipeline.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.error import HTTPError

import httpx
from dotenv import load_dotenv

_ENV_LOADED = False

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


def _transcribe_url(api_key_override: Optional[str] = None) -> str:
    _load_env()
    explicit_stt_base = os.getenv("VIVA_COPILOT_STT_BASE_URL") or os.getenv("STT_BASE_URL")
    if explicit_stt_base:
        base = explicit_stt_base.rstrip("/")
        if base.endswith("/audio/transcriptions"):
            return base
        return f"{base}/audio/transcriptions"
    return "https://api.groq.com/openai/v1/audio/transcriptions"


_HALLUCINATIONS = frozenset(
    {
        "thank you", "thanks for watching", "you", "the",
        "subtitle", "subtitles by", "please subscribe", "bye",
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
    """Legacy single-key lookup, kept for STT and callers that just need *a* key."""
    _load_env()
    for name in (
        "VIVA_COPILOT_API_KEY", "VIVA_LLM_API_KEY", "GROQ_API_KEY",
        "AI_API_KEY", "GEMINI_API_KEY", "OPENROUTER_API_KEY", "BACKUP_API_KEY",
    ):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def stt_api_key() -> Optional[str]:
    _load_env()
    for name in (
        "VIVA_COPILOT_STT_API_KEY", "STT_API_KEY", "GROQ_API_KEY",
        "AI_API_KEY", "VIVA_COPILOT_API_KEY", "VIVA_LLM_API_KEY", "BACKUP_API_KEY",
    ):
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def chat_model() -> str:
    _load_env()
    return os.getenv("VIVA_COPILOT_LLM_MODEL") or "openai/gpt-oss-20b"


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
    if "rate_limit" in lowered or "rate limit" in lowered or "resource_exhausted" in lowered:
        return (
            "Rate limit hit on the current AI provider. The copilot will try the next "
            "free-tier provider (Groq -> Gemini -> OpenRouter) automatically."
        )
    if "model_not_found" in lowered or "does not exist" in lowered:
        return (
            "The configured chat model is not available on this API key. "
            "The copilot will try a fallback model/provider automatically."
        )
    if "invalid api key" in lowered or "unauthorized" in lowered or "api_key_invalid" in lowered:
        return f"{kind} API key was rejected. Check the relevant key in Gradex_AI_Server/app/.env."
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


# --------------------------------------------------------------------------
# Multi-provider chat chain: Groq -> Gemini -> OpenRouter (free tier)
# --------------------------------------------------------------------------


@dataclass
class _Provider:
    name: str
    key_env_vars: tuple
    models: List[str]
    kind: str = "openai"  # "openai" | "gemini"
    base_url: str = ""
    extra_headers: Dict[str, str] = field(default_factory=dict)

    def resolve_key(self) -> Optional[str]:
        for name in self.key_env_vars:
            value = os.getenv(name)
            if value and value.strip():
                return value.strip()
        return None


def _providers() -> List["_Provider"]:
    _load_env()
    preferred = chat_model()
    groq_models = _dedupe([preferred, "openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.6-27b"])
    gemini_models = _dedupe([os.getenv("GEMINI_MODEL") or "", "gemini-2.0-flash", "gemini-1.5-flash"])
    openrouter_models = _dedupe([
        os.getenv("OPENROUTER_MODEL") or "",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemma-2-9b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ])
    return [
        _Provider(
            name="Groq",
            key_env_vars=("VIVA_COPILOT_API_KEY", "VIVA_LLM_API_KEY", "GROQ_API_KEY", "AI_API_KEY", "BACKUP_API_KEY"),
            models=groq_models,
            kind="openai",
            base_url="https://api.groq.com/openai/v1/chat/completions",
        ),
        _Provider(
            name="Gemini",
            key_env_vars=("GEMINI_API_KEY", "GOOGLE_API_KEY"),
            models=gemini_models,
            kind="gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/models",
        ),
        _Provider(
            name="OpenRouter",
            key_env_vars=("OPENROUTER_API_KEY",),
            models=openrouter_models,
            kind="openai",
            base_url="https://openrouter.ai/api/v1/chat/completions",
            extra_headers={"HTTP-Referer": "https://gradex.local", "X-Title": "Gradex Viva Copilot"},
        ),
    ]


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def chat_model_fallbacks() -> List[str]:
    """Backwards-compatible: Groq model candidates only (used by older tests)."""
    for provider in _providers():
        if provider.name == "Groq":
            return provider.models
    return [chat_model()]


def _openai_body(system_prompt: str, user_payload: Dict[str, Any], model: str, stream: bool) -> Dict[str, Any]:
    return {
        "model": model, "temperature": 0.3, "stream": stream,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    }


def _call_openai_compatible(
    provider: "_Provider", model: str, system_prompt: str, user_payload: Dict[str, Any],
    *, api_key_value: str, timeout: int, on_delta: Optional[Callable[[str], None]],
) -> str:
    client = _http_client()
    headers = {
        "Authorization": f"Bearer {api_key_value}",
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "GradexVivaCopilot/1.0", **provider.extra_headers,
    }
    stream_mode = on_delta is not None
    body = _openai_body(system_prompt, user_payload, model, stream_mode)
    if stream_mode:
        content_parts: List[str] = []
        with client.stream("POST", provider.base_url, json=body, headers=headers, timeout=timeout) as response:
            if response.status_code >= 400:
                raw = response.read()
                detail = raw.decode("utf-8", errors="replace")
                exc = httpx.HTTPStatusError("chat failed", request=response.request, response=response)
                exc._gradex_status = response.status_code  # type: ignore[attr-defined]
                exc._gradex_detail = detail  # type: ignore[attr-defined]
                raise exc
            for line in response.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
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
                    content_parts.append(delta)
                    on_delta(delta)
        return "".join(content_parts)
    response = client.post(provider.base_url, json=body, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError(f"{provider.name} chat returned no choices")
    content = ((choices[0].get("message") or {}).get("content")) or ""
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{provider.name} chat returned empty content")
    return content


def _call_gemini(
    provider: "_Provider", model: str, system_prompt: str, user_payload: Dict[str, Any],
    *, api_key_value: str, timeout: int, on_delta: Optional[Callable[[str], None]],
) -> str:
    client = _http_client()
    url = f"{provider.base_url}/{model}:generateContent?key={api_key_value}"
    body = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": json.dumps(user_payload, ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0.3, "responseMimeType": "application/json"},
    }
    headers = {"Content-Type": "application/json", "User-Agent": "GradexVivaCopilot/1.0"}
    response = client.post(url, json=body, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = ((candidates[0].get("content") or {}).get("parts")) or []
    content = "".join(str(part.get("text") or "") for part in parts)
    if not content.strip():
        raise RuntimeError("Gemini returned empty content")
    if on_delta is not None:
        on_delta(content)
    return content


def groq_chat(
    system_prompt: str, user_payload: Dict[str, Any], *,
    api_key_value: Optional[str] = None, model: Optional[str] = None,
    timeout: int = 25, on_delta: Optional[Callable[[str], None]] = None,
) -> str:
    """Call the chat completion chain: Groq -> Gemini -> OpenRouter.

    ``api_key_value``/``model`` are accepted for backwards compatibility with
    existing callers (``followup_llm._default_chat``) but the actual key and
    model used are resolved per-provider from env. When every provider/model
    candidate fails, the last error is raised.
    """
    last_error: Optional[Exception] = None
    for provider in _providers():
        key = provider.resolve_key()
        if not key:
            continue
        candidates = provider.models
        if not candidates:
            continue
        for candidate in candidates:
            try:
                if provider.kind == "gemini":
                    return _call_gemini(
                        provider, candidate, system_prompt, user_payload,
                        api_key_value=key, timeout=timeout, on_delta=on_delta,
                    )
                return _call_openai_compatible(
                    provider, candidate, system_prompt, user_payload,
                    api_key_value=key, timeout=timeout, on_delta=on_delta,
                )
            except httpx.HTTPStatusError as exc:
                status_code = getattr(exc, "_gradex_status", exc.response.status_code)
                detail = getattr(exc, "_gradex_detail", None)
                if detail is None:
                    try:
                        detail = exc.response.text
                    except Exception:
                        detail = str(exc)
                last_error = RuntimeError(
                    friendly_groq_error(detail, kind=f"{provider.name} follow-up generation")
                )
                if status_code in (400, 401, 403, 404, 429) or status_code >= 500:
                    continue
                raise last_error from exc
            except httpx.HTTPError as exc:
                last_error = RuntimeError(f"{provider.name} chat unreachable: {exc}")
                continue
            except RuntimeError as exc:
                last_error = exc
                continue
    raise last_error or RuntimeError(
        "No AI provider configured or all providers failed "
        "(set GROQ_API_KEY / AI_API_KEY, GEMINI_API_KEY, or OPENROUTER_API_KEY)"
    )


def groq_transcribe(
    audio_bytes: bytes, filename: str, content_type: str, *,
    api_key_value: str, model: str, timeout: int = 30,
) -> str:
    if not audio_bytes or len(audio_bytes) < 800:
        return ""
    client = _http_client()

    def _once() -> str:
        files = {"file": (filename or "chunk.webm", audio_bytes, content_type or "audio/webm")}
        data = {"model": model, "response_format": "json"}
        response = client.post(
            _transcribe_url(api_key_value), data=data, files=files,
            headers={"Authorization": f"Bearer {api_key_value}", "User-Agent": "GradexVivaCopilot/1.0"},
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
                    raise RuntimeError(
                        friendly_groq_error(retry_detail, kind="Speech recognition")
                    ) from retry_exc
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
