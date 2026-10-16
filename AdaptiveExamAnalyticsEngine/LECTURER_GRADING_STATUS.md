# Lecturer grading progress

Implemented and verified 2026-10-16.

The lecturer student endpoint now uses the existing exact-match reconstruction
service for canonical exams. It includes roster students, processing/not-started
submissions and diagram-only results, without grading or changing stored data.

Each row separates:

- `components.essay` and `components.diagram`: status, nullable awarded marks
  (`obtained`) and verified maximum (`maximum`). Status may be graded,
  processing, not_started, failed, missing_submission, needs_review or not_required.
- `grading_status`: complete, pending or needs_review.
- `score`: combined awarded marks, maximum and percentage. Missing component
  evaluations keep the combined total/percentage null; no zero is invented.
- `review_reasons`: human-readable explanation of a provisional result.
- `analysis_status`: separate from grading completion; saved diagram details
  remain available while essay grading is pending.

`app/services/lecturer_grading.py` builds these rows from the verified combined
grades. The existing legacy-exam path is retained; the UI explicitly says that
combined progress is unverified when legacy rows lack component statuses.
Ambiguous canonical keys return HTTP 409 instead of an empty student list.

The client displays a grading-progress card and Essay / Diagram / Overall /
Grading status columns. Pending totals show a dash; review-needed percentages
are labelled provisional. Only complete combined grades enter the overall
average. Existing essay KPIs/distribution are labelled Essay analytics, while
diagram analytics retain their own graded-student count.

Status fetching runs independently of model analysis. Failed status requests
show an error rather than false zero counts. A leftover loading-state reset
that could hide completed status requests was removed. Roster students without
any result cannot trigger analysis by clicking View; available diagram results
remain accessible. Clickable rows support Enter/Space keyboard activation.

Live read-only verification of the 2025 IT2040 exam:

| Measure | Verified result |
| --- | --- |
| Students | 5 |
| Essay | 2 graded, 1 processing, 2 not started |
| Diagram | 5 graded |
| Overall | 3 pending, 1 needs review, 1 complete |
| Complete-only average | 80.91% |
| Pending totals and percentages | null |

Checks executed:

```text
python -m pytest tests/test_lecturer_grading_status.py tests/test_diagram_dashboard.py tests/test_exam_paper.py tests/test_student_document_analytics.py tests/test_schemas.py tests/test_independent_equation_audit.py -q -p no:cacheprovider --tb=short
139 passed, 8 xfailed in 8.27s

npx vitest run src/app/components/analytics/GradingStatus.test.tsx src/app/components/ExamKeysPage.test.tsx
2 files passed; 11 tests passed

npm run build
Passed
```

Python compile checks and git whitespace checks passed. Existing expected audit
failures and frontend bundle-size/npm-config warnings remain. No database
records were modified. Real-browser appearance and stalled-job detection were
not checked; Processing reports the saved state, not proof of an active worker.
