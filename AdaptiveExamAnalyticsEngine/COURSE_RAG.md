# Analytics course RAG

This index belongs only to AdaptiveExamAnalyticsEngine. It does not connect to the
grading engine's retrieval implementation or storage.

From the analytics engine folder, with its Python environment active:

```powershell
python scripts/index_course_materials.py
```

The default import maps IT2040 to the 8 lecture PDFs, 6 tutorial PDFs, and 4 previous
final papers in `datasets/bloom_dataset/{lectures,tutorial,Final exam}`. These PDFs
are local, ignored files: deploying the code does not deploy the course corpus.
Imports show per-file page/chunk counts, skipped text-poor pages, encoding warnings,
and failures. A nonzero exit code means at least one source failed or a required
folder contained no PDFs. Fix the source and rerun; successful documents remain.
An unchanged file is skipped. Changed content replaces its own chunks atomically.
Use `--rebuild` to re-extract unchanged files. Removed files are not automatically
purged: rebuild into a new index path when intentionally removing corpus content.

The normal import requires the existing optional embedding dependencies:

```powershell
python -m pip install -r requirements-embeddings.txt
```

If the embedding model is unavailable, use an explicit keyword-only import:

```powershell
python scripts/index_course_materials.py --keyword-only
```

Rerun the normal import after enabling the model to build semantic vectors. Import
errors never silently replace an existing semantic document with a keyword-only
copy. `--keyword-only` explicitly requests replacement without vectors.

For another course, supply its code and root directory explicitly:

```powershell
python scripts/index_course_materials.py --course SE9999 --root C:/materials/SE9999
```

That root must contain the same three folder names. Document years are taken from
the PDF filename when present; unknown years remain null. Filenames must be unique
within a course and document type. A document's identity includes the course, type,
and filename; citations include its one-based page and chunk position.

## Configuration

- `COURSE_RAG_INDEX`: SQLite index path; default is the engine's
  `.cache/course_rag/index.sqlite3`. An empty value also uses that default.
- `EMBEDDING_AVAILABLE`: enables semantic retrieval/import using the analytics
  engine's existing `EMBEDDING_MODEL`. Disable for keyword retrieval.
- `COURSE_RAG_MIN_SIMILARITY`: cosine candidate cutoff, default `0.45`. This is
  an initial heuristic, not an academically calibrated confidence threshold.

The index stores the embedding model identifier per document. Reimport after
changing models; incompatible vectors are excluded from semantic ranking. Search
reports keyword fallback or partial vector coverage. Context is built only from
the requested course and document types, with overlapping same-page hits suppressed.
Rank scores use reciprocal rank fusion; they are not probabilities.

## Search and generation

`POST /api/lecturers/materials/search` is registered on both the standalone analytics
API and the shared application backend. It requires the existing lecturer session
and trusted-origin protections; students cannot access it. Example body:

```json
{"course_code":"IT2040","query":"normalization","document_types":["lecture"],"limit":4}
```

The response includes `status`, `mode`, `warnings`, and `sources`, each with text,
source ID, course, type, filename, page, optional year, and rank score. The reusable
Python interface is `get_course_rag().search(SearchRequest(...))`.

Exam Creator automatically retrieves lecture passages as answer evidence and
tutorial/past-exam passages as assessment examples. Pasted lecturer notes take
priority. Lecture objectives remain the fallback. Examples are not accepted as
answer-source citations. Retrieved text is untrusted evidence, never instructions.
The existing question/rubric validation and lecturer approval remain required.

This version uses PDF text extraction only. It does not recover scanned pages,
interpret diagrams, repair OCR, or guarantee reading order for complex tables.
Inspect the original source for diagram/table questions. Retrieval does not prove
an answer correct. Student practice and other consumers are not connected yet.

## Checks

```powershell
python -m pytest tests/test_course_rag.py tests/test_course_rag_api.py tests/test_exam_creator.py -q --basetemp=.cache/pytest-rag
```

Create `.cache` first if absent. Tests use temporary indexes; they do not alter the
live corpus. Model-backed tests use deterministic vectors, so live retrieval and
generation quality should also be reviewed with actual course documents.

## Verified local corpus (2026-10-18)

The initial semantic import indexed all 18 PDFs: 279 pages produced 293 chunks.
A repeat import skipped all 18 unchanged documents. Six text-poor pages were
excluded: Lecture 06 page 2, Lecture 07 pages 20/24/27/28, and Lecture 08 page 33.
The index remains local and ignored by Git; run the importer on each deployment.

Live hybrid searches returned Lecture 03 pages 14/19/22 for normalization and
Lecture 04 page 19 for SQL joins. Tutorial 03 pages 1/2 were retrieved as
normalization assessment examples. An unrelated photosynthesis/chlorophyll query
returned no lecture hits. Transaction searches found passing mentions; the eight
included lectures do not constitute complete coverage of every DBMS topic.

Focused checks: 84 backend tests, 4 frontend tests, and the frontend production
build passed. The build retains its existing large-bundle warning. A concurrent
import/search regression test verifies snapshot consistency, and a failed-write
test verifies replacement rollback. A live generation attempt hit a 60-second
test timeout despite successful hybrid retrieval; this is not a question-quality
benchmark. A second attempt used the configured 300-second timeout and completed,
but the returned batch was rejected by the existing question constraint checks
(topic, marks, citations, originality, and requested count). No valid live batch
was established by these checks; academic generation quality remains unverified.
The model's configured production timeout was not changed.
