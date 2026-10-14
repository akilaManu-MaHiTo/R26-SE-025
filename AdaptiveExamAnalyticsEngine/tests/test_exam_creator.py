"""Creator contracts: no live model or database needed."""
import httpx
import pytest
from pydantic import ValidationError

from app.main import app
from app.services import recommendation


def row(id, topic="SQL", bloom="Apply", source="tutorial", year=2025):
    return dict(question_id=id, source_id=id, canonical_topic=topic,
                bloom_level=bloom, source_type=source, year=year, marks=10,
                text=f"Write a query for {id}")


def request(**blueprint):
    from app.schemas.exam_creator import CreatorRequest
    return CreatorRequest.model_validate({
        "course_code": "IT2040", "paper": {"exam": "DBMS", "year": 2026,
        "questions": [], "blueprint": {"total_marks": 20, **blueprint}}})


def test_generated_questions_are_not_evidence_of_practice():
    signals = recommendation._compute_signals([row("g", source="generated")])
    assert signals["tutorial_counts"].get("SQL", 0) == 0


def test_recent_window_excludes_old_and_future_exams():
    signals = recommendation._compute_signals([
        row("old", source="exam", year=2023), row("recent", source="exam", year=2025),
        row("future", source="exam", year=2027)], reference_year=2026)
    assert signals["exam_recent_counts"] == {"SQL": 1}


def test_course_bank_isolation():
    from app.services.exam_creator import course_bank
    bank = [row("IT2040_2025_1"), row("SE9999_2025_1"), row("unknown")]
    assert [r["question_id"] for r in course_bank("IT2040", bank)] == ["IT2040_2025_1"]
    assert course_bank("IT2040", [{**row("GEN_1"), "course_code": "IT2040"}])


def test_draft_aware_ranking_excludes_used_and_filled_topics():
    from app.services.exam_creator import review_paper
    req = request(topic_marks={"SQL": 10, "Design": 10})
    req.paper.questions = [{"question_number": 1, "topic": "SQL", "parts": [
        {"part": "a", "question": "Write a query for used", "max_marks": 10,
         "question_id": "used", "bloom_level": "Apply"}]}]
    result = review_paper(req, {}, [row("used"), row("sql"), row("design", topic="Design")])
    assert [r["question_id"] for r in result["recommendations"]] == ["design"]
    assert result["review"]["remaining_marks"] == 10
    assert result["review"]["topic_coverage"]["Design"]["remaining"] == 10


def test_review_detects_duplicates_unknown_bloom_and_missing_answers():
    from app.services.exam_creator import review_paper
    req = request()
    req.paper.questions = [{"question_number": 1, "topic": "SQL", "parts": [
        {"part": "a", "question": "Same question", "max_marks": 10},
        {"part": "b", "question": " same   QUESTION ", "max_marks": 10}]}]
    result = review_paper(req, {}, [])
    codes = {issue["code"] for issue in result["review"]["issues"]}
    assert {"duplicate", "bloom_missing", "answer_missing"} <= codes


def test_unmarked_tutorial_remains_available_for_lecturer_allocation():
    from app.services.exam_creator import review_paper
    result = review_paper(request(topic_marks={"SQL": 20}), {}, [{**row("tutorial"), "marks": 0}])
    assert result["recommendations"][0]["question_id"] == "tutorial"
    assert result["recommendations"][0]["requires_marks"] is True
    assert result["recommendations"][0]["max_available_marks"] == 20


def test_recommendation_keeps_long_question_and_supporting_data():
    text = "Question and supporting table. " * 100
    result = recommendation.recommend_questions({}, question_bank=[{**row("long"), "text": text}])
    assert result[0]["text"] == text


@pytest.mark.parametrize("blueprint", [
    {"total_marks": -1}, {"bloom_percentages": {"Apply": 110}},
    {"bloom_percentages": {"Wrong": 100}}, {"topic_marks": {"SQL": -5}},
    {"topic_marks": {"SQL": 30}}, {"duration_minutes": 0}])
