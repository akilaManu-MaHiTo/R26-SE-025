# Lecturer Analytics Dashboard - Design Spec

## Purpose

Build a lecturer-facing dashboard that turns one exam's analytics document into:
Data -> Analysis -> Problem -> Recommendation -> Action.

The lecturer should never have to interpret raw percentages themselves. Every number on screen should point toward a status, a priority, and where possible a next step.

Source data: a single MongoDB document per exam. This spec covers one exam (IT2040, Final Exam 2023). Multi-exam features are stubbed but not buildable yet.

---

## Decisions Made

- **Canonicalization layer**: Backend endpoint (post-processing on GET, not pipeline modification)
- **Teaching actions**: LLM-generated, on-demand with caching in MongoDB
- **Config storage**: Backend JSON files (topic_taxonomy.json, thresholds.json)
- **Frontend**: Full rewrite of AnalyticsPage.tsx (single-page layout, not tabbed)

---

## Data Contract

```json
{
  "subject_code": "IT2040",
  "subject_name": "Database Management Systems",
  "year": 2023,
  "month": 5,
  "semester": 1,
  "session_name": "Final Examination",
  "exam": { "session_name": "Final Examination", "total_marks": 100, "question_count": 4 },
  "statistics": {
    "total_students": 9,
    "attempted_students": 9,
    "average_score": 52.22,
    "average_percentage": 57.36,
    "pass_rate": 77.78,
    "highest_score": 82,
    "lowest_score": 35
  },
  "topic_performance": [
    { "topic": "SQL Queries and Triggers", "average_percentage": 33.33, "status": "Critical" }
  ],
  "bloom_performance": [
    { "level": "Analyze", "average_percentage": 56.67 },
    { "level": "Apply", "average_percentage": 58.68 }
  ],
  "question_performance": [
    { "question_id": "Q01", "topic": "...", "bloom_level": "Analyze", "average_percentage": 60.56 }
  ],
  "attention_areas": [
    { "type": "topic", "name": "SQL Queries and Triggers", "average_percentage": 33.33, "priority": "Critical" }
  ],
  "insights": [ "SQL Queries and Triggers is the weakest topic across the class." ],
  "generated_at": "2026-08-22T19:25:40.022228+00:00",
  "analytics_version": "1.0"
}
```

No question text, marking scheme, student IDs, or per-student scores exist in this document.

---

## Topic Canonicalization (Build This First)

### Problem

The stored topic_performance and attention_areas arrays contain fragmented duplicate topics. The same underlying subject area is labeled slightly differently, each with its own separately-computed average.

### Known Fragment Groups

| Canonical topic | Raw fragments | Raw averages |
|---|---|---|
| SQL Queries & Triggers | "SQL Queries and Triggers", "SQL Queries and Triggers in Database Management Systems", "SQL Queries, Triggers, Role-Based Access Control (RBAC)" | 33.33 / 53.85 / 58.97 |
| Database Indexes & Storage | "Database Indexes and Data Structures", "Database Indexes and Storage Structures" | 40.00 / 52.50 |
| Transactions & Concurrency Control | "Database Transaction Management and Concurrency Control", "Database Transactions and Concurrency Control" | 50.00 / 53.75 |
| Database Recovery | "Database Recovery Algorithms", "Database Recovery Algorithms and Log Management" | 58.75 / 65.00 |

Unclear / leave as-is: "Database Management Systems" (general), "Database Design and Relational Algebra", "Database Connectivity and SQL Injection Prevention with JDBC".

### Canonicalization Algorithm

1. Load topic_taxonomy.json config mapping raw topic strings to canonical_topic_id.
2. For each canonical_topic_id, recompute average_percentage by returning to the RAW per-question / per-student scores that fed each fragment (NOT by averaging the already-computed fragment percentages).
   - If raw per-student scores are not available, fall back to a WEIGHTED average using each fragment's underlying question_count as the weight, and flag the merged value as "estimated" in the UI.
3. Attach to each canonical topic: merged average_percentage, list of contributing raw fragment labels, total question_count and student_count.
4. Regenerate attention_areas and insights FROM the canonical topic list.
5. Keep raw, unmerged topic_performance in admin/debug view only.

### Topic Taxonomy Config Shape

