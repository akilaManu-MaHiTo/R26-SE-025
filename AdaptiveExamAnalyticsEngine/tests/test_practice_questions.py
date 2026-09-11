from unittest.mock import AsyncMock

from app.services import practice_questions


async def test_generate_practice_questions_caches_document(monkeypatch):
    from app.schemas.student import NextQuestionStrategy

    strategy = NextQuestionStrategy(recommended_topics=["SQL"], recommended_bloom_levels=["Understand"], recommended_difficulty="Medium", number_of_questions=5)
    gen = AsyncMock(return_value={"status": "ok", "questions": [{"prompt": "p", "bloom_level": "Understand", "topic": "SQL", "difficulty": "Medium", "hints": []}]})
    save = AsyncMock()
    monkeypatch.setattr(practice_questions, "generate_practice_questions_call", gen)
    monkeypatch.setattr(practice_questions, "upsert_generated_questions", save)

    result = await practice_questions.generate_practice_questions(object(), "IT22145976", "IT2040", "Final Examination 2021", strategy)

    assert result["status"] == "ok"
    save.assert_awaited_once()


async def test_generate_practice_questions_degrades_when_qwen_down(monkeypatch):
    from app.schemas.student import NextQuestionStrategy

    strategy = NextQuestionStrategy(recommended_topics=["SQL"], recommended_bloom_levels=["Understand"], recommended_difficulty="Medium", number_of_questions=5)
    gen = AsyncMock(return_value={"status": "degraded", "reason": "ollama_unavailable"})
    monkeypatch.setattr(practice_questions, "generate_practice_questions_call", gen)

    result = await practice_questions.generate_practice_questions(object(), "IT22145976", "IT2040", "Final Examination 2021", strategy)

    assert result == {"status": "degraded", "reason": "ollama_unavailable"}
