import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class OllamaUnavailable(Exception):
    pass


async def generate(prompt: str, *, temperature: float | None = None) -> dict:
    url = f"{settings.ollama_base_url}/api/generate"
    body = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
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
            if attempt == max_attempts - 1:
                return None, raw, True
            prompt = f"{prompt}\nYour previous JSON did not match this schema: {exc}. Retry and output ONLY valid JSON matching the schema."
        except OllamaUnavailable:
            raise
    return None, raw, True
