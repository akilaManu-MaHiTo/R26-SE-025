"""Real retrieval with a mocked generator; academic quality needs a live model review."""
import httpx
import pytest

from app.schemas.exam_creator import GenerateRequest
from app.services import exam_creator, llm_service
from tests.test_course_rag import pdf


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    from app.config import settings
    from app.services.course_rag import CourseRag
    monkeypatch.setattr(settings, "course_rag_index", str(tmp_path / "index.sqlite3"))
    monkeypatch.setattr(settings, "embedding_available", False)
    rag = CourseRag(settings.course_rag_index, semantic=False)
    for kind, text in [("lecture", "Normalization removes redundant data and update anomalies."),
                       ("tutorial", "Explain normalization using the supplied functional dependencies."),
                       ("exam", "Decompose a relation into third normal form using normalization.")]:
        rag.index_pdf(pdf(tmp_path / f"{kind}.pdf", text), "IT2040", kind, year=2024)
    return rag


def request(notes=""):
    return GenerateRequest.model_validate({"course_code": "IT2040", "topic": "normalization",
        "bloom_level": "Apply", "marks": 10, "count": 1,
        "paper": {"exam": "DBMS", "year": 2026, "questions": [], "blueprint": {"lecture_notes": notes}}})


def fake_candidate(source_id):
    return {"text": "For Enrolment(student, module, title), with module determining title, propose a decomposition.",
        "topic": "normalization", "bloom_level": "Apply", "marks": 10,
        "model_answer": "Split into Module(module, title) and Enrolment(student, module).",
        "marking_scheme": [{"criterion": "Valid decomposition", "marks": 10}],
        "estimated_minutes": 12, "source_ids": [source_id]}


async def test_creator_uses_lecture_evidence_and_separate_assessment_examples(corpus, monkeypatch):
    captured = {}
    async def generate(recommendation, count):
        captured.update(recommendation)
        return {"status": "ok", "candidates": [fake_candidate(recommendation["sources"][0]["source_id"])]}
    monkeypatch.setattr(llm_service, "generate_candidates", generate)
    result = await exam_creator.generate_for_paper(request(), [])
    assert result["status"] == "ok"
    assert result["retrieval"]["lectures"]["mode"] == "keyword"
    assert {s["kind"] for s in captured["sources"]} == {"lecture"}
    assert {s["kind"] for s in captured["assessment_examples"]} == {"tutorial", "exam"}
    assert {h["question_id"] for h in captured["historical_questions"]} >= {
        s["source_id"] for s in captured["assessment_examples"]}
    source = result["candidates"][0]["sources"][0]
    assert source["filename"] == "lecture.pdf" and source["page_number"] == 1
    assert source["course_code"] == "IT2040"


async def test_pasted_notes_first_context_bounded_and_missing_index_visible(tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "course_rag_index", str(tmp_path / "absent.sqlite3"))
    captured = {}
    async def generate(recommendation, count):
        captured.update(recommendation)
        return {"status": "ok", "candidates": [fake_candidate("lecturer-notes")]}
    monkeypatch.setattr(llm_service, "generate_candidates", generate)
    bank = [{"source_type": "lecture", "canonical_topic": "normalization", "text": "Evidence " * 1000,
             "question_id": f"objective{i}"} for i in range(8)]
    result = await exam_creator.generate_for_paper(request("N" * 20000), bank)
    assert captured["sources"][0]["source_id"] == "lecturer-notes"
    assert sum(len(s["text"]) for s in captured["sources"]) <= 24000
    assert result["retrieval"]["lectures"]["status"] == "unavailable"


async def test_tutorials_and_exams_cannot_supply_answer_evidence(corpus, monkeypatch):
    from app.services.course_rag import get_course_rag
    from app.schemas.course_rag import SearchRequest
    example = get_course_rag().search(SearchRequest(course_code="IT2040", query="normalization", document_types=["exam"])).sources[0]
    async def generate(recommendation, count):
        return {"status": "ok", "candidates": [fake_candidate(example.source_id)]}
    monkeypatch.setattr(llm_service, "generate_candidates", generate)
    result = await exam_creator.generate_for_paper(request(), [])
    assert result["status"] == "degraded" and result["candidates"] == []
    assert result["retrieval"]["assessment_examples"]["sources"]


async def test_generation_failure_retains_retrieval_status(corpus, monkeypatch):
    async def generate(*args, **kwargs):
        return {"status": "degraded", "reason": "ollama_unavailable"}
    monkeypatch.setattr(llm_service, "generate_candidates", generate)
    result = await exam_creator.generate_for_paper(request(), [])
    assert result["status"] == "degraded"
    assert result["retrieval"]["lectures"]["sources"]


def test_citation_metadata_survives_saved_draft_validation():
    from app.schemas.exam_creator import DraftPart
    source = {"source_id": "doc:p1:c0", "kind": "lecture", "text": "Evidence",
              "course_code": "IT2040", "filename": "Lecture.pdf", "page_number": 1, "year": 2024, "rank_score": .02}
    part = DraftPart.model_validate({"question": "Question", "sources": [source]})
    assert part.model_dump()["sources"][0] == source
