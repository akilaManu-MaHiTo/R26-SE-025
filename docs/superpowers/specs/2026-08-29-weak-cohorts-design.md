# Weak Cohorts — Lecture Dashboard Design

**Date:** 2026-08-29
**Status:** Draft (awaiting user review)
**Scope:** Lecture Analytics `AnalyticsPage` — identify topic/Bloom-weak students and bulk-act on cohorts. Approach 2 (Ranked Cohorts + Action Drawer) — client-side, no new DB.

## 1. Placement & Architecture

- Insert `WeakCohortsPanel` in `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx:529` between `KpiCards` and `CanonicalTopicTable + AttentionAreasPanel` grid.
- Data sources (existing, no new collections):
  - `GET /api/lecturers/exams/{code}/{session}/analytics` → `analytics.canonical_topic_performance`, `topic_bloom_matrix`, `weakness_scores`, `diagram_analysis` (`app/services/topic_canonicalization.py`, `app/analytics/exam_analytics.py`)
  - `GET /api/lecturers/exams/{code}/{session}/students` → `students[]` (`app/api/lecturer.py:173`)
- Derived client-side `rankedCohorts` via `buildRankedCohorts(analytics, students)` — no backend change, reuses `Badge`/`Card` styling.

## 2. Components

### `WeakCohortsPanel.tsx` (new, `src/app/components/analytics/`)
- Props: `cohorts: RankedCohort[], selectedId: string|null, onSelect(id), onBulk(cohort, action)`
- RankedCohort: `{id, topic, bloom_level?, average_percentage, status/priority, studentCount, students[], weakness, evidence_status}`
- Renders 2-4 cards (max 6, `show more`): header `topic × bloom` + priority Badge + avg% + n + avatars + weakness bar. Actions: `View in table`, `Bulk generate`, `Export CSV`. Empty: `All topics Strong — no weak cohorts`.

### `CohortActionDrawer.tsx` (new, reuses `Dialog` + `TeachingActions` + `Recommendations`)
- Trigger `Bulk generate` → `fetchTeachingActions` + `fetchRecommendations(limit=5, topic=cohort.topic)` (existing `app/api/lecturer.py:426` / `539`)
- Shows `TeachingActions[]` + `RecommendationsResponse.high_priority[]` + `Add to Exam Draft`.

### `AnalyticsPage.tsx` mods
- State `selectedCohortId`, `cohortFilter: (s)=>boolean`
- `filteredStudents = students.filter(matches search && cohortFilter)` — highlights High rows.
- Sticky bulk bar when `selectedCohort.students.length>1`: `Bulk act on 4 students — Generate set | Copy IDs`
- URL sync `?cohort=Schema%20Refinement` via `useSearchParams`.

## 3. Data Flow

```
fetchExamAnalytics → canonical_topic_performance + topic_bloom_matrix + weakness_scores [+ diagram_analysis]
fetchExamStudents → students[] (10 for IT2040 2024)
  ↓ buildRankedCohorts() sort(weakness desc, avg asc, fail_rate desc)
WeakCohortsPanel onSelect → setSelectedCohortId → setCohortFilter (topic_performance% <60 || overall<60)
  ↓
Individual Students Table → filteredStudents highlighted
  ↓ Bulk generate → fetchTeachingActions + fetchRecommendations → CohortActionDrawer → Export CSV
```

- Lazy enrichment: first filter uses `overall<60` + `attention_areas`; `View in table` optionally `fetchLecturerStudentDetail` for top 3 to refine.
- No new backend indexes; purely derived.

## 4. Error Handling & Edge Cases

- **All Strong:** Panel `All topics Strong — no weak cohorts`.
- **Small n (<10):** `evidence_status insufficient_evidence` → muted Badge `· n=3 — interpret with caution`, de-prioritized after `confirmed_weakness`.
- **Diagram vs text:** Missing `diagram_analysis` omits `· Diagrams 52.5%`. Empty `students[]` topic detail falls back to `overall` + hint `Refine with details`.
- **Fetch fails:** Drawer shows `No recommendations — unmapped_topics` + Retry; panel never blocks page (`catch => []`).
- **Performance:** `buildRankedCohorts` O(T×S) `T≤11` `S≤500`, memoized `useMemo([analytics, students])`.

## 5. Testing

- **Unit `buildRankedCohorts.test.ts`:** Fixture `canonical 51.33/56.8/58.75` + `matrix Schema×Analyze 51.33` + `weakness_scores` → asserts `rankedCohorts[0].topic === Schema Refinement`, `priority High`, sort order.
- **Component `WeakCohortsPanel.test.tsx`:** Renders 3 cards, `View in table` filters, `Bulk generate` opens drawer, empty state.
- **Integration `AnalyticsPage.test.tsx`:** Mock `fetchExamAnalytics` (IT2040 2024) + `fetchExamStudents` (10) → Panel between `KpiCards` and `CanonicalTopicTable`, selecting cohort filters table to 4 rows.
- **E2E playwright:** Select `Final Examination` → Weak Cohorts visible → Bulk generate → Drawer with `5Q set` → Export CSV.
- **Regression:** `tests/test_api_lecturer.py`, `tests/test_exam_analytics.py` pass (no backend change).

## 6. Out of Scope (YAGNI)

- Cross-exam trend sparklines, `studentExamResults` early-warning persistence, `create Exam Draft` from cohort (deferred to Approach 3).
- New DB collections or indexes.
