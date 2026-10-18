# Analytics course RAG

This index belongs only to AdaptiveExamAnalyticsEngine. It does not connect to the
grading engine's retrieval implementation or storage.

## Manage materials in the application

Open **Question & Exam Prediction → Course Materials** at
`/question-exam/course-materials`. The catalog reads the existing analytics index,
including the eight IT2040 lectures, six tutorials, and four past final papers.
All courses and document types appear initially; use the course and type filters
to narrow the list. Each entry shows its page count, indexed passage count, year,
index mode, extraction warnings, and skipped text-poor pages.

The complete management flow is:

1. Select or enter a course code, choose Lecture / Tutorial / Past exam, optionally
   enter a year, and select a PDF. Uploads are limited to 20 MB and validated on
   the server as well as in the interface. Access requires a lecturer session.
2. **Upload and index** extracts text page by page, creates bounded passages,
   computes embeddings when configured, and atomically saves the PDF and its
   indexed passages together. The interface shows a working state and refreshes
   the catalog after success. There is no fabricated percentage progress.
3. **Open PDF** opens the original document in an authenticated browser tab. The
   original PDF is stored as a BLOB in the same SQLite document record, making
   replacement and backup consistent with the indexed content.
4. **Replace** asks for a new PDF and confirmation. It preserves the course,
   material type, year, filename, and document identity. Failed extraction or
   indexing preserves the previous PDF and passages. Uploading an existing name
   through the new-upload form reports a conflict instead of replacing silently.
5. **Remove** asks for confirmation, then removes the stored PDF record and all
   its passages/vectors from retrieval. Other materials, bundled source files on
   disk, and previously saved exam drafts are preserved. A manual bulk import
   can restore a removed bundled file because its original still exists on disk.
6. Exam Creator searches this same index immediately: lecture text supplies answer
   evidence; tutorial/past-paper matches supply assessment examples and originality
   comparisons. File/page citations and lecturer approval still apply. Other
   features can adopt the same service/search API later; they are not connected
   automatically by this materials-management change.

The API supports `GET/POST /api/lecturers/materials`,
`PUT/DELETE /api/lecturers/materials/{document_id}`, and
`GET /api/lecturers/materials/{document_id}/pdf` in addition to search.

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
Use `--rebuild` to re-extract unchanged files. The bulk importer does not purge
sources absent from disk; use **Remove** in Course Materials to remove a document.

The analytics base requirements include the embedding dependencies. To repair an
existing environment that was created before that dependency was included, run
this command with the **same Python executable that starts the backend**:

```powershell
python -m pip install -r requirements-embeddings.txt
```

If the backend is launched from the repository's root `.venv`, run from the
repository root instead:

```powershell
.\.venv\Scripts\python.exe -m pip install -r AdaptiveExamAnalyticsEngine/requirements-embeddings.txt
```

Installing into `AdaptiveExamAnalyticsEngine/.venv` does not install into the root
environment. Restart the backend after dependency or generation-code updates.

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
  `storage/course_rag/index.sqlite3`. An empty value also uses that default.
- `EMBEDDING_AVAILABLE`: enables semantic retrieval/import using the analytics
  engine's existing `EMBEDDING_MODEL`. Disable for keyword retrieval.
- `COURSE_RAG_MIN_SIMILARITY`: cosine candidate cutoff, default `0.45`. This is
  an initial heuristic, not an academically calibrated confidence threshold.

The index stores the embedding model identifier per document. Reimport after
changing models; incompatible vectors are excluded from semantic ranking. Search
reports keyword fallback or partial vector coverage. Context is built only from
the requested course and document types, with overlapping same-page hits suppressed.
Rank scores use reciprocal rank fusion; they are not probabilities.

Exam Creator generation uses a bounded selection of evidence (up to 6,000 text
characters), learning outcomes (up to 1,200 characters), and six short historical
examples, with a final encoded JSON bound. If evidence or outcomes are shortened,
the response includes a visible warning. The model receives an 8,192-token context
window, a count-dependent output limit, and a JSON response schema constrained to
the requested question count, topic, Bloom level, marks, and supplied source IDs.
The full local history still participates in the post-generation duplicate check.
These limits do not change the configured model or timeout. A CPU-only 7B model
can still be slow; increasing the timeout alone does not improve throughput.

The database now contains uploaded originals as well as generated passages: keep
it in persistent storage and back it up using SQLite's backup API, which includes
committed WAL data. `storage/course_rag/` is ignored by Git. Deploying source code
does not transfer this database or PDFs.

Existing installations can retain an explicit `COURSE_RAG_INDEX` pointing to their
old index, or copy it to persistent storage using SQLite backup before switching
paths. Do not overwrite an already-used destination database. This workspace's
original `.cache/course_rag/index.sqlite3` was safely backed up to the new default;
the old file was retained. All 18 original PDFs were attached by the importer
without regenerating the existing embeddings. Restart running backends to pick up
the new default. Legacy version-1 indexes remain readable; the first import or
upload adds the new PDF/warning columns without discarding their existing chunks.
To attach originals to other legacy indexes, rerun the importer with the same
source PDFs; unchanged content does not require embedding again.

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
python -m pytest tests/test_course_material_management.py tests/test_course_rag.py tests/test_course_rag_api.py tests/test_exam_creator_rag.py tests/test_exam_creator.py -q --basetemp=.cache/pytest-rag
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

Materials-management follow-up: 98 focused backend tests, eight frontend tests,
and the production build passed. The active persistent catalog was checked for
all 18 original PDFs and 293 existing embedded chunks. SQLite integrity check
passed; concurrent delete/backfill and replacement/backfill consistency were
independently reviewed. This follow-up did not rerun live LLM generation or OCR.

Generation-runtime repair: the root backend environment was missing
`sentence-transformers`; installing the existing pinned embedding requirements
restored hybrid retrieval. With the 7B model and 300-second timeout unchanged,
the bounded structured request generated two SQL/Apply questions successfully.
The measured full request took 236 seconds (Ollama generation about 195 seconds,
1,012 prompt tokens and 666 output tokens). Both candidates passed the existing
source, topic, marks, rubric and originality checks. This is one runtime check,
not an academic-quality benchmark or a guarantee of the same latency for every
topic. The focused regression suite passed 111 tests.
