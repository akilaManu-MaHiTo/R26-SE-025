# Exam Paper Reconstruction Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reconstruct verified exam/question/student/evaluation relationships and report incomplete or conflicting data honestly.

**Architecture:** Pure Python reconstruction over source documents, a read-only Motor repository loader and a CLI using existing analytics settings. Do not modify grading logic or add persistence/API exposure.

**Tech Stack:** Existing Python, Motor, PyMongo, pytest; no added dependency.

**Spec:** `EXAM_PAPER_AUDIT.md` (actual database audit and matching design).

## Global constraints

- No grades, answers or rubrics are modified; only the separately authorized examStructure correction was applied.
- Exact keys/references and complete uniquely matched metadata only; no fuzzy matching.
- Missing/unverified diagram definitions remain unresolved.
- Existing results and source provenance survive unchanged; summaries omit personal data.

## Review focus

- Conflicting explicit keys must not be repaired by metadata fallback.
- A shared rubric must not merge different students or exam years.
- Duplicate result rows must never silently win or add marks twice.
- Missing/NaN/infinite marks and criterion inconsistencies must be reported.
- Live processing records and truncated answers must remain incomplete.

## Task 1: Pure reconstruction and validation

Files: create `app/services/exam_paper.py`, `tests/test_exam_paper.py`.

- [x] Write tests for four essays plus a diagram, verified metadata representations, missing definitions/results/rubrics, duplicates, two students and two exams.
- [x] Run tests and observe missing-service failure.
- [x] Implement `reconstruct_exam_paper(exam_key, sources)` with distinct definition/paper/student validation and unresolved evidence.
- [x] Verify no source dictionaries change and no ambiguous records become accepted answers.

## Task 2: Read-only loader and CLI

Files: modify `app/db/repository.py`; create `scripts/reconstruct_exam_paper.py`; extend tests.

- [x] Test exact-key/full-identity/ref queries using in-memory collections, including both rubric spellings.
- [x] Implement `load_exam_paper_sources(db, exam_key)` and the summary-first CLI.
- [x] Run focused tests, compile checks and a real read-only gradev5 reconstruction summary.
- [x] Save a synthetic sample and verification results; document usage and unresolved live data.

## Execution notes

The user explicitly requested implementation following database verification, so execution continues inline without another authorization round. The missing diagram source is an input limitation, not permission to invent a prompt or reuse SQL Q5.

Ruling: Move the audit and plan to the engine root after writing them; the repository ignores every `docs` directory. Root placement follows the existing audit-document convention and keeps these deliverables visible to Git.

Fresh review: malformed nested containers/criterion labels, duplicate roster IDs, and ignored essay maximum marks were reproduced and fixed with regression tests. Full-paper fallback answers are quarantined rather than counted repeatedly.

## Follow-up: combine essay and diagram grades

The user explicitly selected all five essays plus one diagram and authorized
correcting examkeys again. The 2025 exam now has six slots and a 55-mark maximum.

- [x] Add failing tests for combined maxima/percentages, missing evaluations,
  duplicated grades, invalid marks/totals, criterion review and ambiguous rubrics.
- [x] Add per-student grading from the already exact-matched source records,
  independently of missing original diagram prompt/artifact recovery.
- [x] Keep missing component marks and final percentages null; flag provisional
  numeric grades with inconsistent criterion evidence as needs_review.
- [x] Verify both maxima and current student results against gradev5 read-only;
  leave saved grading results untouched and update documentation/sample output.
