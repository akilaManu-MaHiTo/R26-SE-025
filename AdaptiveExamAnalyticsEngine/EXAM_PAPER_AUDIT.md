# Exam-paper reconstruction audit and design

Inspected 2026-10-16, against the local MongoDB **gradev5**, using read-only
queries before implementation. Counts are a point-in-time observation: essay
grading was actively processing. No credentials, roster names or student IDs
are retained here.

**Subsequent user correction:** The user confirmed that **all five stored
essays plus the diagram** count. A second guarded update changed the 2025
examStructure to five Essays followed by Diagram. The verified maxima are
35 + 20 = **55**. Combined component grading is now supported independently
of original question-paper recovery; missing evaluations remain pending and
inconsistent evidence requires review. The four-essay conflict described below
records the earlier audit state and is resolved by this explicit correction.

## Actual collections and schemas

| Collection | Count | Observed fields and types |
| --- | ---: | --- |
| `examkeys` | 2 | `_id`: ObjectId; `examKey`, `subjectCode`, `subjectName`, `examMonth`, `session`: string; `examYear`, `examSemester`: integer; `examStructure`: string array |
| `rubricCollection` | 0 | Collection expected by the essay/analytics source code; absent from collection inventory |
| **`rubicCollection`** | 1 | `_id`: ObjectId; `examKey`, `subject_code`, `subject_name`, `session_name`, `filename`: string; `year`, `month`, `semester`: integer; `parsed_at`: float; `questions`: embedded array; `exam_roster`: embedded object |
| `submissions` | 5 | `_id`, `rubric_ref`: ObjectId; `examKey`, `batch_job_id`, `student_id`, `paper_key`, subject/session fields, transcripts and `status`: string; year/month/semester and `max_marks_paper_total`: integer; `max_marks_per_question`: array; `evaluation`: object or null; `error`: null in inspected records; `progress`: object; created/updated/processed timestamps: BSON dates (processed timestamp only when present) |
| `diagram_marking` | 1 | `_id`: ObjectId; `examCode`: string; `guideLines`: embedded array; `totalMarks`: integer; `source_file`: object; `created_at`, `updated_at`: BSON dates |
| `diagram_evaluations` | 5 | `_id`: ObjectId; `student_id`, `examKey`, subject/session fields, `guideline_object_id`, `remarks`, `source`, created/updated timestamps: string; year/month/semester, `diagram_marks`, `agent_marks`: integer; `diagram_details`, `evaluation_result`: objects; `diagram_entity_relations`, `diagram_relations`: arrays |

Nested structures actually observed:

- Essay `questions[]`: `question_no`, `question_text` strings;
  `max_marks` integer; `criteria[]` with `point` string and `marks` integer.
- `exam_roster`: `students[]` (student ID/name/date strings),
  `duplicate_roster_ids[]`, `uploaded_at` string, `row_count` integer.
- Essay `evaluation`: `results[]`, total score numeric, maximum integer,
  justification/feedback/grading source strings, RAG metadata, `answer_split`.
  Each result has `q_no`, `answer_excerpt`, `slice_source`, `grading_source`,
  `justification`, `feedback` strings; numeric `score`; nullable `error`;
  `criteria_breakdown[]` with string `point`/`reason`, numeric `awarded_marks`.
  There is no per-result `max_score` in these records.
- Diagram guidelines: integer `id`, string `criterion`/`description`, numeric
  `marks`, heterogeneous `expected` objects describing entities, attributes,
  relationships, notation or completeness. `source_file` contains filename,
  uploaded timestamp, extracted marking-guideline text and character count.
  **It is marking text, not a verified original question prompt.**
- Diagram `evaluation_result`: `status`, `detections[]`, `structure`, nullable
  `ocr_error`, `guideline_object_id`, `agent_marks`, **`agent_grading`**.
  `agent_grading`: numeric `agent_marks`/`max_marks`, `feedback` string,
  `criterion_results[]` with integer `id`, numeric `marks`, string `reason`.
- Diagram artifacts are extracted structures/detections and crop paths;
  the save schema does not retain a stable original-upload reference.
  `diagram_details` repeats some extracted structures and detection metadata.

Only `_id` indexes were observed on the rubric/guideline collections. No
duplicate exam/student/rubric-or-guideline groups occurred in the ten inspected
grading records. That is not a uniqueness guarantee for later runs.

## Verified records and relationships

