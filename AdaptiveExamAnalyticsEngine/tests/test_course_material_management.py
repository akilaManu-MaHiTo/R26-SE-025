"""Materials management must operate on the existing analytics index only."""
import sqlite3

import httpx
import pytest

from tests.test_course_rag import pdf, search


@pytest.fixture
def material_api(tmp_path, monkeypatch):
    from app.config import settings
    from app.main import app
    from Gradex_AI_Server.app import session_auth
    monkeypatch.setattr(settings, "course_rag_index", str(tmp_path / "index.sqlite3"))
    monkeypatch.setattr(settings, "embedding_available", False)
    async def lecturer(connection):
        return {"email": "l@example.test", "role": "lecturer"}
    monkeypatch.setattr(session_auth, "session_user", lecturer)
    return app


async def test_existing_index_inventory_pdf_and_removal(material_api, tmp_path):
    from app.services.course_rag import get_course_rag
    rag = get_course_rag()
    path = pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant facts from database relations.", "")
    rag.index_pdf(path, "IT2040", "lecture", 2024)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=material_api), base_url="http://test", headers={"Origin": "http://test"}) as client:
        response = await client.get("/api/lecturers/materials")
        assert response.status_code == 200
        item = response.json()["items"][0]
        assert (item["filename"], item["course_code"], item["document_type"], item["pages"], item["chunks"]) == ("Lecture.pdf", "IT2040", "lecture", 2, 1)
        assert item["empty_pages"] == [2]
        doc_id = item["document_id"]
        file_response = await client.get(f"/api/lecturers/materials/{doc_id}/pdf")
        assert file_response.status_code == 200 and file_response.content.startswith(b"%PDF")
        assert (await client.delete(f"/api/lecturers/materials/{doc_id}")).status_code == 200
        assert (await client.get("/api/lecturers/materials")).json()["items"] == []
        assert (await client.delete(f"/api/lecturers/materials/{doc_id}")).status_code == 404
    assert path.exists()  # bundled/local source files are never deleted by the API
    assert search(rag).sources == []


async def test_upload_replace_and_failed_replacement_preserve_sources(material_api, tmp_path):
    original = pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant facts from database relations.").read_bytes()
    updated = pdf(tmp_path / "Update.pdf", "Transactions preserve atomicity and durability in database systems.").read_bytes()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=material_api), base_url="http://test", headers={"Origin": "http://test"}) as client:
        response = await client.post("/api/lecturers/materials", data={"course_code": "it2040", "document_type": "lecture", "year": "2024"}, files={"file": ("Lecture.pdf", original, "application/pdf")})
        assert response.status_code == 201
        doc_id = response.json()["item"]["document_id"]
        duplicate = await client.post("/api/lecturers/materials", data={"course_code": "IT2040", "document_type": "lecture"}, files={"file": ("Lecture.pdf", original, "application/pdf")})
        assert duplicate.status_code == 409
        bad = await client.put(f"/api/lecturers/materials/{doc_id}", files={"file": ("Bad.pdf", b"%PDF broken", "application/pdf")})
        assert bad.status_code == 422
        assert (await client.get(f"/api/lecturers/materials/{doc_id}/pdf")).content == original
        replacement = await client.put(f"/api/lecturers/materials/{doc_id}", files={"file": ("Update.pdf", updated, "application/pdf")})
        assert replacement.status_code == 200
        item = replacement.json()["item"]
        assert (item["document_id"], item["filename"], item["year"]) == (doc_id, "Lecture.pdf", 2024)
        hits = await client.post("/api/lecturers/materials/search", json={"course_code": "IT2040", "query": "transactions"})
        assert hits.json()["sources"]
        old = await client.post("/api/lecturers/materials/search", json={"course_code": "IT2040", "query": "normalization"})
        assert old.json()["sources"] == []


@pytest.mark.parametrize("filename,content,data,expected", [
    ("notes.txt", b"plain", {}, 422),
    ("../notes.pdf", b"%PDF", {}, 422),
    ("notes.pdf", b"", {}, 422),
    ("notes.pdf", b"not pdf", {}, 422),
    ("notes.pdf", b"%PDF", {"course_code": "../IT2040"}, 422),
    ("notes.pdf", b"%PDF", {"document_type": "answers"}, 422),
])
async def test_invalid_uploads_rejected(material_api, filename, content, data, expected):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=material_api), base_url="http://test", headers={"Origin": "http://test"}) as client:
        response = await client.post("/api/lecturers/materials", data={"course_code": "IT2040", "document_type": "lecture", **data}, files={"file": (filename, content)})
    assert response.status_code == expected


async def test_student_cannot_manage_materials(material_api, monkeypatch):
    from Gradex_AI_Server.app import session_auth
    async def student(connection):
        return {"email": "s@example.test", "role": "student", "student_id": "S1"}
    monkeypatch.setattr(session_auth, "session_user", student)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=material_api), base_url="http://test", headers={"Origin": "http://test"}) as client:
        for method, path in [("GET", "/api/lecturers/materials"), ("POST", "/api/lecturers/materials"), ("DELETE", "/api/lecturers/materials/" + "a" * 24)]:
            assert (await client.request(method, path)).status_code == 403


