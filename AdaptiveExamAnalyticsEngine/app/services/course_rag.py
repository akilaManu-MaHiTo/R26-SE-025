"""Analytics-owned PDF retrieval. No grading service, shared index, or external database."""
from contextlib import closing
from functools import lru_cache
from hashlib import sha256
import json
import logging
from pathlib import Path
import re
import sqlite3

import fitz
import numpy as np

from app.config import settings
from app.schemas.course_rag import RetrievedSource, SearchRequest, SearchResult

logger = logging.getLogger(__name__)
ENGINE_ROOT = Path(__file__).resolve().parents[2]
CHUNK_CHARS = 1400
OVERLAP = 200
SCHEMA_VERSION = 1
STOP_WORDS = set("a an and are as at be by describe discuss explain for from how in is it of on or the to what with".split())

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY, course_code TEXT NOT NULL, kind TEXT NOT NULL,
    filename TEXT NOT NULL, year INTEGER, checksum TEXT NOT NULL,
    model TEXT NOT NULL, pages INTEGER NOT NULL, empty_pages TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS document_scope ON documents(course_code, kind);
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL, position INTEGER NOT NULL, text TEXT NOT NULL, vector BLOB
);
CREATE INDEX IF NOT EXISTS chunk_document ON chunks(document_id);
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    text, content='chunks', content_rowid='rowid', tokenize='porter unicode61'
);
CREATE TRIGGER IF NOT EXISTS chunk_insert AFTER INSERT ON chunks BEGIN
    INSERT INTO chunk_fts(rowid, text) VALUES (new.rowid, new.text);
END;
CREATE TRIGGER IF NOT EXISTS chunk_delete AFTER DELETE ON chunks BEGIN
    INSERT INTO chunk_fts(chunk_fts, rowid, text) VALUES ('delete', old.rowid, old.text);
