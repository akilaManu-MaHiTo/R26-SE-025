import httpx
import pydantic
import pytest
from pytest import MonkeyPatch

from app.llm.ollama import OllamaUnavailable, generate, validate_with_retry
from app.config import settings


class FakeResponse(httpx.Response):
    pass


def _fake_json_response(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


async def test_generate_returns_response_json(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        return _fake_json_response({"response": '{"primary_topic": "SQL"}'})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    result = await generate("classify this")
    assert result["primary_topic"] == "SQL"


async def test_generate_raises_on_network_error(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    with pytest.raises(OllamaUnavailable):
        await generate("classify this")


class FakeSchema(pydantic.BaseModel):
    topic: str


async def test_validate_with_retry_succeeds_on_second_attempt(monkeypatch: MonkeyPatch):
    calls = {"n": 0}

    async def fake_post(*args, **kwargs):
        calls["n"] += 1
        payload = {"topic": "SQL"} if calls["n"] > 1 else {"wrong_field": "x"}
        return _fake_json_response({"response": __import__("json").dumps(payload)})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    parsed, raw, review = await validate_with_retry(FakeSchema, "prompt", temperature=0.2)
    assert calls["n"] == 2
    assert parsed is not None and parsed.topic == "SQL"
    assert review is False


async def test_validate_with_retry_flags_review_after_two_failures(monkeypatch: MonkeyPatch):
    async def fake_post(*args, **kwargs):
        return _fake_json_response({"response": '{"wrong_field": "x"}'})

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    parsed, raw, review = await validate_with_retry(FakeSchema, "prompt", temperature=0.2)
    assert parsed is None
    assert review is True