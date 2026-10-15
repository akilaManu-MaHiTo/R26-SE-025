from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.analytics.student_document import build_numeric_analysis
from app.services import llm_service, practice_questions, student_dashboard
from app.services.recommendation import recommend_questions, recommend_for_weak_areas
from app.services.student_pipeline import _assemble_document
from tests.test_student_document_analytics import semantics, two_question_input


def ready(coroutine):
    """Mocks complete immediately; reject accidental external/event-loop work."""
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        coroutine.close()
    raise AssertionError("Unexpected pending I/O")


def analysis():
    normalized = two_question_input()
    labels = semantics()
    labels["01"] = labels["01"].model_copy(update={"topic": "SQL"})
    return normalized, build_numeric_analysis(normalized, labels)


def insights(topic="SQL", level="Apply"):
    return {"status": "ok", "learning_gaps": ["Invented gap about Botany"],
        "recommendations": [{"priority": "Low", "topic": topic, "bloom_level": level,
                             "action": "Use a worked example."}],
        "generation_target": {"recommended_bloom_level": "Create", "recommended_difficulty": "Hard",
                              "recommended_topics": ["Botany"]}}


def assemble(advice):
    normalized, numeric = analysis()
    return numeric, _assemble_document(normalized, numeric, advice,
        {"evaluation": {"grading_source": "test", "rag_context_used": False}})


def test_ai_cannot_replace_structured_gaps_or_backend_practice_target():
    numeric, document = assemble(insights())
    assert document["learning_analysis"]["learning_gaps"] == [
        gap.model_dump() for gap in numeric.learning_analysis.learning_gaps]
    assert document["next_question_strategy"] == numeric.next_question_strategy.model_dump()
    recommendation = next(r for r in document["recommendations"] if r["topic"] == "SQL")
    assert recommendation["priority"] == "Medium"  # SQL is 3/5 = Developing.
    assert "Use a worked example." in recommendation["action"]
    assert "3/5" in recommendation["action"]
    assert "01" in recommendation["action"]


@pytest.mark.parametrize("topic,level", [("Botany", "Apply"), ("SQL", "Create")])
def test_unsupported_topic_or_topic_bloom_pair_uses_evidenced_fallback(topic, level):
    _, document = assemble(insights(topic, level))
    assert all("Use a worked example." not in r["action"] for r in document["recommendations"])
    assert {r["topic"] for r in document["recommendations"]} == {"SQL", "Transaction Management"}
    assert all("Evidence:" in r["action"] for r in document["recommendations"])


def target():
    return {"recommended_topics": ["SQL"], "recommended_bloom_levels": ["Apply"],
            "recommended_difficulty": "Medium", "number_of_questions": 5}


def batch():
    return [{"prompt": f"Write SQL query for case {i}.", "topic": "SQL", "bloom_level": "Apply",
             "difficulty": "Medium", "hints": []} for i in range(5)]


@pytest.mark.parametrize("defect", ["count", "reported_count", "topic", "level", "difficulty", "duplicate"])
def test_generated_batch_rejects_target_mismatch_and_duplicate_prompts(monkeypatch, defect):
    questions = batch()
    reported = 5
    if defect == "count": questions.pop()
    if defect == "reported_count": reported = 4
    if defect == "topic": questions[0]["topic"] = "Botany"
    if defect == "level": questions[0]["bloom_level"] = "Create"
    if defect == "difficulty": questions[0]["difficulty"] = "Hard"
    if defect == "duplicate": questions[1]["prompt"] = "  WRITE SQL QUERY FOR CASE 0.  "
    async def generated(model, *args, **kwargs):
        return model(requested_count=reported, questions=questions), {}, False
    monkeypatch.setattr(llm_service, "validate_with_retry", generated)
    result = ready(llm_service.generate_practice_questions(target()))
    assert result == {"status": "degraded", "reason": "target_mismatch"}


def test_valid_generated_batch_is_accepted(monkeypatch):
    async def generated(model, *args, **kwargs):
        return model(requested_count=5, questions=batch()), {}, False
    monkeypatch.setattr(llm_service, "validate_with_retry", generated)
    assert ready(llm_service.generate_practice_questions(target())) == {"status": "ok", "questions": batch()}


def test_no_practice_target_does_not_call_the_model(monkeypatch):
    generate = AsyncMock()
    monkeypatch.setattr(llm_service, "validate_with_retry", generate)
    assert ready(llm_service.generate_practice_questions({**target(), "recommended_topics": []})) == {
        "status": "degraded", "reason": "insufficient_evidence"}
    generate.assert_not_called()


def test_invalid_generation_is_not_saved(monkeypatch):
    from app.schemas.student import NextQuestionStrategy
    questions = batch()
    questions[0]["topic"] = "Botany"
    save = AsyncMock()
    monkeypatch.setattr(practice_questions, "generate_practice_questions_call", AsyncMock(
        return_value={"status": "ok", "questions": questions}))
    monkeypatch.setattr(practice_questions, "upsert_generated_questions", save)
    result = ready(practice_questions.generate_practice_questions(object(), "S1", "IT2040", "Final",
        NextQuestionStrategy(**target())))
    assert result == {"status": "degraded", "reason": "target_mismatch"}
    save.assert_not_called()


def candidate(identifier="practice-1", topic="SQL", text="Write a JOIN query."):
    return {"question_id": identifier, "source_id": "tutorial", "source_type": "tutorial",
            "canonical_topic": topic, "bloom_level": "Apply", "text": text, "marks": 5}


def cohort():
    return {"canonical_topic_performance": [{"topic": "SQL", "average_percentage": 40,
        "question_count": 2, "student_count": 10, "status": "Needs Improvement"}]}