END;
"""


def page_chunks(text: str):
    """Bounded word-aligned windows; never join unrelated pages."""
    text = " ".join(text.split())
    start = 0
    while start < len(text):
        end = min(start + CHUNK_CHARS, len(text))
        if end < len(text):
            boundary = text.rfind(" ", start + CHUNK_CHARS // 2, end)
            if boundary != -1:
                end = boundary
        yield text[start:end].strip()
        if end == len(text):
            break
        start = end - OVERLAP
        boundary = text.find(" ", start, end)
        if boundary != -1:
            start = boundary + 1


def _unit_vectors(values, count):
    vectors = np.asarray(values, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) != count or not np.isfinite(vectors).all():
        raise ValueError("Embedding model returned invalid vectors")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise ValueError("Embedding model returned empty vectors")
    return vectors / norms


class CourseRag:
    def __init__(self, index_path=None, embedder=None, semantic=None):
        self.index_path = Path(index_path or settings.course_rag_index or ENGINE_ROOT / ".cache/course_rag/index.sqlite3").resolve()
        self.semantic = settings.embedding_available if semantic is None else semantic
        self.model_name = settings.embedding_model
        self._embedder = embedder

    @property
    def embedder(self):
        if self._embedder is None:
            # Reuse the analytics model instance also used by question originality checks.
            from app.services.llm_service import _get_embedder
            self._embedder = _get_embedder()
        return self._embedder

    def _connect(self, write=False):
        if write:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.index_path if write else self.index_path.as_uri() + "?mode=ro",
                             uri=not write, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        if write:
            db.execute("PRAGMA journal_mode=WAL").fetchone()
        return db

    def index_pdf(self, path, course_code, document_type, year=None, *, rebuild=False):
        scope = SearchRequest(course_code=course_code, query="index", document_types=[document_type])
        path = Path(path)
        if path.suffix.lower() != ".pdf":
            raise ValueError("Only PDF source files can be indexed")
        content = path.read_bytes()
        checksum = sha256(content).hexdigest()
        identity = sha256(f"{scope.course_code}:{document_type}:{path.name}".encode()).hexdigest()[:24]
        model = self.model_name if self.semantic else ""
        if self.index_path.exists() and not rebuild:
            with closing(self._connect()) as db:
                old = db.execute("SELECT * FROM documents WHERE id=?", (identity,)).fetchone()
            if old and old["checksum"] == checksum and old["model"] == model and old["year"] == year:
                return {"status": "unchanged", "filename": path.name}

        chunks, empty_pages, warnings = [], [], []
        try:
            with fitz.open(stream=content, filetype="pdf") as document:
                if document.needs_pass:
                    raise ValueError("Password-protected PDFs are not supported")
                pages = len(document)
                for number, page in enumerate(document, 1):
                    text = page.get_text("text", sort=True).strip()
                    if len(text) < 40:
                        empty_pages.append(number)
                        continue
                    if text.count("\ufffd") > max(3, len(text) // 100):
                        warnings.append(f"Page {number}: possible text encoding damage; check the original PDF.")
                    for position, chunk in enumerate(page_chunks(text)):
                        chunks.append((number, position, chunk))
        except Exception as exc:
            raise ValueError(f"Could not extract {path.name}: {exc}") from exc
        if not chunks:
            raise ValueError(f"No usable text in {path.name}; OCR is not included")
        vectors = [None] * len(chunks)
        if self.semantic:
            # Prepare before replacing: a model failure must preserve an existing index entry.
            encoded = _unit_vectors(self.embedder.embed_batch([c[2] for c in chunks]), len(chunks))
            vectors = [vector.tobytes() for vector in encoded]

        with closing(self._connect(write=True)) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, SCHEMA_VERSION):
                raise ValueError("Unsupported course RAG index version; use a new index path")
            db.executescript(SCHEMA)
            db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
            with db:
                db.execute("DELETE FROM documents WHERE id=?", (identity,))
                db.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)", (
                    identity, scope.course_code, document_type, path.name, year, checksum,
                    model, pages, json.dumps(empty_pages)))
                db.executemany("INSERT INTO chunks VALUES (?,?,?,?,?,?)", [
                    (f"{identity}:p{page}:c{position}", identity, page, position, text, vector)
                    for (page, position, text), vector in zip(chunks, vectors)])
        return {"status": "indexed", "filename": path.name, "pages": pages, "chunks": len(chunks),
                "empty_pages": empty_pages, "warnings": warnings, "mode": "hybrid" if model else "keyword"}

    def search(self, request: SearchRequest) -> SearchResult:
        if not self.index_path.is_file():
            return SearchResult(status="unavailable", mode="unavailable",
                                warnings=["Course material index is missing. Run the analytics material importer."])
        try:
            with closing(self._connect()) as db:
                # Keep scoped rows and FTS hits consistent while an importer commits new chunks.
                db.execute("BEGIN")
                if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    raise ValueError("Course material index version is unsupported")
                return self._search(db, request)
        except (sqlite3.Error, OSError, ValueError) as exc:
            logger.warning("Analytics course index unavailable: %s", exc)
            return SearchResult(status="unavailable", mode="unavailable",
                                warnings=["Course material index could not be read. Check or rebuild the analytics index."])

    def _search(self, db, request):
        types = list(dict.fromkeys(request.document_types))
        filters = f"d.course_code=? AND d.kind IN ({','.join('?' for _ in types)})"
        parameters = [request.course_code, *types]
        rows = db.execute(f"""SELECT c.*, d.course_code, d.kind, d.filename, d.year, d.model
            FROM chunks c JOIN documents d ON d.id=c.document_id WHERE {filters}""", parameters).fetchall()
        if not rows:
            return SearchResult(status="ok", mode="keyword", warnings=["No indexed materials match this course and document selection."])
        by_id = {row["id"]: row for row in rows}
        terms = list(dict.fromkeys(w for w in re.findall(r"[^\W_]+", request.query.lower())
                                   if w not in STOP_WORDS))[:32]
        if not terms:
            return SearchResult(status="ok", mode="keyword", warnings=["Enter subject-specific search terms."])
        # Tokens are quoted and bound as data; FTS operators from a user never execute.
        expression = " AND ".join(f'"{term}"' for term in terms)
        lexical = db.execute(f"""SELECT c.id FROM chunk_fts
            JOIN chunks c ON c.rowid=chunk_fts.rowid JOIN documents d ON d.id=c.document_id
            WHERE chunk_fts MATCH ? AND {filters} ORDER BY bm25(chunk_fts) LIMIT 60""",
            [expression, *parameters]).fetchall()
        rankings = [[row["id"] for row in lexical]]
        mode, warnings = "keyword", []
        compatible = [row for row in rows if row["model"] == self.model_name and row["vector"] is not None]
        if self.semantic and compatible:
            try:
                query_vector = _unit_vectors([self.embedder.embed(request.query)], 1)[0]
                matrix = np.stack([np.frombuffer(row["vector"], dtype=np.float32) for row in compatible])
                if matrix.shape[1] != len(query_vector) or not np.isfinite(matrix).all():
                    raise ValueError("Incompatible vectors")
                similarities = matrix @ query_vector
                ranked = sorted(zip(compatible, similarities), key=lambda pair: float(pair[1]), reverse=True)
                # shortcut: this cutoff is conservative, calibrate against lecturer-rated retrieval as the corpus grows.
                threshold = max(settings.course_rag_min_similarity, float(ranked[0][1]) - 0.15)
                rankings.append([row["id"] for row, score in ranked if score >= threshold][:60])
                mode = "hybrid"
                if len(compatible) != len(rows):
                    warnings.append("Some documents have no compatible embeddings; reimport them for full semantic coverage.")
            except Exception as exc:
                logger.warning("Analytics semantic search unavailable: %s", exc)
                warnings.append("Semantic retrieval unavailable; keyword search was used.")
        elif self.semantic:
            warnings.append("No compatible embeddings for these materials; keyword search was used. Reimport to build vectors.")
        else:
            warnings.append("Semantic retrieval disabled; keyword search was used.")
        scores = {}
        for ranking in rankings:
            for rank, source_id in enumerate(ranking, 1):
                scores[source_id] = scores.get(source_id, 0) + 1 / (60 + rank)
        sources, seen_pages = [], set()
        for source_id in sorted(scores, key=lambda key: (-scores[key], key)):
            row = by_id[source_id]
            page_key = (row["document_id"], row["page_number"])
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            sources.append(RetrievedSource(source_id=source_id, kind=row["kind"], text=row["text"],
                course_code=row["course_code"], filename=row["filename"], page_number=row["page_number"],
                year=row["year"], rank_score=round(scores[source_id], 6)))
            if len(sources) == request.limit:
                break
        return SearchResult(status="ok", mode=mode, warnings=warnings, sources=sources)


@lru_cache(maxsize=4)
def _service(index_path, model, semantic):
    return CourseRag(index_path, semantic=semantic)


def get_course_rag():
    return _service(settings.course_rag_index, settings.embedding_model, settings.embedding_available)
