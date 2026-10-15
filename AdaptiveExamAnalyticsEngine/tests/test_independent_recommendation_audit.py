"""Independent audit contracts; strict xfails preserve documented baseline defects."""
import pytest

from app.services import llm_service
from app.services.recommendation import recommend_questions
from app.services.student_pipeline import _gap_from_insight_text, _validated_insights
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


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R1: empty assessment evidence still produces practice recommendations")
def test_no_observed_evidence_does_not_claim_personalized_need():
    assert recommend_questions({}, question_bank=[candidate()], reference_year=2026) == []


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R2: duplicate bank rows are ranked twice")
def test_duplicate_candidates_are_not_recommended_twice():
    document = {"canonical_topic_performance": [{"topic": "SQL", "average_percentage": 40}]}
    result = recommend_questions(document, question_bank=[candidate(), candidate()], reference_year=2026)
    assert len({row["question_id"] for row in result}) == len(result)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R3: practice schema checks types but not requested count or target membership")
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


def test_student_insight_validation_currently_accepts_unassessed_topics():
    # Baseline characterization: schema validity is not evidence validity.
    result = _validated_insights({"status": "ok", "learning_gaps": ["Botany is weak"],
        "recommendations": [{"topic": "Botany", "priority": "High", "bloom_level": "Create",
                             "action": "Study photosynthesis."}],
        "generation_target": {"recommended_bloom_level": "Create", "recommended_difficulty": "Hard",
                              "recommended_topics": ["Botany"]}})
    assert result is not None
    assert result.generation_target.recommended_topics == ["Botany"]


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="R4: all free-text learning gaps attach to first weak topic")
def test_learning_gap_is_not_attached_to_an_unrelated_topic():
    result = _gap_from_insight_text("Review transaction isolation.", {
        "critical_topics": ["SQL"], "weak_topics": ["Transactions"],
        "overall_performance": "Needs Improvement"})
    assert result["topic"] == "Transactions"
