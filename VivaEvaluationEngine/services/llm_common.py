"""Shared configuration and HTTP helpers for every LLM call in the viva engine.

The judge, Q&A relevance, conversation understanding, technical accuracy and the live question
recommender all talk to the same OpenAI-compatible chat endpoint (Groq by default). They used to each
carry their own copy of the env loading, key / model / URL resolution, JSON extraction and the HTTP
POST. This module is the one place those live, so a new key name, default model or endpoint is
changed once.

Each caller keeps its own prompt, its own model-fallback loop and its own error handling.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-20b"
USER_AGENT = "GradexVivaEvaluationEngine/1.0"

# First one set wins.
BASE_URL_ENV_VARS = ("OPENAI_BASE_URL", "LLM_BASE_URL", "VIVA_LLM_BASE_URL")
API_KEY_ENV_VARS = ("VIVA_LLM_API_KEY", "GROQ_API_KEY", "AI_API_KEY", "BACKUP_API_KEY")
# The live copilot also accepts its own key, right after the shared viva key.
COPILOT_API_KEY_ENV_VARS = (
    "VIVA_LLM_API_KEY",
    "VIVA_COPILOT_API_KEY",
    "GROQ_API_KEY",
    "AI_API_KEY",
    "BACKUP_API_KEY",
)
MODEL_ENV_VARS = ("VIVA_LLM_MODEL", "GROQ_MODEL")
COPILOT_MODEL_ENV_VARS = ("VIVA_COPILOT_LLM_MODEL", "VIVA_LLM_MODEL", "GROQ_MODEL")

_ENV_LOADED = False


def load_env_files() -> None:
    """Load the local .env files (engine, then server) without needing python-dotenv.

    A value already in the process environment is never overwritten.
    """
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    engine_root = Path(__file__).resolve().parents[1]
    candidates = [
        engine_root / ".env",
        engine_root.parent / "Gradex_AI_Server" / "app" / ".env",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        except OSError:
            continue


def resolve_api_key(env_vars: Sequence[str] = API_KEY_ENV_VARS) -> Optional[str]:
    """The first non-empty key among `env_vars`, or None when no LLM key is configured."""
    load_env_files()
    for name in env_vars:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def resolve_model_name(env_vars: Sequence[str] = MODEL_ENV_VARS) -> str:
    """The first model name set among `env_vars`, else the default."""
    load_env_files()
    for name in env_vars:
        value = os.getenv(name)
        if value:
            return value
    return DEFAULT_MODEL


def chat_url() -> str:
    """The chat-completions endpoint: the configured base URL (or Groq) plus /chat/completions."""
    load_env_files()
    base = DEFAULT_BASE_URL
    for name in BASE_URL_ENV_VARS:
        value = os.getenv(name)
        if value:
            base = value
            break
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def extract_json_object(text: Optional[str]) -> Optional[Dict[str, Any]]:
    """Parse a JSON object out of an LLM reply, tolerating markdown fences and surrounding prose."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
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


def is_model_unavailable_error(exc: urllib.error.HTTPError) -> bool:
    """True when the provider rejected the model name (retired or unknown), so the next
    candidate model is worth trying. Any other HTTP error should be raised."""
    try:
        body = exc.read().decode("utf-8", errors="replace")
    except Exception:
        body = str(exc.reason or exc)
    lowered = body.lower()
    return exc.code == 404 or (
        exc.code == 400 and ("model" in lowered or "not exist" in lowered or "not found" in lowered)
    )


def post_chat_completion(
    body: Dict[str, Any],
    api_key: str,
    *,
    timeout: float,
    user_agent: str = USER_AGENT,
) -> str:
    """POST one chat-completion request and return the reply text.

    Raises urllib.error.HTTPError / URLError on transport problems and KeyError / IndexError /
    json.JSONDecodeError when the reply is not in the expected shape; callers decide what to do.
    """
    request = urllib.request.Request(
        chat_url(),
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.loads(response.read().decode("utf-8"))
    return str(raw["choices"][0]["message"]["content"])
