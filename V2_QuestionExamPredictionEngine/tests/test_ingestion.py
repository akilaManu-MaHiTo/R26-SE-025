from app.ingestion.transformer import (
    flatten_paper,
    ingest,
    to_question_attempts,
    to_question_catalog,
)
from tests.fixtures.fixture_data import sample_papers, sample_submissions


def test_flatten_paper_counts_parts():
    flat = flatten_paper(sample_papers[0])
    assert len(flat) == 3
    assert flat[0]["max_marks"] == 2.0


def test_to_question_catalog_classifies_missing_labels():
    paper = {
        "exam_id": "exam-2023",
        "course_code": "SE2032",
        "year": 2023,
        "questions": [
            {
                "question_number": "01",
                "parts": [{"part": "a", "text": "Write a SQL SELECT.", "max_marks": 2.0}],
            }
        ],
    }
    catalog = to_question_catalog(paper)
    assert catalog[0]["topic_assignments"][0]["topic"] == "SQL"
    assert catalog[0]["bloom_level"] == "Apply"
    assert catalog[0]["question_id"] == "exam-2023-01a"


def test_to_question_attempts_join_and_normalize():
    papers = sample_papers
    catalog_records, _ = ingest([], papers, sample_submissions, "run-fixture")
    lookup = {c["question_id"]: c for c in catalog_records}
    attempts = to_question_attempts(sample_submissions[:5], lookup, "run-fixture")
    assert len(attempts) == 5
    assert all(0.0 <= a["normalized_score"] <= 1.0 for a in attempts)
    assert attempts[0]["attempt_id"] == "exam-2023-01a-stu-001"


def test_ingest_returns_catalog_and_attempts():
    catalog, attempts = ingest([], sample_papers, sample_submissions, "run-fixture")
    assert len(catalog) == 6
    assert len(attempts) == 72