```json
{
  "sql_queries_triggers": {
    "label": "SQL Queries & Triggers",
    "aliases": [
      "SQL Queries and Triggers",
      "SQL Queries and Triggers in Database Management Systems",
      "SQL Queries, Triggers, Role-Based Access Control (RBAC)"
    ],
    "subtopics": ["RBAC"]
  },
  "indexes_storage": {
    "label": "Database Indexes & Storage",
    "aliases": ["Database Indexes and Data Structures", "Database Indexes and Storage Structures"]
  },
  "transactions_concurrency": {
    "label": "Transactions & Concurrency Control",
    "aliases": [
      "Database Transaction Management and Concurrency Control",
      "Database Transactions and Concurrency Control"
    ]
  },
  "database_recovery": {
    "label": "Database Recovery",
    "aliases": ["Database Recovery Algorithms", "Database Recovery Algorithms and Log Management"]
  }
}
```

### Unmapped Topic Handling

If a future exam produces a raw topic string with no match in topic_taxonomy, flag it for admin review, then persist the decision into the taxonomy config.

---

## Statistical Confidence Requirement

total_students = 9. Every displayed percentage must be paired with its underlying count.

- Every topic/question/Bloom percentage: show (n students, m questions) as secondary text.
- If n < 10, render a "low sample size" indicator (muted dot + tooltip).
- Do not compute or display any statistic that implies precision the sample size does not support.

---

## Status and Priority Thresholds (Config-Driven)

```json
{
  "status_thresholds": [
    { "min": 0,  "max": 39.99,  "status": "Critical",           "priority": "Critical" },
    { "min": 40, "max": 59.99,  "status": "Needs Improvement",  "priority": "High" },
    { "min": 60, "max": 74.99,  "status": "Developing",         "priority": "Medium" },
    { "min": 75, "max": 100,    "status": "Strong",             "priority": "Low" }
  ]
}
```

status describes performance level. priority describes urgency of lecturer action. These are two distinct fields everywhere, even though derived from the same thresholds today.

---

## Backend Architecture

### New Files

1. `V2_QuestionExamPredictionEngine/app/services/topic_canonicalization.py` - Canonicalization logic
2. `V2_QuestionExamPredictionEngine/config/topic_taxonomy.json` - Topic aliases config
3. `V2_QuestionExamPredictionEngine/config/thresholds.json` - Status/priority thresholds

### Modified Files

1. `V2_QuestionExamPredictionEngine/app/api/lecturer.py` - Extend analytics endpoint with canonical fields
2. `V2_QuestionExamPredictionEngine/app/api/lecturer.py` - Add teaching-actions endpoint
3. `V2_QuestionExamPredictionEngine/app/schemas/exam_analytics.py` - Add canonical fields to schema

### Canonicalization Service

The service lives in `app/services/topic_canonicalization.py` and is called by the analytics endpoint on GET.

Flow:
1. Load topic_taxonomy.json
2. For each canonical topic, find all matching raw fragments (exact alias match)
3. Fetch raw submissions for the exam from MongoDB
4. For each canonical topic, iterate over all questions mapped to any of its fragments, collect per-student scores, compute weighted average (by marks, not by fragment percentage)
5. Flag unmapped topics -> store in unmapped_topics field
6. Regenerate attention_areas from canonical topics
7. Regenerate insights from canonical + question + Bloom data

### Extended Analytics Response

The GET /api/lecturers/exams/{code}/{session}/analytics endpoint returns the existing ExamAnalyticsDocument plus these new fields:

```json
{
  "...existing fields...": "...",
  "canonical_topic_performance": [
    {
      "topic": "SQL Queries & Triggers",
      "average_percentage": 48.72,
      "status": "Needs Improvement",
      "priority": "High",
      "question_count": 3,
      "student_count": 9,
      "contributing_fragments": ["SQL Queries and Triggers", "SQL Queries and Triggers in Database Management Systems", "SQL Queries, Triggers, Role-Based Access Control (RBAC)"],
      "is_estimated": false
    }
  ],
  "canonical_attention_areas": [
    { "type": "topic", "name": "SQL Queries & Triggers", "average_percentage": 48.72, "priority": "High", "question_count": 3, "student_count": 9 }
  ],
  "canonical_insights": [
    "SQL Queries & Triggers is the weakest topic at 48.72% across 3 questions and 9 students."
  ],
  "unmapped_topics": []
}
```

### Teaching Actions Endpoint

New endpoint: GET /api/lecturers/exams/{code}/{session}/teaching-actions

- On-demand LLM call to generate 3-5 concrete bullet recommendations per Critical/High canonical topic + lowest question
- Input to LLM: canonical topics with percentages, status, question IDs
- Output: structured JSON [{topic, priority, actions: [str], generated_at}]
- Caching: Store result in teaching_actions_cache collection keyed by (code, session, analytics_generated_at). Cache expires when analytics document is regenerated.
- Fallback: If LLM unavailable, return generic template-based recommendations (status -> action templates)

