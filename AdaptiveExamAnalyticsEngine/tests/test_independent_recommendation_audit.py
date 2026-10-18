"""Independent audit contracts; strict xfails preserve documented baseline defects."""
import pytest

from app.services import llm_service
from app.services.recommendation import recommend_questions
from app.services.student_pipeline import _validated_insights
from app.services.teaching_actions import _validate_llm_output


def candidate(question_id="practice-1"):
    return {"question_id": question_id, "source_id": "tutorial-1",
            "source_type": "tutorial", "canonical_topic": "SQL",
            "bloom_level": "Apply", "text": "Write a SELECT query.", "marks": 5}


def test_teaching_actions_repair_numbers_and_reject_unknown_topics():
    evidence = [{"topic": "SQL", "priority": "High", "average_percentage": 40}]
    generated = [{"topic": "SQL", "priority": "Low", "performance_percentage": 100,
                  "actions": ["Review SELECT queries."]},
                 {"topic": "Unassessed topic", "actions": ["Study this."]}]
    result = _validate_llm_output(generated, evidence, None)
    assert len(result) == 1
    assert result[0]["priority"] == "High"
    assert result[0]["performance_percentage"] == 40


def test_no_observed_evidence_does_not_claim_personalized_need():
    assert recommend_questions({}, question_bank=[candidate()], reference_year=2026) == []


def test_duplicate_candidates_are_not_recommended_twice():
    document = {"canonical_topic_performance": [{"topic": "SQL", "average_percentage": 40,
        "question_count": 2, "student_count": 10}]}
    result = recommend_questions(document, question_bank=[candidate(), candidate()], reference_year=2026)
    assert len(result) == 1
    assert len({row["question_id"] for row in result}) == len(result)


def test_generated_practice_must_match_backend_target(monkeypatch):
    async def fake_validate(model, *args, **kwargs):
        return model(requested_count=5, questions=[{
            "prompt": "Explain photosynthesis.", "topic": "Botany",
            "bloom_level": "Remember", "difficulty": "Hard"}]), {}, False
    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    target = {"number_of_questions": 5, "recommended_topics": ["SQL"],
              "recommended_bloom_levels": ["Apply"], "recommended_difficulty": "Medium"}
    coroutine = llm_service.generate_practice_questions(target)
    try:
        coroutine.send(None)
    except StopIteration as completed:
        result = completed.value
    else:
        coroutine.close()
        pytest.fail("Mocked generation unexpectedly requires an event loop")
    assert result["status"] != "ok"


def test_student_insight_validation_rejects_unassessed_topics():
    from tests.test_recommendation_evidence import analysis
    _, numeric = analysis()
    result = _validated_insights({"status": "ok", "learning_gaps": ["Botany is weak"],
        "recommendations": [{"topic": "Botany", "priority": "High", "bloom_level": "Create",
                             "action": "Study photosynthesis."}],
        "generation_target": {"recommended_bloom_level": "Create", "recommended_difficulty": "Hard",
                              "recommended_topics": ["Botany"]}}, numeric)
    assert result is None


def test_learning_gaps_retain_their_original_topic_evidence():
    from tests.test_recommendation_evidence import assemble, insights
    numeric, document = assemble(insights())
    assert document["learning_analysis"]["learning_gaps"] == [
        gap.model_dump() for gap in numeric.learning_analysis.learning_gaps]
