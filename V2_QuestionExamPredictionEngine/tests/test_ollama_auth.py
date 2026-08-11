import httpx

from app.config import settings
from app.llm.ollama import generate


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request):
        return await self._handler(request)


def _capture(requests):
    async def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"response": '{"ok": true}'})

    return FakeTransport(handler)


async def test_generate_sends_bearer_header_when_key_set(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", "secret-key")
    requests: list[httpx.Request] = []
    client = httpx.AsyncClient(transport=_capture(requests))

    monkeypatch.setattr("app.llm.ollama.httpx.AsyncClient", lambda *a, **k: client)

    await generate("hello")

    assert requests
    assert requests[0].headers.get("authorization") == "Bearer secret-key"


async def test_generate_sends_no_auth_header_when_key_empty(monkeypatch):
    monkeypatch.setattr(settings, "ollama_api_key", "")
    requests: list[httpx.Request] = []
    client = httpx.AsyncClient(transport=_capture(requests))

    monkeypatch.setattr("app.llm.ollama.httpx.AsyncClient", lambda *a, **k: client)

    await generate("hello")

    assert requests
    assert "authorization" not in requests[0].headers
