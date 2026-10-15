# Lecturer exam creator

The existing Exam Creator now supports a saved exam blueprint, draft-aware bank recommendations, and grounded question alternatives through the existing Ollama integration. No new model downloads or dependencies are required by this change.

## Workflow

1. Select the historical exam whose analytics should inform the new paper. The editor starts empty and uses the current year for the target paper. The historical session, year, month and semester are saved separately.
2. Set total marks, duration, purpose, learning outcomes, topic marks and Bloom percentages. Percentages must total 100. A complete topic allocation restricts recommendations to those topics; a partial allocation allows other topics.
3. Final-exam recommendations prioritize blueprint gaps. Revision recommendations also use measured weaknesses. Already selected/rejected questions, questions exceeding remaining marks, and questions exceeding a topic allocation are excluded.
   Tutorials without assigned marks remain available, but require an explicit lecturer mark allocation before insertion.
4. Paste relevant lecture notes, or use a topic with lecture objectives in the course bank. Generate two alternatives at the chosen Bloom level and marks. Outputs include an answer, a marking scheme whose marks sum correctly, estimated minutes, and supplied source references. Objectives are labeled as objectives, not full lecture passages.
5. Add an alternative for review. Edit answers and marking criteria, then approve each part. Editing question text, topic, marks, answer or rubric resets its approval.
6. Save the draft, including an empty blueprint-only draft. Blueprint, source exam, notes, answers, rubrics, sources, approvals and rejection reasons survive reopening.
7. Export the student paper and a separate lecturer marking-scheme PDF. Student exports omit answers and rubrics. Long text is paginated line by line.

## API and models

- `POST /api/lecturers/exam-creator/review`: `{course_code, paper}`; returns available course topics, ranked candidates, coverage, estimated time and review issues. Missing saved analytics is explicitly reported; it does not prevent blueprint checks.
- `POST /api/lecturers/exam-creator/generate`: the same payload plus `topic`, `bloom_level`, `marks` and `count` (1–3); requires source evidence and remaining allocation. Invalid generated sources, mismatched topic/Bloom/marks, incorrect rubrics and close textual duplicates are rejected.
- Existing draft endpoints retain optional metadata and support older drafts without a blueprint.
- Bank rows must identify their owner using `course_code`, `subject_code`, or the existing `IT2040_...` question ID convention. Unowned `GEN_...` legacy rows are deliberately excluded until they are tagged with a verified course. No ownership is inferred from similar topic names.
- Generation uses the existing `settings.llm_model` / Ollama endpoint. The project already supports `qwen3:8b` via `COLAB_MODEL`; local generation uses `OLLAMA_MODEL`. This change does not alter the user's current model or endpoint settings.
- Generation honors `OLLAMA_TIMEOUT` in `.env` (seconds per attempt). CPU generation with a 7B model can exceed 90 seconds; use `OLLAMA_TIMEOUT=300` if needed and restart the analytics backend after changing it. Timeout errors include the configured limit; a passing model health check only confirms reachability and model availability.
- Existing MiniLM embeddings provide optional semantic similarity warnings. If unavailable, the UI explicitly reports that only textual similarity was checked. BGE retrieval/reranking and fine-tuning remain future evaluations, not claimed quality improvements.

## Limits and validation

Source references establish which supplied evidence the model cited, not factual correctness. Bloom levels, time estimates, answer quality, learning-outcome alignment and whether a diagram is actually present require lecturer review. Diagram checks flag explicit missing-material phrases; they do not inspect attachments. Source notes are entered as text; PDF ingestion and automatic difficulty calibration are not included.

Regression tests cover course isolation, the two-year recency window, generated candidates not counting as tutorial practice, draft-aware exclusions, unmarked tutorials, complete long question text, malformed inputs, missing source evidence, rubric totals, generated constraint checks, and draft persistence. API/model tests mock model output and do not benchmark live generation quality.

Validation on 2026-10-14: 39 focused creator/recommendation/LLM-service tests passed; the frontend production build passed. Browser checks exercised tutorial mark allocation, insertion and updated remaining marks, answer/rubric editing, approval invalidation after marks changes, and narrow/desktop layouts. Existing build warnings concern bundle size and mixed static/dynamic imports; the existing TopBar also logs a Button ref warning in development.

The original backend suite has these nine failures, reproduced with the original tracked backend modules loaded from Git HEAD:

- `test_config_ollama.py::test_llm_base_url_resolves_to_localhost_in_local_env`
- `test_exam_analytics_service.py::test_compute_exam_analytics_persists_and_returns_document`
- `test_llm_generate.py::test_valid_candidate`
- `test_loader.py::test_load_real_builds_course_from_courses_json`
- `test_run_sample.py::test_main_ignores_unrelated_graded_submission_and_analytics`
- `test_sample_data_structure.py::test_submissions_have_v2_shape_and_graded_status`
- `test_sample_data_structure.py::test_migrate_sample_v2_is_idempotent`
- `test_student_data_ingestion.py::test_normalize_submission_joins_questions_and_criteria`
- `test_switch_llm.py::test_preserves_lf_line_endings`
