import json

import httpx
import pytest

from app.services import llm_service


@pytest.mark.parametrize("source_text", ["SQL joins combine related rows. " * 100, "\x00" * 3100])
async def test_grounded_prompt_is_bounded_and_uses_constrained_structured_output(monkeypatch, source_text):
    captured = {}
    async def validate(schema, prompt, **kwargs):
        captured.update(prompt=prompt, **kwargs)
        return None, {}, True
    monkeypatch.setattr(llm_service, "validate_with_retry", validate)
    result = await llm_service.generate_candidates({
        "course_code": "IT2040", "topic": "SQL", "bloom_level": "Apply", "mark_range": [10, 10],
        "learning_outcomes": "Apply SQL joins. " * 300,
        "sources": [{"source_id": f"lecture-{n}", "kind": "lecture", "text": source_text} for n in range(4)],
        "assessment_examples": [{"source_id": "tutorial-1", "kind": "tutorial", "text": "Example question " * 100}],
        "historical_questions": [{"question_id": f"old-{n}", "question_text": "Historical SQL query " * 100} for n in range(20)],
    }, count=2)
    assert len(captured["prompt"]) <= 12000
    assert captured["generation_options"] == {"num_ctx": 8192, "num_predict": 1280}
    schema = captured["response_schema"]
    candidates = schema["properties"]["candidates"]
    assert candidates["minItems"] == candidates["maxItems"] == 2
    properties = schema["$defs"]["GroundedCandidate"]["properties"]
    assert properties["topic"]["const"] == "SQL"
    assert properties["marks"]["const"] == 10
    assert "tutorial-1" not in properties["source_ids"]["items"]["enum"]
    assert result["context_truncated"] is True


async def test_transport_sends_schema_and_generation_options(monkeypatch):
    from app.llm.ollama import generate
    requests = []
    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"response": '{"ok":true}'})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr("app.llm.ollama.httpx.AsyncClient", lambda **kwargs: client)
    schema = {"type": "object", "properties": {"ok": {"const": True}}}
    result = await generate("test", response_schema=schema, generation_options={"num_ctx": 8192, "num_predict": 1280})
    assert result == {"ok": True}
    assert requests[0]["format"] == schema
    assert requests[0]["options"]["num_predict"] == 1280
    assert requests[0]["options"]["num_ctx"] == 8192
