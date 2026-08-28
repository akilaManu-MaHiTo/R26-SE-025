# ExamCreator Full-Paper Editor Design

> Spec for Approach 1 (Split Layout) — A) Draft + PDF only, no DB persistence.

## 1. Overview

Lecturer creates a new draft exam from scratch via `ExamCreator.tsx:1`. Left 65% is a full-paper editor seeded from JSON paper structure (`question_number/topic/parts[a,b,c]/max_marks`, total 100). Right 35% shows adaptive recommendations (weak areas + ranked questions) fetched from `V2_QuestionExamPredictionEngine` recommendation engine. Top bar switches exams. Lecturer inserts recommended questions via `Insert as Q2 / Add part to Q3` chooser, edits instantly, sees live total, downloads PDF client-side.

## 2. Layout & Routing

- Route `/exam-creator` sets `hideSidebar=true` via `Gradex_AI_Client/src/app/routeConfig.tsx` (or `App.tsx` layout prop). If flag missing, fallback to normal layout with sidebar.
- Top bar: `Select Exam` dropdown populated by `fetchExams()` (course_code, year, session_name). On change → `fetchRecommendations(course, session, year, month, semester, limit=12)` re-fetches.
- Split: Left 65% scrollable editor (`overflow-y-auto`), Right 35% sticky recommendations panel. Footer bar fixed: `[Preview] [Download PDF] Total: 87/100`.
- Responsive: <1024px stacks vertically (editor top, recs bottom). Visual companion: `http://localhost:52755` mockup approved.

## 3. Paper Data Model (Left Editor)

```ts
type Paper = {
  exam: string; // "IT2040 – Database Management Systems"
  year: number; // 2023
  questions: {
    question_number: number; // auto 1..n
    topic: string; // Select from 11 canonicals (topic_taxonomy.json)
    parts: { part: string; // a,b,c auto
             question: string; // Textarea, supports (i)/(ii) multiline
             max_marks: number; // Input 1-40 editable
           }[];
  }[];
};
```

- Seeded from example JSON (Q1 20, Q2 20, Q3 25, Q4 35 = 100). `question_number` and `part` auto-renumber on insert/delete.
- Controls: `topic` Select, `question` Textarea, `max_marks` Number Input, `×` delete part/question, `+ Add part` (next letter), `+ Add Custom Question` (blank Q).
- Draft state is `useState<Paper>` client-only, no DB writes.

## 4. Insert/Edit Interaction (Right → Left)

- Card: `Badge topic | bloom | difficulty | marks | priority | score%`, `text` line-clamp, `reason` box (weakness_pct, lecture covered, tutorial_count, exam_recent_count, bloom_gap), buttons `Insert as ▼` + `Add` / `Edit` / `Reject`.
- `Insert as` dropdown: `Q1 ... Qn+1`, `Qk → new part`. `Add` clones `rec.text` → `{part: nextLetter, question: rec.text, max_marks: rec.marks || 10, topic: rec.canonical_topic}`. Splices into `Paper.questions` at chosen index, renumbers, scrolls to inserted Q with `ring-primary` highlight 1s. `Reject` adds to `rejectedIds` Set (filters from right). `Edit` scrolls to left editor for that Q (future: inline modal).
- Instant edit: all left inputs are controlled, update `Paper` immediately.

## 5. Validation (Non-blocking)

- `total = Σ parts.max_marks`. Footer shows `Total: 87/100 ⚠️ needs 13 more` (amber <100, red >100, green =100). No block on download. Invalid marks (NaN/≤0) shows inline `Input error` but still downloadable.
- Bloom/Difficulty distribution mini bar derived from `question_bank` bloom if available, else edited `bloom_level`. Shows gap vs target (e.g., Apply 40%).

## 6. Data Flow

1. Mount → `fetchExams()` → dropdown.
2. Select exam → `fetchRecommendations()` → `GET /api/lecturers/exams/{course}/{session}/recommendations?year=&month=&semester=&limit=12` → `Gradex_AI_Server/app/main.py` proxies `V2_QuestionExamPredictionEngine/app/api/lecturer.py:109` which computes `weakness 0.5 SQL` + `question_bank.json:161` + `0.35/0.20/0.15/0.15/0.15` scoring → returns `weakness_scores, ranked_weak_topics, high/medium` cards.
3. Right panel renders `Weak Areas` badges + `High/Medium/Low` sections. `draft` state seeded from example JSON, updated only client-side.
4. `Download PDF` → client-side `jspdf` renders A4: header `exam year`, each `Question N (Topic)` + `a) question [max_marks]`, page breaks, footer `Total: 100`. `Preview` opens Blob in new tab. No server call.

## 7. Error Handling

- `fetchExams` empty → `No exams found. Ingest submissions first.` Card.
- `fetchRecommendations` 404 → `No analytics for this exam` with link to AnalyticsPage.
- Network error → `ProgressLoader` → `Retry` button.
- PDF generation error → toast `Failed to generate PDF`.

## 8. Testing

- `tests/test_recommendation_engine.py` (5 passed) covers scoring.
- `tests/test_api_recommendations.py` (2 passed) covers `GET recommendations`.
- Client: mock `fetchRecommendations` → `ExamCreator` renders `High (n)` cards, `Insert as Q2` updates `question_number` and `total`. `vite build` passes (23.58s). No backend persistence tests for A.

## 9. Out of Scope (Future)

- DB persistence (`POST /drafts`), versioning, collaborative editing, LLM regeneration of questions, marks auto-suggestion. Kept YAGNI for A.
