# V2 QuestionExamPredictionEngine + Gradex Integration Design

**Date:** 2026-08-07
**Status:** Approved design
**Scope:** Connect the V2 predictive learning-analytics / exam-recommendation engine into the Gradex AI server and client.

## 1. Purpose

Expose two V2 engine capabilities through the existing Gradex API and frontend:

1. Ranked topic × Bloom **exam recommendations** for the lecturer (drives `ExamCreator.tsx`).
2. **Per-student analytics and study recommendations** (drives a student drill-down in `AnalyticsPage.tsx`).

Adopted flow = **Approach A: read the latest analysis run**; read-only, idempotent, no automatic run bootstrap. Assumes a populated MongoDB (seeded via `run_sample.py` or prior runs) with a local Ollama for optional LLM study actions.

## 2. Constraints and principles

- The browser never computes authoritative mastery or recommendation scores; all math stays deterministic in the V2 backend.
- LLM enriches, explains, generates; it never awards marks or computes mastery.
- Graceful degradation: if Mongo/Ollama are unavailable, endpoints and UI degrade with clear states; they do not crash.
- Existing `Gradex_AI_Server` endpoints and existing `AnalyticsPage` upload/historical flows are unchanged (this feature is additive).

## 3. Architecture

```
Gradex_AI_Server (FastAPI, port 8000)
  app/main.py            + add V2_ROOT to sys.path, include predict router
  app/predict_api.py     NEW read-only router (below)
  ↑ imports from V2 (top-level `app` package):
      app.db.repository          latest_run_id, find_recommendations (new), find_attempts_by_student
      app.services.student_dashboard.build_student_dashboard
      app.api.deps.get_db
      app.schemas.student.StudentDashboard
Gradex_AI_Client (React/Vite)
  ExamCreator.tsx      AI recommendations panel (advisory)
  AnalyticsPage.tsx    Student drill-down tab (additive)
MongoDB (dbms_analytics)   seeded question_attempts / exam_recommendations / analysis_runs
Ollama                     (optional) LLM study actions
```

## 4. Backend wiring (Gradex_AI_Server)

**4a. Import the V2 engine.** In `Gradex_AI_Server/app/main.py`, add to the existing `sys.path` block:

```python
V2_ROOT = PROJECT_ROOT / "V2_QuestionExamPredictionEngine"
```

V2 is a top-level `app` package; `Gradex_AI_Server.app` is namespaced, so no collision.

**4b. New router module `Gradex_AI_Server/app/predict_api.py`** with two read-only endpoints:

```http
GET /api/predict/exam-recommendations
GET /api/predict/students/{student_key}/dashboard?include_llm=false
```

- `exam-recommendations`: resolve latest run via `latest_run_id(db)`. No run → `200 {"status":"no_run","recommendations":[]}`. Otherwise read that run's `exam_recommendations` via a new `find_recommendations(db, run_id)` and return a trimmed shape per recommendation:

```json
{
  "status": "ok",
  "run_id": "...",
  "course_code": "...",
  "exam_id": "...",
  "recommendations": [{
    "topic": "...", "bloom_level": "...", "question_type": "problem_solving",
    "mark_range": [1.0, 4.0], "priority_score": 0.82,
    "component_breakdown": {...}, "evidence": {...}
  }]
}
```

- `student dashboard`: proxy `build_student_dashboard(db, student_key, run_id, include_llm)` unchanged, returning the existing `StudentDashboard` schema. Keeps V2 semantics: `404` unknown student/run; Ollama down while `include_llm=true` → deterministic actions.

**4c. V2 repo addition.** Add `find_recommendations(db, run_id) -> list[dict]` to `V2_QuestionExamPredictionEngine/app/db/repository.py`.

**4d. Requirements.** Gradex server env needs `motor`, `pydantic-settings`, `httpx` (student dashboard + optional LLM path). Embeddings/sentence-transformers remain optional; neither endpoint calls them.

**4e. Error handling.**

- `exam-recommendations`: no run → `200 {status:"no_run", recommendations:[]}`; Mongo error → `503` with message.
- Student dashboard: unknown student/run → `404`; Mongo error → `500`; LLM unavailable → deterministic actions.

## 5. ExamCreator.tsx (client)

Add an advisory **AI recommendations** panel:

- Wire the existing "Auto-balance" button to load `GET /api/predict/exam-recommendations` (loading → results → empty).
- A Card listing each recommendation: `topic` + `bloom` badges, `priority_score` badge, and an evidence tooltip ("mastery 0.41 · failure rate 0.38 · N students · confirmed_weakness").
- Advisory only: recommendations never mutate the question bank or auto-add questions.
- `no_run` state → muted hint "Run analytics first — upload exam + answers in Student Analytics".
- Reuse existing `Card`, `Badge`, `Button`, `Separator` styling. Keep the static `bank` and manual picker untouched.

## 6. AnalyticsPage.tsx

Add a **Student Drill-down** tab (Tabs already imported), additive to existing upload + historical flows:

- Student `Select` populated from the current `students` list.
- On select, fetch `GET /api/predict/students/{student_key}/dashboard?include_llm=true` via `backendBaseUrl`.
- Render:
  - Study-action cards (action, topic, rationale, practice_topics) with a `source` badge (`llm` / `deterministic`).
  - Weakest topics (ranked).
  - Topic skills and Bloom skills as Progress bars with `evidence_status` labels.
  - Cohort comparison and exam performance summary (percentage, grade).
- Loading and error states for the fetch; existing cohort analytics untouched.
- Reuse existing `Card`, `Badge`, `Progress`, `Separator`, `Tabs` styling.

## 7. Testing

- **V2 repo:** unit test for `find_recommendations`; run existing V2 suite to confirm unchanged.
- **Server:** light `TestClient` tests for both endpoints against a test Mongo DB reusing V2 fixtures — happy path, `no_run`, unknown student `404`.
- **Client:** `npm run build` (Vite/TS) typechecks the new components.

## 8. Out of scope

- Bootstrapping/ml runs from the client (Approach B) and auto-seed (`C`).
- LLM candidate-question generation surfaced in the client (recommendations-only decided).
- Authentication / role-based authorization.
- Changing the existing `Gradex_AI_Server` `/api/analytics/*` endpoints or the existing AnalyticsPage upload/historical flows.