---

## Frontend Architecture

### Full Rewrite

File: Gradex_AI_Client/src/app/components/AnalyticsPage.tsx - complete rewrite.

### Layout (Single-Page, Not Tabbed)

```
+------------------------------------------------------+
| Header: Course code, name, session, year  [Export][Report]
+------------------------------------------------------+
| KPI Row: 6 metric cards with sample-size indicators  |
+--------------------------+---------------------------+
| Topic Performance Table  | Attention Areas Panel     |
| (canonical, sorted asc)  | (grouped by priority)     |
+--------------------------+---------------------------+
| Bloom Performance Chart  | Question Performance      |
| (Recharts BarChart)      | (table + bar, flag lowest)|
+--------------------------+---------------------------+
| Key Insights (color-coded cards)                      |
+------------------------------------------------------+
| Recommended Teaching Actions (LLM-generated cards)    |
+------------------------------------------------------+
```

### New Components

1. **KpiCards.tsx** - 6 metric cards (Total Students, Avg Score, Avg%, Pass Rate, Highest, Lowest) with sample-size indicators
2. **CanonicalTopicTable.tsx** - Sorted ascending by percentage, status badges, priority dots, click opens TopicDetailModal
3. **AttentionAreasPanel.tsx** - Grouped by priority (Critical > High > Medium), top 2 per band + "View All", Critical always visible even if empty
4. **BloomChart.tsx** - Recharts BarChart, only render levels present in data, caption noting only assessed levels
5. **QuestionPerformanceTable.tsx** - Table + bar, auto-flag lowest with visual marker
6. **InsightsPanel.tsx** - Color-coded cards (red=weakest, green=strongest, amber=lowest question)
7. **TeachingActions.tsx** - LLM-generated action cards with "Recommended" tag, Generate Practice Questions button (stub)
8. **TopicDetailModal.tsx** - Modal/drawer for topic detail view
9. **QuestionDetailModal.tsx** - Modal/drawer for question detail view

### API Layer

Extend Gradex_AI_Client/src/app/api/lecturerApi.ts with:
- fetchTeachingActions(courseCode, sessionName) -> TeachingAction[]

### State Management

useState for: selected exam, view mode (list/analytics), detail modals. No Redux/Zustand needed.

### Key Behaviors

- Bloom chart: only render levels present in data (currently Apply + Analyze, not all 6)
- Question table: auto-flag lowest with icon + color, not just sort order
- Attention Areas: Critical band renders empty state ("No critical areas") rather than disappearing
- Export/Report buttons: stubbed (Phase 2)
- Topic detail: show canonical label, merged %, status, priority, contributing fragments, related question IDs, Bloom levels
- Question detail: show question ID, topic, Bloom level, class average, status. Disable buttons requiring additional data with tooltips.

---

## Explicitly Out of Scope

- Student drill-down (needs separate per-student collection)
- Exam comparison / historical trends (only one exam exists)
- Question text, marking scheme, mark distribution, individual responses
- Learning material / practice question recommendations tied to actual course content
- Export (PDF/CSV) - Phase 2
- Admin Unmapped Topics review queue - Phase 2

---

## Build Phases

### Phase 1 (MVP) - This Build

- Canonicalization pipeline (topic_canonicalization.py + config files)
- Config-driven thresholds
- Extended analytics endpoint with canonical fields
- Full frontend rewrite (all components listed above)
- Sample-size indicators
- Teaching actions endpoint with LLM + cache + fallback

### Phase 2 (Future)

- Detail views with disabled/stubbed actions
- Export (PDF/CSV)
- Admin Unmapped Topics review queue

### Phase 3 (Needs New Data Sources)

- Student-level drill-down
- Exam comparison + trend charts
- Question-text-aware recommendations

---

## Acceptance Criteria

- [ ] No topic is displayed twice under different labels on the main dashboard
- [ ] Every percentage shown has a visible (n, m) sample-size annotation
- [ ] Status thresholds are read from config, not hardcoded in components
- [ ] Bloom chart shows only levels present in data (currently 2, not a fixed 6)
- [ ] Attention Areas panel is built from canonical (merged) topics
- [ ] No fabricated student-level, comparison, trend, or question-text data anywhere
- [ ] AI/system-generated recommendations are visually distinguished from raw data readouts
- [ ] Critical priority band renders an explicit empty state rather than disappearing when empty
