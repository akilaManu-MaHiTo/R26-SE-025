# Lecturer diagram dashboard fix

Verified 2026-10-16 against gradev5 using read-only queries.

The dashboard had a Diagram Analysis panel, but its repository queried singular
`diagram_evaluation` and expected old `total_score`/`criteria_results` fields.
The live collection is `diagram_evaluations`; grades are nested under
`evaluation_result.agent_grading`. Marking rubrics have guideline IDs, not
student/exam metadata. Cached essay snapshots could also hide newer diagrams.

Changes:

- `app/ingestion/diagram_data.py` adapts saved agent grades into the existing
  dashboard schema on a copy. Exact guideline references supply criterion labels
  and maxima; awards supply pass/partial/fail. Raw saved grades are not changed.
  Missing/invalid marks, unsuccessful results and conflicting totals raise
  validation errors instead of appearing as zero or disappearing silently.
- Repository diagram reads use the plural collection, check canonical exam keys
  against full exam identity, and resolve marking rubrics through exact IDs.
  Student lookups no longer fall back to another year/session. Duplicate student
  evaluations and ambiguous rubric references are rejected.
- Class diagram analysis uses extracted data from evaluation records and saved
  grade totals, rather than treating detection counts as awarded marks. Multiple
  different rubrics are rejected because local criterion IDs cannot safely be
  combined; grouping separate diagram questions would require a later change.
- Lecturer HTTP and cached streaming responses refresh diagram analysis with
  read-only queries, without rerunning Bloom classification or grading.
- Fresh exam analysis surfaces diagram validation failures rather than silently
  returning an empty diagram section.
- Student diagram rendering reads detections/entities/relationships from the
  evaluation record, while retaining the earlier artifact-field fallbacks.

Live verification:

- Class panel: **5 students, 16.6/20 average, 83%, 11 criteria**.
- Percentages: 65%, 65%, 95%, 95%, 95%.
- Saved detail for a student without completed essay grading returned **19/20**,
  11 criterion results, extracted diagram data and the exact marking rubric.
  `auto_analyze=False` ensured no inference or derived-data writes.

Checks:

```text
python -m pytest tests/test_diagram_dashboard.py tests/test_exam_paper.py tests/test_student_document_analytics.py tests/test_schemas.py tests/test_independent_equation_audit.py -q -p no:cacheprovider --tb=short
134 passed, 8 xfailed in 9.45s
```

The expected failures are existing independent-equation audit cases, not new
passing claims. New regressions cover saved/cached HTTP and stream responses,
exact references, wrong years/keys, duplicate students, failed evaluations,
missing/excessive marks and multiple rubric collisions. Production frontend
`npm run build` passed (existing bundle-size/npm-config warnings). Python compile
checks and `git diff --check` passed.

No collection was renamed and no saved evaluation, rubric or answer was modified
by this fix. The earlier rubric collection rename was a separate user request.
The browser itself was not visually inspected; restart the analytics backend
if it does not automatically reload Python changes, then refresh the page.
