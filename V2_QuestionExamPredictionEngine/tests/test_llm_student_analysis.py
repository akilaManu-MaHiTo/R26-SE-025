from pydantic import ValidationError
import pytest

from app.llm.ollama import OllamaUnavailable
from app.llm.roles.student_analysis import (
    QuestionSemantics,
    StudentInsightResponse,
)
from app.services import llm_service


async def test_classify_question_semantics_returns_validated_fields(monkeypatch):
    captured = {}

    async def fake_validate(model, prompt, temperature):
        captured.update(model=model, prompt=prompt, temperature=temperature)
        return model(
            level="Understand",
            topic="Concurrency Control",
            subtopic="Two-Phase Locking",
            confidence=0.94,
            reason="The question asks for an explanation.",
        ), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    result = await llm_service.classify_question_semantics(
        {"code": "SE3040", "name": "Software Architecture"},
        "Explain two-phase locking.",
        ["Mentions growing phase"],
    )

    assert result["status"] == "ok"
    assert result["semantics"]["subtopic"] == "Two-Phase Locking"
    assert captured["model"] is QuestionSemantics
    assert "SE3040" in captured["prompt"]
    assert "Software Architecture" in captured["prompt"]
    assert "Explain two-phase locking." in captured["prompt"]
    assert "Mentions growing phase" in captured["prompt"]


async def test_classify_question_semantics_degrades_when_qwen_is_unavailable(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise OllamaUnavailable("offline")

    monkeypatch.setattr(llm_service, "validate_with_retry", unavailable)
    result = await llm_service.classify_question_semantics(
        {"code": "IT2040", "name": "Database Management Systems"},
        "Explain two-phase locking.",
        [],
    )

    assert result == {"status": "degraded", "reason": "ollama_unavailable"}


def test_student_insight_schema_accepts_semantics_and_priorities_without_scores():
    insight = StudentInsightResponse(
        learning_gaps=["Needs practice applying transaction isolation concepts"],
        recommendations=[
            {
                "priority": "High",
                "topic": "Concurrency Control",
                "bloom_level": "Apply",
                "action": "Practice transaction schedule analysis.",
            }
        ],
        generation_target={
            "recommended_bloom_level": "Apply",
            "recommended_difficulty": "Medium",
            "recommended_topics": ["Concurrency Control"],
        },
    )

    assert insight.recommendations[0].priority == "High"
    schema_text = str(StudentInsightResponse.model_json_schema()).lower()
    for forbidden in ("score", "percentage", "marks", "average"):
        assert forbidden not in schema_text


def test_student_insight_schema_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        StudentInsightResponse(
            learning_gaps=[],
            recommendations=[
                {
                    "priority": "Urgent",
                    "topic": "Transactions",
                    "bloom_level": "Understand",
                    "action": "Review isolation levels.",
                }
            ],
            generation_target={
                "recommended_bloom_level": "Understand",
                "recommended_difficulty": "Easy",
                "recommended_topics": ["Transactions"],
            },
        )


async def test_generate_student_insights_returns_validated_response(monkeypatch):
    captured = {}

    async def fake_validate(model, prompt, temperature):
        captured.update(model=model, prompt=prompt, temperature=temperature)
        return model(
            learning_gaps=["Struggles to apply locking rules"],
            recommendations=[
                {
                    "priority": "High",
                    "topic": "Concurrency Control",
                    "bloom_level": "Apply",
                    "action": "Trace two-phase locking schedules.",
                }
            ],
            generation_target={
                "recommended_bloom_level": "Apply",
                "recommended_difficulty": "Medium",
                "recommended_topics": ["Concurrency Control"],
            },
        ), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    evidence = {
        "weak_topics": ["Concurrency Control"],
        "weak_bloom_levels": ["Apply"],
    }
    result = await llm_service.generate_student_insights("student-17", evidence)

    assert result["status"] == "ok"
    assert result["learning_gaps"] == ["Struggles to apply locking rules"]
    assert result["recommendations"][0]["priority"] == "High"
    assert captured["model"] is StudentInsightResponse
    assert "student-17" in captured["prompt"]
    assert "Concurrency Control" in captured["prompt"]
    assert "authoritative" in captured["prompt"].lower()
    assert "no numeric performance calculations" in captured["prompt"].lower()


async def test_generate_student_insights_degrades_on_schema_failure(monkeypatch):
    async def invalid_response(model, prompt, temperature):
        return None, {"learning_gaps": "invalid"}, True

    monkeypatch.setattr(llm_service, "validate_with_retry", invalid_response)
    result = await llm_service.generate_student_insights("student-17", {})

    assert result["status"] == "degraded"
    assert result["reason"] == "schema_failure"


async def test_generate_student_insights_degrades_when_qwen_is_unavailable(monkeypatch):
    async def unavailable(*args, **kwargs):
        raise OllamaUnavailable("offline")

    monkeypatch.setattr(llm_service, "validate_with_retry", unavailable)
    result = await llm_service.generate_student_insights("student-17", {})

    assert result == {"status": "degraded", "reason": "ollama_unavailable"}
