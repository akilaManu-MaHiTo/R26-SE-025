# Exam-paper reconstruction verification

Verified 2026-10-16. The implementation is a read-only reconstruction/validation
service, not evidence that the live data contains a complete mixed paper.

## Files

- `app/services/exam_paper.py`: pure reconstruction, source references,
  exact identity checks, separate exam/paper/student statuses, unresolved data.
- `app/db/repository.py`: new `load_exam_paper_sources`; existing grading and
  analytics functions are unchanged. Queries read one exam's key/metadata
  candidates plus exact referenced rubrics, including both known spellings.
- `scripts/reconstruct_exam_paper.py`: existing analytics database settings,
  summary-first output, explicit private-data export, no-overwrite output.
- `tests/test_exam_paper.py`: synthetic schema fixtures and isolated query/CLI
  checks; no database creation, seeding, grading calls or network requests.
- `EXAM_PAPER_AUDIT.md`, `EXAM_PAPER_IMPLEMENTATION_PLAN.md`, `README.md`:
  inspected architecture, design, execution record and usage.
- `examples/exam_paper.synthetic.json`: five essays plus an unresolved diagram,
  with combined grade 53.5/55 (97.27%). The question paper remains **incomplete**;
  no fictional diagram question text is inserted.
- `audit_evidence/exam_paper_gradev5_summary.json`: sanitized live results for
  both actual exam keys, with read timestamps and no student IDs or answers.

## Executed tests

```text
python -m pytest tests/test_exam_paper.py tests/test_student_document_analytics.py tests/test_schemas.py -q -p no:cacheprovider --tb=short
95 passed in 0.71s
```

71 new reconstruction/query/CLI/grading cases and 24 existing numeric/schema checks
passed. The initial missing-service and missing-loader failures were observed
before their implementation. Additional regressions were observed failing
before fixes for ignored maximum marks, reused full-paper answer slices,
malformed nested fields, roster duplicates and unsafe numeric/string ID coercion.

Independent review reproduced the malformed-container, duplicate-roster and
maximum-score defects; all findings have regression coverage and were fixed.

| Requested scenario | Observed test behavior |
| --- | --- |
| Four essays + one diagram | Four numbered essay definitions; missing original diagram definition remains unresolved, never a fabricated valid paper |
| Different identifier representations | Exact ObjectId/string references, `01`/`1` question numbers, and complete unique metadata mapping succeed; `ERD-004` never acts as an exam key |
| Missing diagram | Expected diagram slot is missing; incomplete |
| Missing essay | Missing numbered slot and Essay type reported |
| Wrong question count/type | Extra essay Q5 retained as unresolved; not relabelled as Diagram |
| Two students | Separate answers/results under exact student IDs |
| Missing submission/evaluation | Matched rubric roster reports missing students; processing/null results do not become zero marks |
| Duplicates | Duplicate questions, submissions, result rows, diagram evaluations and roster IDs flagged; ambiguous answers not selected |
| Unmatched rubric | Exact-reference failure or cross-collection collision is flagged |
| Different exam years/semesters/sessions | Complete tuple checked; conflicting explicit keys/metadata quarantined |

Additional cases cover malformed data, missing/nonfinite/excessive marks,
criterion alignment and totals, potentially truncated answers, unknown student
IDs, duplicate canonical identities, full-paper fallback, credential-safe error
messages, default output privacy and refusal to overwrite an existing file.

Python compile checks and `git diff --check` passed. CLI `--help` was inspected.
The actual live CLI process returned **2** for incomplete data and emitted valid
summary JSON, verified with a subprocess assertion rather than inferred from
the shell tool's generic nonzero status.

## Live gradev5 result

For **EXAM-2025-S1-Apr**:

- Canonical exam definition valid: five Essays, then Diagram, following the user's final clarification.
- Five verified numbered essay definitions. Q6 Diagram's original definition is missing.
- Five students; zero complete student papers.
- Ten essay result/answer-excerpt links (two graded submissions, five
  accepted essay slots each).
- One unresolved diagram question/rubric group, linked through five exact
  exam/student/guideline references; its original prompt/number is absent.
- Five unresolved diagram evaluations at question-definition level. Their
  exact exam/student/rubric links still support component grading.
- Three remaining essay submissions had no evaluation at the read time.
- One criterion label/mark association mismatch and two potentially truncated
  1200-character answer excerpts were reported without changing the grades.
- Combined maximum: **35 essay + 20 diagram = 55**. One complete combined
  grade, one provisional grade requiring criterion review, and three pending
  grades. Missing essay evaluations are not treated as zero. Per-student
  `grading` includes source references, both component scores, total and percentage.

For **EXAM-IT2040-2027-S2-Nov-FINAL**:

- Canonical definition valid: five Essays then Diagram.
- Zero matched question definitions/submissions/evaluations; all six slots
  reported missing, paper incomplete.

These are nontransactional reads of a live database. The exported summaries
explicitly say `consistentSnapshot: false`; concurrent grading can change the
counts. No full student data was exported from the real database.

## Authorized database change and unresolved inputs

The only database writes in this task were the user's two subsequent explicit
corrections of the 2025 examkeys array. Each compare-and-set update checked its
ObjectId, exact exam key, full exam metadata and prior five-Essay array before
first replacing the last Essay with Diagram, then, after clarification, setting
five Essays followed by Diagram. Each matched 1, modified 1; read-back
verified the requested array. No grades, answers, rubrics, other exam records,
collections or indexes were modified by reconstruction.

Still needed for a complete mixed paper:

1. The authoritative original diagram prompt and explicit question-to-guideline
   binding. The expected final Diagram slot alone does not establish which
   original question a rubric describes.
2. Essay Q5 is resolved: the user confirmed it counts, and Diagram is the
   sixth slot. The original diagram prompt/binding is still needed for a complete paper.
3. Stable references to original submitted diagram images, if completeness must
   include the original artifact rather than only saved extracted structures.
4. Completion/review of pending essay grading, criterion discrepancies and
   potentially truncated saved answer excerpts.
5. Comparison of saved essay `question_text` (currently short headings) with
   the original paper. Reconstruction preserves the stored wording; it does
   not certify the AI rubric parser captured the original question verbatim.

The configured diagram server has no URI default database and its existing
default-database call raises ConfigurationError; the essay source expects a
different rubric collection spelling and does not visibly propagate examKey.
Those upstream defects are documented, not silently repaired in a reconstruction
task. Reconstructed source associations cannot independently prove authorship,
OCR correctness or the accuracy of the original grading model.

Not run: the full repository suite (some fixtures create/drop a test database),
live LLM/OCR grading, browser workflows or migrations. No complete real mixed
paper or end-to-end grading success is claimed.
