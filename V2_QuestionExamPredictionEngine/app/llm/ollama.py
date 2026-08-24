import json
import logging
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class OllamaUnavailable(Exception):
    pass


async def check_llm_health(timeout: float = 10.0) -> tuple[bool, str]:
    """Probe the configured LLM endpoint; returns (healthy, detail)."""
    url = f"{settings.llm_base_url}/api/version"
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if response.status_code == 200:
        return True, "ok"
    return False, f"HTTP {response.status_code}"


async def check_llm_detailed_health(timeout: float = 10.0) -> dict:
    """Check both Ollama reachability and model availability.

    Returns dict with:
      online: bool (ollama reachable && model available)
      ollama_reachable: bool
      model: str
      model_available: bool
      detail: str
    """
    model = settings.llm_model
    ollama_reachable, detail = await check_llm_health(timeout=timeout)
    if not ollama_reachable:
        return {
            "online": False,
            "ollama_reachable": False,
            "model": model,
            "model_available": False,
            "detail": detail,
        }
    # Ollama is reachable — check if the configured model is pulled
    url = f"{settings.llm_base_url}/api/tags"
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        return {
            "online": False,
            "ollama_reachable": True,
            "model": model,
            "model_available": False,
            "detail": f"tags check failed: {type(exc).__name__}: {exc}",
        }
    if resp.status_code != 200:
        return {
            "online": False,
            "ollama_reachable": True,
            "model": model,
            "model_available": False,
            "detail": f"tags HTTP {resp.status_code}",
        }
    try:
        data = resp.json()
        models = data.get("models") or []
        # model names in tags are like "qwen2.5:3b-instruct" or "qwen2.5:3b-instruct:latest"
        available_names = {m.get("name", "") for m in models if isinstance(m, dict)}
        # also consider base name without tag
        model_base = model.split(":")[0]
        model_available = any(
            name == model or name.startswith(model + ":") or name.split(":")[0] == model_base and model in name
            or model_base == name.split(":")[0] and model.split(":")[0] == name.split(":")[0] and (model == name or name.startswith(model))
            for name in available_names
        )
        # simpler exact or prefix check
        if not model_available:
            # fallback: check if any available name matches requested model exactly or with :latest
            model_available = model in available_names or f"{model}:latest" in available_names
            # also allow partial: if requested is "qwen2.5:3b-instruct" and available is "qwen2.5:3b-instruct" it's true
            if not model_available:
                for avail in available_names:
                    if avail == model or avail.startswith(model + ":"):
                        model_available = True
                        break
        if model_available:
            return {
                "online": True,
                "ollama_reachable": True,
                "model": model,
                "model_available": True,
                "detail": "ok",
            }
        return {
            "online": False,
            "ollama_reachable": True,
            "model": model,
            "model_available": False,
            "detail": f"model '{model}' not found. Available: {', '.join(sorted(available_names)[:5]) or 'none'}",
        }
    except Exception as exc:
        return {
            "online": False,
            "ollama_reachable": True,
            "model": model,
            "model_available": False,
            "detail": f"tags parse error: {exc}",
        }


async def generate(prompt: str, *, temperature: float | None = None) -> dict:
    url = f"{settings.llm_base_url}/api/generate"
    body = {
        "model": settings.llm_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "think": False,
        "options": {
            "temperature": settings.ollama_classify_temperature if temperature is None else temperature,
            "num_predict": 2048,
        },
    }
    headers = {}
    if settings.ollama_api_key:
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
            response = await client.post(url, json=body, headers=headers)
            if response.status_code >= 400:
                raise OllamaUnavailable(f"Ollama returned HTTP {response.status_code}")
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaUnavailable(str(exc)) from exc
    try:
        return json.loads(data.get("response", "{}"))
    except json.JSONDecodeError as exc:
        raise OllamaUnavailable(f"invalid JSON from model: {exc}") from exc


async def validate_with_retry(
    schema: type[T],
    prompt: str,
    temperature: float,
    max_attempts: int = 2,
) -> tuple[T | None, dict | None, bool]:
    raw: dict | None = None
    for attempt in range(max_attempts):
        try:
            raw = await generate(prompt, temperature=temperature)
            return schema.model_validate(raw), raw, False
        except ValidationError as exc:
            logger.error(
                "LLM output failed %s schema validation (attempt %d): %s\nraw=%s",
                schema.__name__,
                attempt + 1,
                exc,
                json.dumps(raw, ensure_ascii=False),
            )
            if attempt == max_attempts - 1:
                return None, raw, True
            prompt = f"{prompt}\nYour previous JSON did not match this schema: {exc}. Retry and output ONLY valid JSON matching the schema."
        except OllamaUnavailable:
            raise
    return None, raw, True