def test_ranked_practice_has_observed_evidence_and_no_unassessed_or_mastered_topics():
    bank = [candidate(), candidate("other", "Botany"), candidate("strong", "JDBC")]
    document = cohort()
    document["canonical_topic_performance"].append({"topic": "JDBC", "average_percentage": 100})
    result = recommend_questions(document, question_bank=bank)
    assert [r["canonical_topic"] for r in result] == ["SQL"]
    assert result[0]["reason"]["observed_average_percentage"] == 40
    assert recommend_questions({}, question_bank=bank) == []


def test_candidate_ids_and_normalized_text_are_not_repeated():
    bank = [candidate(), candidate(), candidate("copy", text=" WRITE A JOIN QUERY. ")]
    assert len(recommend_questions(cohort(), question_bank=bank)) == 1


@pytest.mark.parametrize("patch", [{"average_percentage": None}, {"average_percentage": float("nan")},
    {"question_count": 1}, {"student_count": 1}, {"question_count": None}, {"student_count": True},
    {"evidence_status": "insufficient_evidence"}])
def test_invalid_or_insufficient_cohort_evidence_does_not_produce_practice(patch):
    document = cohort()
    document["canonical_topic_performance"][0].update(patch)
    assert recommend_questions(document, question_bank=[candidate()]) == []
    assert recommend_for_weak_areas(document, question_bank=[candidate()])["recommendations"] == []


def test_mastered_or_unclassified_topics_do_not_create_a_personal_practice_target():
    normalized = two_question_input(first=(5, 5), second=(5, 5))
    labels = semantics()
    for unknown in (False, True):
        if unknown:
            labels = {key: label.model_copy(update={"topic": "Unclassified"}) for key, label in labels.items()}
            normalized = two_question_input()
        numeric = build_numeric_analysis(normalized, labels)
        document = _assemble_document(normalized, numeric, insights(),
            {"evaluation": {"grading_source": "test", "rag_context_used": False}})
        assert document["recommendations"] == []
        assert document["next_question_strategy"]["recommended_topics"] == []


def test_lost_criterion_evidence_includes_the_actual_question_and_marks():
    _, numeric = analysis()
    criterion = numeric.evidence()["weak_criteria"][0]
    assert criterion["question_id"] == "Q01"
    assert criterion["topic"] == "SQL"
    assert criterion["bloom_level"] == "Apply"
    assert (criterion["awarded_marks"], criterion["max_marks"]) == (1, 2)


def test_fallback_action_uses_the_bloom_level_observed_for_its_topic():
    normalized = two_question_input()
    labels = semantics()
    labels["01"] = labels["01"].model_copy(update={"topic": "SQL", "level": "Understand"})
    numeric = build_numeric_analysis(normalized, labels)
    action = next(r.action for r in numeric.recommendations if r.topic == "SQL")
    assert "Understand" in action
    assert "Apply" not in action  # Apply was assessed only on Transaction Management.


def test_legacy_student_cache_is_rebuilt_before_using_recommendations(monkeypatch):
    from app.schemas.student import StudentAnalyticsDocument
    from tests.test_student_dashboard_service import valid_document
    legacy = valid_document()
    legacy["analysis_version"] = "1.0"
    current = StudentAnalyticsDocument.model_validate({**deepcopy(legacy), "analysis_version": "1.1"})
    build = AsyncMock(return_value=current)
    monkeypatch.setattr(student_dashboard, "find_student_analytics", AsyncMock(return_value=legacy))
    monkeypatch.setattr(student_dashboard, "find_graded_submission", AsyncMock(return_value={"student_id": "S1"}))
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)
    monkeypatch.setattr(student_dashboard, "upsert_student_analytics", AsyncMock())
    ready(student_dashboard.ensure_student_analytics(object(), "S1", "IT2040", "Final"))
    build.assert_awaited_once()


def test_cached_practice_for_an_old_target_is_not_returned(monkeypatch):
    from types import SimpleNamespace
    from app.api import dashboard
    from app.schemas.student import NextQuestionStrategy
    cached = {"generation_version": "1.1", "request": {**target(), "recommended_topics": ["Botany"]},
              "questions": batch()}
    monkeypatch.setattr(dashboard, "find_generated_questions", AsyncMock(return_value=cached))
    monkeypatch.setattr(dashboard, "ensure_student_analytics", AsyncMock(return_value=SimpleNamespace(
        next_question_strategy=NextQuestionStrategy(**target()))))
    create = AsyncMock(return_value={"regenerated": True})
    monkeypatch.setattr(dashboard, "create_practice_questions", create)
    assert ready(dashboard.get_practice_questions("S1", "IT2040", "Final", False, object())) == {"regenerated": True}
    create.assert_awaited_once()


@pytest.mark.parametrize("duplicate", [False, True])
def test_current_practice_cache_is_revalidated_before_return(monkeypatch, duplicate):
    from types import SimpleNamespace
    from app.api import dashboard
    from app.schemas.student import NextQuestionStrategy
    questions = batch()
    if duplicate:
        questions[1] = dict(questions[0])
    cached = {"generation_version": "1.1", "request": target(), "questions": questions}
    monkeypatch.setattr(dashboard, "find_generated_questions", AsyncMock(return_value=cached))
    monkeypatch.setattr(dashboard, "ensure_student_analytics", AsyncMock(return_value=SimpleNamespace(
        next_question_strategy=NextQuestionStrategy(**target()))))
    create = AsyncMock(return_value={"regenerated": True})
    monkeypatch.setattr(dashboard, "create_practice_questions", create)
    result = ready(dashboard.get_practice_questions("S1", "IT2040", "Final", False, object()))
    assert result == ({"regenerated": True} if duplicate else cached)
    assert create.await_count == int(duplicate)