- `EXAM-2025-S1-Apr`: IT2040, 2025, semester 1, April, Final.
  Originally declared **five essays**. On the user's subsequent explicit
  instruction, its last slot was changed to Diagram using a guarded, single
  record update. Structure after that first correction: **four Essays then one Diagram**;
  the subsequent user correction above supersedes it with **five Essays then Diagram**.
  No rubric, answer or grade was changed.
- `EXAM-IT2040-2027-S2-Nov-FINAL`: IT2040, 2027, semester 2, November,
  Final; five Essays followed by one Diagram. No matching grading records
  were observed. Do not derive keys by parsing either naming format.
- All five essay submissions and the one essay rubric carry the first exact
  `examKey`. Every `rubric_ref` equals that rubric's ObjectId, but the rubric
  exists in **rubicCollection**, not the collection used by existing code.
- The five essay questions are `01` through `05`, maxima 10, 7, 6, 6, 6
  (35 total). Question 05 is **SQL Server Security Authorization Steps**;
  it is not a diagram question. The corrected structure therefore conflicts
  with the stored fifth essay. Do not relabel or discard its grades.
  Their stored `question_text` values are short headings. They are reproduced
  from the rubric, but equality to the original exam wording is not established.
- All five diagram records carry the same exact exam key and full matching
  metadata. Their string `guideline_object_id` equals the diagram guideline's
  ObjectId. That guideline's `examCode` is **ERD-004**, not an exam key.
  This proves which rubric was used by those evaluations, not a numbered
  diagram definition or that ERD-004 universally aliases the exam key.
- The same five exact student IDs appear in both pipelines. Do not match by
  roster name, list order, paper filename or exam key alone.
- At the null-safe inspection, two essay records were graded, one processing
  and two not started. All five diagram evaluations had saved grades (19,
  13, 13, 19, 19 out of 20). These values may change as grading continues.
- No diagram question number or original question prompt was present in
  these collections. The guideline filename is not evidence of question order.

## Existing pipeline trace

Essay:

0. `main.py::upload_rubric` calls `services/ai_service.py::parse_rubric_ai`
   to extract `questions` from the uploaded PDF. Its prompt requests full
   question wording; its normalizer can substitute `Question {number}` when
   wording is absent. Stored fields are therefore extraction outputs, not
   independent evidence that the original exam prompt was captured correctly.
1. `GradingEngine/app/main.py::start_grading`, POST
   `/grade-batch/{rubric_id}`, validates a roster/batch when requested and
   creates stubs before scheduling `run_batch_grading`.
2. `services/grading_manager.py::run_batch_grading` fetches a rubric by
   ObjectId, resolves each student via the validated paper-ID mapping (or
   paper key), obtains page OCR via `process_student_answer`, and combines
   a raw transcript and a cleaned transcript.
3. `services/llm_service.py::generate_grading_report` uses
   `answer_splitter::split_transcript_by_questions` and
   `resolve_answer_for_question`, then sends each answer and its rubric
   question to `evaluate_grading_async`.
4. The exact `/api/grade` route handler is **`handle_grading`**, not `grade`.
   It delegates to `evaluate_grading_async` / `evaluate_grading` in
   `services/ai_model_route.py`: RAG enrichment, Colab, Groq fallback, result
   normalization. `generate_grading_report` stores scores, criteria and
   feedback; `_attach_diagnostics` saves only the first **1200 characters**
   of the grading answer and its slice source.
5. The manager writes `evaluation`, transcripts, identity and processing
   status to the submission. Full-paper fallback can send the same transcript
   for multiple questions; reconstruction must flag that ambiguity. Existing
   fallback/error zeros remain unchanged and are not treated as missing marks.
6. The inspected essay source does not propagate `examKey`, although the live
   records contain it. Their population history is not established by this
   code inspection; do not assume future writes will always include it.

Diagram:

1. `Gradex_AI_Server/app/main.py::diagram_evaluate`, POST
   `/api/diagram-evaluate` (also misspelled alias `/api/digaram-evaluate`),
   accepts an image and `guideline_object_id`. It is not named `student`.
2. It resolves `diagram_marking._id`, runs
   `DiagramEvaluationEngine/predict.py::run_er_pipeline` for detection/OCR,
   then `diagram_grading.py::grade_diagram_with_ollama` against `guideLines`.
   The response includes the rubric ID, extracted diagram and `agent_grading`.
3. Client `DiagramGrading.tsx::persistEvaluation` supplies student ID and exam
   metadata/key separately, then calls POST `/api/diagram-evaluate-save`.
