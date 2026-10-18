"""Independent course retrieval contracts, using real PDFs and a temporary SQLite index."""
import sqlite3

import fitz
import numpy as np
import pytest


def pdf(path, *pages):
    with fitz.open() as document:
        for text in pages:
            page = document.new_page()
            page.insert_text((40, 50), text, fontsize=10)
        document.save(path)
    return path


@pytest.fixture
def rag(tmp_path):
    from app.services.course_rag import CourseRag
    return CourseRag(tmp_path / "index.sqlite3", semantic=False)


def search(rag, query="normalization", course="IT2040", kinds=None, limit=5):
    from app.schemas.course_rag import SearchRequest
    return rag.search(SearchRequest(course_code=course, query=query,
        document_types=kinds or ["lecture", "tutorial", "exam"], limit=limit))


def test_real_pdf_indexing_citations_idempotence_and_empty_pages(rag, tmp_path):
    path = pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant data and update anomalies.", "")
    report = rag.index_pdf(path, "it2040", "lecture", year=2024)
    assert report["status"] == "indexed"
    assert report["pages"] == 2
    assert report["empty_pages"] == [2]
    assert report["chunks"] == 1
    result = search(rag)
    assert result.status == "ok" and result.mode == "keyword"
    source = result.sources[0]
    assert (source.course_code, source.kind, source.filename, source.page_number, source.year) == (
        "IT2040", "lecture", "Lecture.pdf", 1, 2024)
    assert "redundant data" in source.text
    assert rag.index_pdf(path, "IT2040", "lecture", year=2024)["status"] == "unchanged"
    assert [s.source_id for s in search(rag).sources] == [source.source_id]


def test_course_and_type_filters_with_same_filenames(rag, tmp_path):
    path = pdf(tmp_path / "Shared.pdf", "Normalization decomposes database relations into normal forms.")
    for course, kind in [("IT2040", "lecture"), ("IT2040", "exam"), ("SE9999", "lecture")]:
        rag.index_pdf(path, course, kind)
    assert len(search(rag).sources) == 2
    assert len({s.source_id for s in search(rag).sources}) == 2
    assert [s.kind for s in search(rag, kinds=["exam"]).sources] == ["exam"]
    assert len(search(rag, course="SE9999").sources) == 1
    assert search(rag, course="UNKNOWN").sources == []