def test_invalid_blueprint_rejected(blueprint):
    with pytest.raises(ValidationError):
        request(**blueprint)


async def test_generate_endpoint_requires_sources(monkeypatch):
    monkeypatch.setattr(recommendation, "_load_question_bank", lambda: [])
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/lecturers/exam-creator/generate", json={
            **request().model_dump(), "topic": "SQL", "bloom_level": "Apply", "marks": 10})
    assert response.status_code == 422
    assert "source" in response.json()["detail"].lower()


async def test_generate_endpoint_reports_ollama_timeout(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "ollama_timeout", 240)
    monkeypatch.setattr(recommendation, "_load_question_bank", lambda: [])

    async def timed_out(*args, **kwargs):
        raise httpx.ReadTimeout("", request=httpx.Request("POST", "http://ollama/api/generate"))

    monkeypatch.setattr(httpx.AsyncClient, "post", timed_out)
    # Keep the API request real; only the external Ollama call times out.
    from app.api.lecturer import generate_exam_creator
    from app.schemas.exam_creator import GenerateRequest
    from fastapi import HTTPException
    payload = GenerateRequest.model_validate({
        **request(lecture_notes="SQL joins combine related rows.").model_dump(),
        "topic": "SQL", "bloom_level": "Apply", "marks": 10})
    with pytest.raises(HTTPException) as error:
        await generate_exam_creator(payload)
    assert error.value.status_code == 503
    assert "240" in error.value.detail
    assert "timed out" in error.value.detail.lower()
    assert "OLLAMA_TIMEOUT" in error.value.detail


async def test_generation_uses_sources_and_validates_rubric(monkeypatch):
    from app.services import exam_creator, llm_service
    from app.schemas.exam_creator import GenerateRequest
    captured = {}

    async def fake_validate(schema, prompt, **kwargs):
        captured["prompt"] = prompt
        return schema.model_validate({"candidates": [{
            "text": "Write a join query using Student(id) and Enrolment(student_id).",
            "topic": "SQL", "bloom_level": "Apply", "marks": 10,
            "model_answer": "SELECT * FROM Student s JOIN Enrolment e ON s.id=e.student_id",
            "marking_scheme": [{"criterion": "Join condition", "marks": 10}],
            "estimated_minutes": 12, "source_ids": ["lecturer-notes"]}]}), {}, False

    monkeypatch.setattr(llm_service, "validate_with_retry", fake_validate)
    monkeypatch.setattr(llm_service, "is_embedding_available", lambda: False)
    req = GenerateRequest.model_validate({**request(lecture_notes="Joins combine related rows.").model_dump(),
                                         "topic": "SQL", "bloom_level": "Apply", "marks": 10, "count": 1})
    result = await exam_creator.generate_for_paper(req, [])
    assert "Joins combine related rows." in captured["prompt"]
    assert result["candidates"][0]["sources"][0]["source_id"] == "lecturer-notes"
    assert result["candidates"][0]["review_status"] == "needs_review"
    assert result["similarity_available"] is False


async def test_generation_rejects_hallucinated_source_and_wrong_marks(monkeypatch):
    from app.services import exam_creator, llm_service
    from app.schemas.exam_creator import GenerateRequest

    async def fake_generate(*args, **kwargs):
        return {"status": "ok", "candidates": [{"text": "Question", "topic": "SQL",
            "bloom_level": "Apply", "marks": 99, "source_ids": ["invented"],
            "model_answer": "answer", "marking_scheme": [{"criterion": "answer", "marks": 99}],
            "estimated_minutes": 5}], "similarity_checks": []}

    monkeypatch.setattr(llm_service, "generate_candidates", fake_generate)
    req = GenerateRequest.model_validate({**request(lecture_notes="Lecture notes").model_dump(),
                                         "topic": "SQL", "bloom_level": "Apply", "marks": 10, "count": 1})
    result = await exam_creator.generate_for_paper(req, [])
    assert result["status"] == "degraded"
    assert result["candidates"] == []