4. `diagram_evaluate_save` / `_normalize_record` preserves the result and
   inserts it into **diagram_evaluations**. It does not prove student/exam/
   question identity from the uploaded image; the saved association is the
   available provenance, not independently verified authorship.

Connections:

- Analytics uses `app/config.py::settings.effective_mongodb_uri` and
  `settings.mongodb_db`; inspected selection is local **gradev5**.
- Essay `core/database.py` uses `MONGODB_URL` + `DATABASE_NAME`.
  `GradingEngine/.env` was absent; server process environment can supply it.
- Server `mongodb.py` uses URI default database (or `Grading`) for diagram
  collections, but `EXAM_KEYS_DATABASE_NAME` / `DATABASE_NAME` for exam keys.
  Inspected server settings select gradev5 for exam keys while
  `DATABASE_NAME` is `grading`. The configured URI has no default database;
  calling the existing `get_default_database()` without a default raises
  `ConfigurationError`, before its intended `Grading` fallback. This was
  reproduced without connecting. Shared database selection must not be assumed.
- Existing analytics repositories expect singular `diagram_evaluation` and
  an older `criteria_results`/`total_score` format. The new reconstruction
  must read the verified plural collection/nested agent format explicitly.

## Design and exact matching rules (before implementation)

Use a pure reconstruction service plus a small read-only repository query and
CLI inside AdaptiveExamAnalyticsEngine. No new dependency, persisted collection,
grading change, migration or public endpoint is necessary.

1. Select one canonical `examkeys` record by exact `examKey`; detect duplicate
   keys and full-identity collisions. Check subject/year/semester/month/session.
2. Accept direct keys only if supplied metadata does not contradict the exam.
   For legacy records without a key, require a complete, uniquely matching
   subject/year/month/semester/session tuple. Numeric April=4 and the observed
   Final=Final Examination are explicit representations, not fuzzy matching.
   A nonempty different exam key is a conflict, never an automatic alias.
3. Load both known rubric spellings, retaining collection provenance; never
   rename a collection or silently choose between duplicate rubric candidates.
   Join submissions by exact rubric ObjectId/string representation and student
   ID, then `q_no` to that rubric's numeric `question_no` (01 equals 1).
4. Require question number/type to match the corresponding examStructure slot.
   Preserve unexpected definitions and evaluations as unresolved references.
5. Join diagram evaluations to the exact guideline ID and student/exam. This
   permits rubric-level grouping only. **Without an authoritative numbered
   question and prompt, keep these as unresolved diagram evidence.** A single
   diagram slot does not prove the missing definition; do not infer Q5 from
   a filename or replace the SQL essay with it.
6. Separate canonical exam validity, complete question definitions and each
   student's completeness. Use roster IDs only from matched rubrics to report
   students missing both submission types. Never require evaluations to
   establish essay question definitions.
7. Detect duplicate definitions, per-student submissions and result rows;
   do not choose the latest arbitrarily or count ambiguous answers twice.
8. Preserve existing result payloads and source references. Validate finite
   nonnegative marks, verified rubric maxima, criterion alignment and totals.
   Missing marks stay null; no clamping, regrading or zero substitution.
9. Label saved essay excerpts and their potential truncation; full transcript
   references are not claimed to be verified per-question answers. Flag missing
   artifacts, failed grading and unavailable original diagram uploads.
10. Default CLI output is a count/status summary without student identifiers,
    answers or paths. Full reconstruction export requires an explicit flag.

Alternatives considered: a database aggregation cannot safely manufacture the
missing question definitions; a persisted materialization adds stale results
and duplicate management. A read-only service exposes gaps without either cost.

## Known limits / required source corrections

The exam structure correction alone does not make a complete mixed paper.
The user has resolved essay Q5 by including all five essays. The original
diagram question/prompt and explicit question-to-guideline binding remain missing.
The reconstruction will remain incomplete until these are supplied. Changing
grading records or inventing a mapping would violate answer integrity.

Combined grades do not require inventing that missing prompt: the user has
confirmed both components count, and saved exam/student/rubric references link
their marks. The service checks the expected essay slots, one diagram component,
unique matching rubrics, score bounds and saved totals before adding them. It
does not add partial grades, choose among duplicate attempts or assign a final
percentage when either evaluation is missing. Criterion conflicts produce an
explicit `needs_review` grade, even if a provisional numeric total is available.