def test_listing_legacy_index_without_rebuilding_vectors(tmp_path):
    from app.services.course_rag import CourseRag
    rag = CourseRag(tmp_path / "index.sqlite3", semantic=False)
    path = pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant database relations and anomalies.")
    rag.index_pdf(path, "IT2040", "lecture")
    with sqlite3.connect(rag.index_path) as db:
        # The original index has neither of the new metadata columns.
        db.execute("ALTER TABLE documents DROP COLUMN original_pdf")
        db.execute("ALTER TABLE documents DROP COLUMN warnings")
        db.execute("PRAGMA user_version=1")
    inventory = rag.list_documents()
    assert inventory.items[0].filename == "Lecture.pdf"
    assert search(rag).sources
    rag.index_pdf(path, "IT2040", "lecture")  # backfills the PDF without recomputing vectors
    assert rag.document_pdf(inventory.items[0].document_id) == path.read_bytes()


def test_default_index_uses_persistent_storage(monkeypatch):
    from app.config import Settings, settings
    from app.services.course_rag import CourseRag, ENGINE_ROOT
    assert Settings(_env_file=None).course_rag_index == str(ENGINE_ROOT / "storage" / "course_rag" / "index.sqlite3")
    monkeypatch.setattr(settings, "course_rag_index", "")
    assert CourseRag().index_path == ENGINE_ROOT / "storage" / "course_rag" / "index.sqlite3"


async def test_oversized_pdf_rejected_before_indexing(material_api, monkeypatch):
    from app.api import course_rag
    monkeypatch.setattr(course_rag, "MAX_PDF_BYTES", 4)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=material_api), base_url="http://test", headers={"Origin": "http://test"}) as client:
        response = await client.post("/api/lecturers/materials", data={"course_code": "IT2040", "document_type": "lecture"}, files={"file": ("Big.pdf", b"%PDF exceeds configured limit")})
    assert response.status_code == 413


def test_unchanged_import_cannot_restore_a_deleted_document(tmp_path, monkeypatch):
    from app.services.course_rag import CourseRag
    rag = CourseRag(tmp_path / "index.sqlite3", semantic=False)
    path = pdf(tmp_path / "Lecture.pdf", "Normalization removes redundant facts from database relations.")
    report = rag.index_pdf(path, "IT2040", "lecture")
    original_connect = rag._connect
    class DeleteAfterRead(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            cursor = super().execute(statement, parameters)
            if statement.startswith("SELECT checksum, model, year"):
                row = cursor.fetchone()
                with original_connect(write=True) as other:
                    other.execute("DELETE FROM documents WHERE id=?", (report["document_id"],))
                class SavedRow:
                    def fetchone(self):
                        return row
                return SavedRow()
            return cursor
    def connect(write=False):
        db = sqlite3.connect(rag.index_path, factory=DeleteAfterRead)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db
    monkeypatch.setattr(rag, "_connect", connect)
    with pytest.raises(FileNotFoundError):
        rag.index_bytes(path.read_bytes(), path.name, "IT2040", "lecture", require_existing=True)
    assert rag.list_documents().items == []


def test_backfill_cannot_mix_original_pdf_with_another_versions_text(tmp_path, monkeypatch):
    from hashlib import sha256
    from app.services.course_rag import CourseRag
    rag = CourseRag(tmp_path / "index.sqlite3", semantic=False)
    first = pdf(tmp_path / "First.pdf", "Normalization removes redundant facts from database relations.").read_bytes()
    second = pdf(tmp_path / "Second.pdf", "Transactions preserve atomicity and durability in database systems.").read_bytes()
    rag.index_bytes(first, "Lecture.pdf", "IT2040", "lecture")
    original_connect = rag._connect
    writer = CourseRag(rag.index_path, semantic=False)
    class ReplaceAfterRead(sqlite3.Connection):
        def execute(self, statement, parameters=()):
            cursor = super().execute(statement, parameters)
            if statement.startswith("SELECT checksum, model, year"):
                row = cursor.fetchone()
                writer.index_bytes(second, "Lecture.pdf", "IT2040", "lecture")
                class SavedRow:
                    def fetchone(self):
                        return row
                return SavedRow()
            return cursor
    def connect(write=False):
        db = sqlite3.connect(rag.index_path, factory=ReplaceAfterRead)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db
    monkeypatch.setattr(rag, "_connect", connect)
    rag.index_bytes(first, "Lecture.pdf", "IT2040", "lecture", require_existing=True)
    with original_connect() as db:
        row = db.execute("SELECT checksum,original_pdf FROM documents").fetchone()
        assert row["checksum"] == sha256(row["original_pdf"]).hexdigest()
        assert "Normalization" in db.execute("SELECT text FROM chunks").fetchone()[0]