def test_queries_are_safe_bounded_and_do_not_fill_with_irrelevant_hits(rag, tmp_path):
    rag.index_pdf(pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant data and update anomalies."), "IT2040", "lecture")
    assert search(rag, 'normalization ") OR * --').sources
    assert search(rag, "normalization normalization", limit=1).sources
    assert search(rag, "photosynthesis chlorophyll").sources == []
    assert search(rag, "!!!").sources == []


def test_changed_document_replaces_old_text_and_keeps_stable_identity(rag, tmp_path):
    path = pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data.")
    rag.index_pdf(path, "IT2040", "lecture")
    source_id = search(rag).sources[0].source_id
    path.unlink()
    pdf(path, "Transactions maintain atomicity and durability in database systems.")
    rag.index_pdf(path, "IT2040", "lecture")
    assert search(rag).sources == []
    assert search(rag, "transactions").sources[0].source_id == source_id


def test_failed_extraction_preserves_existing_document(rag, tmp_path):
    path = pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data.")
    rag.index_pdf(path, "IT2040", "lecture")
    path.write_bytes(b"broken pdf")
    with pytest.raises(ValueError, match="extract"):
        rag.index_pdf(path, "IT2040", "lecture")
    assert search(rag).sources


def test_empty_replacement_does_not_erase_old_document(rag, tmp_path):
    path = pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data.")
    rag.index_pdf(path, "IT2040", "lecture")
    path.unlink()
    pdf(path, "")
    with pytest.raises(ValueError, match="text"):
        rag.index_pdf(path, "IT2040", "lecture")
    assert search(rag).sources


class TopicEmbedder:
    """Deterministic vectors let us verify filtering without downloading a model."""
    def embed_batch(self, texts):
        return np.array([[1., 0.] if any(w in t.lower() for w in ("normal", "redundan")) else [0., 1.] for t in texts])

    def embed(self, text):
        return self.embed_batch([text])[0]


def test_semantic_paraphrase_and_course_type_isolation(tmp_path):
    from app.services.course_rag import CourseRag
    rag = CourseRag(tmp_path / "index.sqlite3", embedder=TopicEmbedder())
    path = pdf(tmp_path / "lecture.pdf", "Normal forms remove redundant facts from relations.")
    rag.index_pdf(path, "IT2040", "lecture")
    rag.index_pdf(path, "SE9999", "exam")
    result = search(rag, "normalization")
    assert result.mode == "hybrid"
    assert len(result.sources) == 1 and result.sources[0].course_code == "IT2040"
    assert search(rag, "normalization", kinds=["exam"]).sources == []


def test_embedding_failure_is_explicit_and_does_not_destroy_vectors(tmp_path):
    from app.services.course_rag import CourseRag
    class BrokenEmbedder(TopicEmbedder):
        def embed_batch(self, texts):
            raise RuntimeError("model unavailable")
    path = pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data.")
    good = CourseRag(tmp_path / "index.sqlite3", embedder=TopicEmbedder())
    good.index_pdf(path, "IT2040", "lecture")
    broken = CourseRag(good.index_path, embedder=BrokenEmbedder())
    with pytest.raises(RuntimeError, match="model unavailable"):
        broken.index_pdf(path, "IT2040", "lecture", rebuild=True)
    result = search(broken)
    assert result.mode == "keyword" and result.warnings and result.sources
    assert search(good).mode == "hybrid"


def test_model_mismatch_reports_keyword_mode(tmp_path, monkeypatch):
    from app.config import settings
    from app.services.course_rag import CourseRag
    rag = CourseRag(tmp_path / "index.sqlite3", embedder=TopicEmbedder())
    rag.index_pdf(pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data."), "IT2040", "lecture")
    monkeypatch.setattr(settings, "embedding_model", "different-model")
    result = search(CourseRag(rag.index_path, embedder=TopicEmbedder()))
    assert result.mode == "keyword" and result.warnings and result.sources


def test_missing_and_corrupt_indexes_are_explicit(rag):
    assert search(rag).status == "unavailable"
    assert not rag.index_path.exists()
    rag.index_path.write_bytes(b"not a sqlite index")
    assert search(rag).status == "unavailable"


def test_request_validation_and_long_page_chunks(rag, tmp_path):
    from app.schemas.course_rag import SearchRequest
    from pydantic import ValidationError
    for kwargs in ({"course_code": "../course"}, {"query": " "}, {"limit": 0},
                   {"limit": 11}, {"document_types": ["answers"]}):
        with pytest.raises(ValidationError):
            SearchRequest.model_validate({"course_code": "IT2040", "query": "SQL", **kwargs})
    # Use many short lines so PDF content remains on the physical page.
    text = "\n".join(["Normalization avoids redundant facts in relational databases."] * 45)
    report = rag.index_pdf(pdf(tmp_path / "long.pdf", text), "IT2040", "lecture")
    assert report["chunks"] > 1
    result = search(rag)
    assert len(result.sources) == 1  # overlapping chunks on the same page are deduplicated
    assert len(result.sources[0].text) <= 1400


def test_failed_sql_replacement_rolls_back_old_document(rag, tmp_path):
    path = pdf(tmp_path / "lecture.pdf", "Normalization prevents redundant database data.")
    rag.index_pdf(path, "IT2040", "lecture")
    with sqlite3.connect(rag.index_path) as db:
        db.execute("CREATE TRIGGER reject_chunk BEFORE INSERT ON chunks BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    path.unlink()
    pdf(path, "Transactions preserve atomicity and durability in databases.")
    with pytest.raises(sqlite3.IntegrityError, match="test failure"):
        rag.index_pdf(path, "IT2040", "lecture")
    assert search(rag).sources
    assert search(rag, "transactions").sources == []


def test_search_uses_one_snapshot_while_import_commits(rag, tmp_path, monkeypatch):
    rag.index_pdf(pdf(tmp_path / "old.pdf", "Normalization prevents redundant database data."), "IT2040", "lecture")
    new_path = pdf(tmp_path / "new.pdf", "Normalization removes redundant facts from relational tables.")
    with sqlite3.connect(rag.index_path) as db:
        db.execute("PRAGMA journal_mode=WAL")
    original_search = rag._search
    class InterleavedConnection:
        def __init__(self, connection):
            self.connection = connection
        def execute(self, statement, parameters):
            cursor = self.connection.execute(statement, parameters)
            if "FROM chunks c JOIN documents" in statement:
                rows = cursor.fetchall()
                rag.index_pdf(new_path, "IT2040", "lecture")
                class CapturedRows:
                    def fetchall(self):
                        return rows
                return CapturedRows()
            return cursor
    monkeypatch.setattr(rag, "_search", lambda db, request: original_search(InterleavedConnection(db), request))
    result = search(rag)
    assert result.status == "ok"
    assert [s.filename for s in result.sources] == ["old.pdf"]
