# Lecturer dashboard audit and cleanup — 2026-10-16

What this engine does: It reads saved essay/diagram grading evidence, calculates student and class analytics, classifies questions, and serves the lecturer dashboard. This review assumes the current research deployment with one API process; concurrent production workers need the safeguards below.

The project inventory, entry points, settings, dependencies and tests were inspected. Detailed tracing covered lecturer routes, repository joins/cache writes, essay and diagram normalization, class calculations, reconstruction, teaching recommendations and the connected client. Adjacent student, taxonomy, recommendation and exam-creator interfaces were checked where these paths share them. This is not a claim that every research script or training notebook was reviewed line by line.

## Confirmed problems fixed

| Priority | Problem and reproducible case | Change |
| --- | --- | --- |
| P1 | A request for a student's 2027 exam could return their 2025 paper. Archived or duplicate active papers could be selected. | Removed the date-dropping fallback; require an active, unique result. Class requests spanning different years or conflicting exam keys are rejected. |
| P1 | Writing repeat-exam analytics replaced the previous year's record. | Student analytics, alias and result write keys/index definitions now include year/month/semester. Missing dates remain in result filters instead of making them broader. |
| P1 | Zero or missing awards became full marks through a paper-maximum fallback. | Shared saved-total validation preserves zero, rejects invalid/nonfinite/out-of-range awards and leaves missing scores null. Inventory averages use available validated totals and display their component/count. |
| P2 | An explicit missing rubric reference selected a different rubric. Numeric reference `1` could match string ID `"1"`. | Exact supported string/ObjectId references only; no substitution for a missing explicit reference. Read both supported collection spellings, reject ambiguity/conflicting metadata, and require full metadata for unreferenced legacy matching. |
| P2 | Different criterion labels matched by position. Missing awards became zero; duplicates and inconsistent totals passed. | Require exact normalized label coverage, finite explicit awards, positive maxima and consistent question/criterion/paper totals. Reject unreadable evidence and grading-error rows. |
| P2 | Class processing reused the first student's rubric for everyone. | Verify each student's rubric and report excluded invalid evidence. Multiple valid rubric versions require review before saving a class calculation. Duplicate student submissions are excluded. |
| P2 | Another year's snapshot marked an exam analyzed; a version tag alone made malformed snapshots appear complete. | Removed broad inventory cache fallbacks and validate the response schema. Failed refreshes label retained usable results stale. Calculation versions advanced to 1.3. |
| P2 | Classification review/confidence fields disappeared during response validation. | Preserve these fields and display classification-review/limited-evidence warnings on question cards. |
| P2 | Diagram/essay performance labels disagreed at 40–50% and 60–65%; topic sorting could divide by zero. | Use the shared 80/60/40 performance scale and guard zero denominators. Performance labels remain separate from the 50% pass threshold. |
| P2 | Negative recommendation weights passed; zero limit returned every topic; one tutorial produced 0.7333 despite its documented 0.6 endpoint. | Validate finite nonnegative weights, respect explicit zero limits, and interpolate tutorial evidence from 1→0.6 to 3→1. |
| P2 | Inventory errors appeared as “No exams found”; stale stream progress could update the selected exam. | Show a separate error/retry state, guard progress/fallback updates and reset teaching state on selection. |
| P2 | Template advice appeared under an AI-only heading; non-string model output became advice; local mode could retain a stale Colab URL. | Label AI/template/saved suggestions, accept only nonempty string advice, and resolve local mode to localhost while Colab uses its configured URL. |

## Cleanup

- Deleted unused `app/services/topic_canonicalization.py` (287 lines). Whole-tree searches found only two legacy test callers. The active class service already aggregates canonical topics from normalized evidence. Removed those legacy tests and added coverage at the active service boundary; the database-backed service integration test remains.
- Removed the unused `get_weakness_for_exam` wrapper, its repository import, unused variables and duplicated diagram status function.
- Removed disabled Export/Report and Generate Practice Questions controls from these dashboard panels. Other working generation/export flows remain available.
- Retained archived sample scripts, compatibility shims, audit evidence, datasets, notebooks and model assets. They support research or compatibility work; deleting research history was unnecessary. Earlier uncommitted work was preserved.

## Live verification — read only

`gradev5` has no unique indexes on `student_analytics`, `studentExamAnalysis` or `studentExamResults`. No indexes or database records were changed.

The initial strict comparison excluded one of the two graded 2025 IT2040 essays. A follow-up for IT22239199 established that all rows existed: the only label difference was an unmatched closing `)` at the end of one Question 01 rubric criterion. This was a validation false positive, not missing grading evidence. Normalization and reconstruction now share a conservative rule that ignores only excess unmatched terminal closing parentheses, preserving balanced/internal punctuation and rejecting different words or duplicate normalized labels. Error messages identify the question and distinguish duplicate labels from unmatched labels.

Read-only verification after the correction validated this student's five essay questions and all 15 criterion rows. Their combined result is complete: 34.5/35 essay plus 19/20 diagram = 53.5/55 (97.27%). No source labels, answers or saved marks were modified. Calculation versions advanced again to 1.4 so previously cached exclusions are rebuilt when possible.

The five-essay plus diagram structure and 55 maximum marks were preserved. Original diagram question wording remains unavailable and the preview continues to flag that source gap.

## Remaining work and limits

1. **Source freshness:** version/schema checks and Reanalyse exist, but no full source revision/hash is implemented. Editing grading data without invalidating a snapshot can leave valid-looking cached essay analytics outdated. Reanalyse after corrections; version checks are not automatic evidence freshness.
2. **Indexes/concurrent writes:** initialize full-identity unique indexes through a controlled database review before concurrent production use. Existing `create_indexes` can replace old definitions; it was not executed here. Other deployments may still have older broad indexes and must review them before repeat-exam writes.
3. **Multiple workers:** the in-flight exam job map is process-local. It does not coordinate separate API workers or every non-streaming request. A shared job lease is needed for multiple workers.
4. **Legacy inventory:** the exam list is essay-rubric-driven. Canonical records without an essay rubric, including diagram-only exams, do not yet have a complete inventory flow. The empty-state wording now states the actual requirement.
5. **Source repairs:** mismatched saved labels and missing original diagram text need authoritative source correction. The application must not invent those repairs.

## Verification

- **298 passed** across 21 offline backend test files after the criterion-label correction: integrity, ingestion, reconstruction, grading status, diagrams, schemas, class arithmetic, recommendation/evaluation and configuration. The selected suite's formerly expected equation failures now pass. Pairing regressions preserve balanced suffixes after list markers such as `a)` and reject normalization collisions.
- **18 passed** across four frontend test files: inventory failure/retry, null versus zero, classification warnings, suggestion provenance, grading progress and paper preview.
- `npm run build` passed. Existing npm configuration and Vite bundle-size warnings remain.
- Independent read-only review reproduced key bugs and confirmed the corrected reference/type guards. Live checks printed only counts, validation reasons and index definitions.
- Not run: database-dependent tests, full model inference/training, every legacy sample/migration test, multiworker load tests or a real browser walkthrough. An initial broader student-pipeline attempt invoked real model work and was interrupted; it is not counted as passing.

Verdict: the confirmed lecturer matching, score-validation and calculation defects above are corrected. Source-based cache invalidation and production concurrency/index setup remain explicit limits.