def test_draft_keeps_blueprint_and_source_exam():
    from app.api.lecturer import ExamDraftPaper
    data = request().paper.model_dump()
    paper = ExamDraftPaper.model_validate(data)
    assert paper.model_dump()["blueprint"]["total_marks"] == 20


@pytest.mark.parametrize("part", [
    {"question": "q", "max_marks": 5, "model_answer": None},
    {"question": "q", "max_marks": 5, "bloom_level": []},
    {"question": "q", "max_marks": 5, "estimated_minutes": float("inf")},
    {"question": "q", "max_marks": 5, "marking_scheme": [{"criterion": "x", "marks": "bad"}]},
])
def test_malformed_part_metadata_is_rejected(part):
    from app.schemas.exam_creator import CreatorPaper
    with pytest.raises(ValidationError):
        CreatorPaper.model_validate({"exam": "DBMS", "year": 2026, "questions": [
            {"question_number": 1, "topic": "SQL", "parts": [part]}]})


async def test_review_endpoint_scopes_bank_and_uses_saved_source(monkeypatch):
    from app.api import lecturer
    captured = []

    async def fake_find(db, *args):
        captured.extend(args)
        return {"topic_performance": []}

    monkeypatch.setattr(lecturer, "find_exam_analytics", fake_find)
    monkeypatch.setattr(recommendation, "_load_question_bank", lambda: [
        row("IT2040_2025_1"), row("SE9999_2025_1", topic="Other course")])
    payload = request().model_dump()
    payload["paper"]["source_exam"] = {"session_name": "Midterm", "year": 2025, "month": 8, "semester": 2}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/lecturers/exam-creator/review", json=payload)
    assert response.status_code == 200
    assert captured == ["IT2040", "Midterm", 2025, 8, 2]
    assert response.json()["topics"] == ["SQL"]


def test_rubric_total_is_enforced():
    from app.schemas.exam_creator import GroundedCandidate
    with pytest.raises(ValidationError, match="Marking scheme"):
        GroundedCandidate.model_validate({"text": "Question", "topic": "SQL", "bloom_level": "Apply",
            "marks": 10, "model_answer": "Answer", "source_ids": ["notes"], "estimated_minutes": 5,
            "marking_scheme": [{"criterion": "Correct answer", "marks": 3}]})


async def test_draft_api_round_trip_preserves_blueprint_and_review_metadata():
    from copy import deepcopy
    from app.api import deps

    class DraftCollection:
        document = None

        async def find_one(self, query, projection):
            return deepcopy(self.document)

        async def replace_one(self, query, document, upsert):
            self.document = deepcopy(document)

    collection = DraftCollection()
    app.dependency_overrides[deps.get_db] = lambda: {"exam_drafts": collection}
    try:
        paper = request(lecture_notes="Course source text", learning_outcomes="Apply joins").paper.model_dump()
        paper["rejected_questions"] = [{"question_id": "old", "reason": "Already assessed"}]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            saved = await client.post("/api/lecturers/exams/drafts", json={"subject_code": "IT2040", "paper": paper})
            assert saved.status_code == 200
            draft_id = saved.json()["draft_id"]
            loaded = await client.get(f"/api/lecturers/exams/drafts/{draft_id}")
            assert loaded.json()["paper"] == paper
            assert loaded.json()["total_marks"] == 0
            paper["questions"] = [{"question_number": 1, "topic": "SQL", "parts": [{
                "part": "a", "question": "Write a join", "max_marks": 10, "bloom_level": "Apply",
                "model_answer": "SELECT ...", "marking_scheme": [{"criterion": "Join", "marks": 10}],
                "sources": [{"source_id": "notes", "kind": "lecture_notes", "text": "Course source text"}],
                "review_status": "approved"}]}]
            updated = await client.post("/api/lecturers/exams/drafts", json={"subject_code": "IT2040", "paper": paper, "draft_id": draft_id})
            assert updated.status_code == 200
            loaded = await client.get(f"/api/lecturers/exams/drafts/{draft_id}")
            assert loaded.json()["paper"] == paper
            assert loaded.json()["created_at"] == saved.json()["created_at"]
    finally:
        app.dependency_overrides.clear()
