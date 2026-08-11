import pytest

from app.llm.ollama import OllamaUnavailable
from app.services import llm_service
from app.services.llm_service import (
    classify_question,
    classify_question_semantics,
    generate_candidates,
    generate_student_insights,
    misconception_summary,
    study_actions,
)


def test_high_confidence_rules_skips_qwen(monkeypatch):
    async def fail(*a, **k):
        raise AssertionError("Ollama should not be called")

    monkeypatch.setattr(llm_service, "validate_with_retry", fail)
    result = classify_question("Write a SQL SELECT that joins two tables.")
    assert result["status"] == "rules"


def test_low_confidence_calls_qwen_and_succeeds(monkeypatch):
    class FakeClassification:
        primary_topic = "SQL"
        bloom_level = "Apply"
        question_type = "coding"
        key_concepts = []
        rationale = "x"
        review_flag = False

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeClassification(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = classify_question("Discuss the history of computing.")
    assert result["status"] == "qwen"
    assert result["qwen"]["primary_topic"] == "SQL"


def test_qwen_down_degrades_to_rules(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = classify_question("Discuss the history of computing.")
    assert result["status"] == "rules_degraded"
    assert result["reason"] == "ollama_unavailable"


async def test_misconception_summary_degraded_on_unavailable(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = await misconception_summary("SQL", [], ["answer..."])
    assert result["status"] == "degraded"
    assert result["reason"] == "ollama_unavailable"


async def test_generate_candidates_ok_skips_similarity_when_embeddings_off(monkeypatch):
    from app.llm.roles.generate import CandidateQuestions

    class FakeCandidates:
        def __init__(self):
            self.candidates = [
                type("C", (), {"model_dump": lambda self: {"text": "q", "topic": "SQL"}})()
            ]

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeCandidates(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    monkeypatch.setattr(llm_service, "is_embedding_available", lambda: False)
    result = await generate_candidates({"topic": "SQL", "bloom_level": "Apply", "mark_range": (1, 4)})
    assert result["status"] == "ok"
    assert result["similarity_checks"] == []


async def test_classify_question_from_running_loop_does_not_crash(monkeypatch):
    class FakeClassification:
        primary_topic = "SQL"
        bloom_level = "Apply"
        question_type = "coding"
        key_concepts = []
        rationale = "x"
        review_flag = False

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeClassification(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = classify_question("Discuss the history of computing.")
    assert result["status"] == "qwen"
    assert result["qwen"]["primary_topic"] == "SQL"


async def test_study_actions_ok(monkeypatch):
    class FakeActions:
        def model_dump(self):
            return {
                "student_key": "stu-001",
                "actions": [{"action": "review", "topic": "SQL", "rationale": "r", "practice_topics": ["joins"]}],
            }

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        return FakeActions(), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = await study_actions("stu-001", ["SQL"], {})
    assert result["status"] == "ok"
    assert result["student_key"] == "stu-001"


async def test_study_actions_degraded_on_unavailable(monkeypatch):
    async def raise_unavailable(*a, **k):
        raise OllamaUnavailable("down")

    monkeypatch.setattr(llm_service, "validate_with_retry", raise_unavailable)
    result = await study_actions("stu-001", ["SQL"], {})
    assert result["status"] == "degraded"
    assert result["reason"] == "ollama_unavailable"


async def test_classify_question_semantics_prompt_embeds_schema(monkeypatch):
    captured: dict = {}

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        captured["prompt"] = prompt
        return None, {}, True

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = await classify_question_semantics(
        {"code": "IT2040", "name": "DBMS"},
        "Explain the differences between Conceptual, Logical, and Physical Database Design.",
        ["Explains Conceptual Design", "Explains Logical Design"],
    )
    assert result["status"] == "degraded"
    assert result["reason"] == "schema_failure"
    prompt = captured["prompt"]
    assert '"level"' in prompt
    assert '"topic"' in prompt
    assert '"subtopic"' in prompt
    assert '"confidence"' in prompt
    assert '"reason"' in prompt


async def test_generate_student_insights_prompt_embeds_schema(monkeypatch):
    captured: dict = {}

    async def fake_validate(schema, prompt, temperature, max_attempts=2):
        captured["prompt"] = prompt
        return None, {}, True

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = await generate_student_insights("IT21001234", {"topic": "SQL"})
    assert result["status"] == "degraded"
    assert result["reason"] == "schema_failure"
    prompt = captured["prompt"]
    assert '"learning_gaps"' in prompt
    assert '"recommendations"' in prompt
    assert '"generation_target"' in prompt
    assert "Example output" in prompt
    assert '"recommended_bloom_level"' in prompt